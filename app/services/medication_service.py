import asyncio
import base64
import difflib
import io
import logging
import os
import re
import time
import uuid
from typing import NamedTuple, cast

import httpx
from fastapi import BackgroundTasks, HTTPException, status
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import AsyncSessionLocal
from app.dtos.medication_dto import (
    FoodInteractionCheckResult,
    FoodItem,
    GuideCard,
    InteractionCheckResult,
    InteractionWarning,
    MedicationScheduleCreateRequest,
    MedicationScheduleResponse,
    MedicationScheduleUpdateRequest,
    QuickRegisterCandidate,
    QuickRegisterResult,
    RecognitionCandidate,
    RecognitionConfirmResult,
    RecognitionJobCreateResult,
    RecognitionResult,
)
from app.models.medication_model import MedicationRecognitionJob, MedicationSchedule
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.family_repository import FamilyRepository
from app.repositories.food_drug_interaction_repository import FoodDrugInteractionRepository
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client
from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.food_item_extraction import extract_food_items
from app.services.side_effect_notification_service import SideEffectNotificationService

logger = logging.getLogger("app.medication_service")

CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")

# 타임아웃/5xx처럼 재시도하면 성공할 여지가 있는 실패에 한해서만 재시도한다.
# 401/403 같은 인증 오류나 응답 파싱 실패는 재시도해도 결과가 같으므로 즉시 실패 처리한다.
_CLOVA_OCR_MAX_ATTEMPTS = 2
_CLOVA_OCR_RETRY_DELAY_SECONDS = 0.5

# 약품명 후보로 볼 만한 OCR 텍스트 블록 판별 기준.
# "정"/"캡슐" 같은 제형 접미사만으로는 "환자정보", "서방정"(잘린 조각) 등 일반 텍스트도
# 걸려버려서, 반드시 (a) 처방전 약품 목록에서 흔히 쓰이는 "*" 불릿 표시가 있거나 (b) 흔한
# 약품 제형 접미사로 끝나는 경우만 후보로 인정한다. (b)는 최소 길이(_MIN_DRUG_NAME_LEN)
# 조건과 함께 적용되므로 "환자정보"/"서방정" 같은 짧은 일반 텍스트 조각은 그 단계에서 이미
# 걸러진다.
#
# (#128) 예전에는 용량 숫자+단위(mg/g/ml)가 붙어 있기만 해도 후보로 인정했는데, 실제
# 처방전에는 브랜드명 카드 아래에 괄호 없이 "알마게이트 500mg"처럼 성분명+용량 줄이 그대로
# 따라붙는 포맷이 있어(약국 영수증형 처방전), 이 줄도 용량 패턴만으로 별도 약품 후보가 되어
# 브랜드명과 성분명이 각각 다른 약으로 중복 등록됐다(6개 약인데 14개로 등록됨). 제형 접미사가
# 없는 용량줄은 더 이상 자체적으로 후보가 되지 않고, 대신 _fuzzy_match_unrecognized_fields의
# 유사도 매칭 경로로 넘어가 실제 마스터 DB에 있는 약과 확실히 비슷할 때만 구제된다.
_KOREAN_TOKEN_PATTERN = re.compile(r"[가-힣]{2,}")
_DOSAGE_PATTERN = re.compile(r"\d+(mg|g|ml)", re.IGNORECASE)
_MIN_DRUG_NAME_LEN = 5
# 제형 접미사 뒤에 용량/단위 표기(숫자, ㎍/h 같은 비-한글 문자, "[한국먼디파마]" 같은 제조사
# 대괄호 표기)가 더 붙어도 인정한다. 문자열 "끝"까지 한글이 없어야 한다고 앵커하면, 처방전에서
# 흔히 브랜드명과 제조사명이 한 줄에 같이 붙는 실제 포맷("노스판패취10ug/h [한국먼디파마]")에서
# 깨진다 — 그래서 접미사 바로 다음 글자가 한글로 이어지지만 않으면("서방정보"처럼 붙어버리는
# 경우만 제외) 인정하도록, 끝 앵커 대신 다음 글자가 한글이 아닌지만 확인한다.
_DRUG_FORM_SUFFIX_PATTERN = re.compile(r"(정|캡슐|시럽|패취|점안액|디스커스|연고|겔|주)(?![가-힣])")

# 약국/병원명은 처방전 헤더에 "*" 불릿과 함께 적히기도 해서 _looks_like_drug_name의 "*" 조건만으로는
# 걸러지지 않는다("SAMPLE*약국" 등). 문자열 "끝"에만 앵커링하면 "본 약국의 의견과는..."처럼 조사(의/은/는
# 등)가 곧바로 붙은 실제 OCR 필드("약국의")를 놓친다 — 한국어 조사는 띄어쓰기 없이 명사에 붙으므로,
# 끝 앵커 대신 텍스트 어디에든 기관명이 포함되면 제외한다(실제 드러그명에 약국/병원/의원/한의원이
# 부분문자열로 등장하는 경우는 없다고 봐도 안전하다).
_INSTITUTION_SUFFIX_PATTERN = re.compile(r"약국|병원|의원|한의원")

# (#OCR-LLM) "성분/함량", "효능/효과"처럼 처방전 문서에 고정으로 박히는 라벨 문구가 CLOVA에
# 심하게 오인식되면("생봉/행정") 우연히 "정"으로 끝나 _DRUG_FORM_SUFFIX_PATTERN을 통과해버린다.
# 실제 약품명에서 "/"는 항상 숫자와 함께 온다(예: "타진서방정 10/5mg"의 복합 용량 표기) — 라벨
# 문구는 숫자 없이 한글 단어끼리만 "/"로 이어지므로, "/"가 있는데 숫자가 하나도 없으면 약품명이
# 아닌 라벨/문구로 보고 제외한다.

# (#120) "아스피린에 과민증이 있는 경우..."처럼 처방전 복약안내 문구에 성분명이 조사와 함께
# 언급되면("아스피린에"), 실제로는 완결된 약품명이 아닌 문장 중간 단어인데도 편집거리상 다른
# 실약품명("아스피린정")과 우연히 비슷해(1글자 차이) 임계값을 넘겨버릴 수 있다. 조사는 한국어에서
# 띄어쓰기 없이 명사 바로 뒤에 붙으므로, 이런 조사로 끝나는 토큰은 완결된 약품명일 수 없다고 보고
# 퍼지 매칭 대상에서 제외한다.
#
# (#OCR-LLM-2) "전액본인부담금이란"처럼 영수증/문서에 박힌 설명 문구("~이란")도 "*" 불릿과 함께
# OCR 오인식되면 마찬가지로 문장이 완결되지 않은 것으로 보고 제외한다 — "란"으로 끝나는 실제
# 약품명은 없다고 봐도 안전하다.
_TRAILING_PARTICLE_PATTERN = re.compile(
    r"(?:에서|부터|까지|으로|처럼|이나|은|는|이|가|을|를|도|만|와|과|의|에|로|나|란)$"
)

# (#106) CLOVA OCR이 "패취"를 "매취"로 읽는 것처럼 글자 하나를 비슷한 글자로 잘못 읽으면,
# 접미사/용량 패턴이 아예 안 맞아 _looks_like_drug_name을 통과하지 못한다. 이런 텍스트를
# 구제하기 위해 숫자/기호를 떼고 한글만 남긴 뒤 마스터 DB 약품명(마찬가지로 한글만 남긴 것)과
# 편집거리 기반 유사도를 비교한다. 임계값은 실제 오탈자 케이스("노스판매취" vs "노스판패취" ≈
# 0.8)와 노이즈 텍스트(처방전 설명 문구 등, 대부분 0.3 미만)를 실측해 분리되는 지점으로 정했다.
_FUZZY_MATCH_THRESHOLD = 0.8
_FUZZY_MATCH_MIN_KOREAN_LEN = 3

# (#108) 마스터 DB(dur_prod_master_list, 27,000여 개)를 매칭/퍼지 후보로 쓴다. 전체를 매번
# 편집거리로 비교하면 느리므로, 한글 쿼리의 앞 몇 글자를 접두어로 먼저 후보를 좁힌다(대부분의
# OCR 오인식은 뒷글자에서 발생하고 앞글자는 맞는 경우가 많다).
_FUZZY_TIER1_PREFIX_LEN = 2
_FUZZY_TIER1_CANDIDATE_LIMIT = 300

# ("더보기 > 약품 검색"과 마스터 DB 불일치 수정) 수동 등록(자동완성 검색/빠른 등록) 후보 조회 상한.
_SEARCH_TIER1_CANDIDATE_LIMIT = 10


def _korean_only(text: str) -> str:
    return "".join(_KOREAN_TOKEN_PATTERN.findall(text))


def _best_fuzzy_candidate(query: str, candidates: list[tuple[str, str]], threshold: float) -> str | None:
    """`candidates`((item_seq, 이름)) 중 `query`(한글만 남긴 OCR 텍스트)와 가장 유사하면서
    임계값 이상인 것의 item_seq를 반환한다.

    (#120) 후보와 길이가 같은 것만 비교한다 — 이 함수의 목적은 "글자 하나가 비슷한 다른 글자로
    잘못 읽힌" 같은-길이 치환 오류 구제(T-MED-9)이지, "성분명만 언급되고 제형 접미사가 없는"
    더 짧은 텍스트를 임의로 늘려 다른 약과 매칭하는 것이 아니다. 예: "아스피린"(성분명 단독
    언급, 4자)은 "아스피린정"(5자)과 글자 하나 차이로 보이지만(ratio≈0.89), 실제로는 완전히
    무관한 다른 약의 성분명 언급일 뿐이다 — 길이가 다르면 애초에 비교 대상에서 제외한다."""
    best_key: str | None = None
    best_ratio = 0.0
    for key, name in candidates:
        korean_name = _korean_only(name)
        if len(korean_name) != len(query):
            continue
        ratio = difflib.SequenceMatcher(None, query, korean_name).ratio()
        if ratio > best_ratio:
            best_ratio, best_key = ratio, key
    return best_key if best_ratio >= threshold else None


class MatchedDrug(NamedTuple):
    """(T-MED-16) 매칭 파이프라인이 다루는 최소 단위 — 마스터 DB(`dur_prod_master_list`)를
    직접 조회하므로 더 이상 MySQL에 캐싱할 필요가 없어, `Medication` ORM 대신 이 튜플로
    item_seq/item_name만 주고받는다."""

    item_seq: str
    item_name: str


# T-MED-3: OCR이 실패했거나(키 미설정/호출 예외/빈 응답) QA가 dummy_mode를 명시적으로 요청했을 때
# 쓰는 고정 더미 인식 텍스트. 처방전 목록 표기 관례("*" 불릿)를 그대로 따라야 기존 매칭 로직
# (_looks_like_drug_name)을 그대로 태워서 "실제 인식됐을 때와 동일한 흐름"으로 검증할 수 있다.
DUMMY_OCR_RAW_TEXT = ["*타이레놀정", "*아스피린정"]

# T-MED-6: 더미 텍스트는 결정적 테스트 데이터라 confidence 개념이 없으므로, 실제 인식과 동일한
# 코드 경로를 태우기 위해 confidence=1.0(완전 확신)으로 취급한다.
_DUMMY_OCR_CONFIDENCE = 1.0

# T-MED-6: OCR 텍스트가 약품명처럼 전혀 안 보여 매칭 후보가 하나도 없을 때(마스터 DB 상위 몇 개를
# 참고용으로만 보여주는 경우) 부여하는 낮은 match_rate — 실제 OCR 근거가 없으므로 사용자 확인을
# 강하게 유도해야 한다.
_NO_OCR_EVIDENCE_MATCH_RATE = 0.3

# T-MED-6: 마스터 DB에 없어 즉석 생성된(AUTO_ 더미) 약품은 OCR 신뢰도가 아무리 높아도 "검증되지
# 않은 신규 등록"이라는 리스크가 남으므로, match_rate에 상한을 둬 사용자가 한 번 더 확인하게 한다.
_AUTO_CREATED_MATCH_RATE_CAP = 0.5

# T-MED-13: dummy_mode(T-MED-3)는 confidence와 마찬가지로 용법 정보도 없는 결정적 테스트 데이터라,
# 실제 인식과 동일한 흐름을 태우기 위해 대표적인 예시값을 그대로 둔다. `dummy_mode` 플래그로 이미
# 실인식과 명시적으로 구분되므로, 실제 값처럼 오인될 위험이 없다.
_DUMMY_DOSAGE = "1정"
_DUMMY_TIMES = ["09:00", "13:00", "19:00"]
_DUMMY_DURATION = "3일"
_DUMMY_INSTRUCTION = "식후 30분 복용"

# T-MED-13: 처방전 OCR 원문에서 실제 용법 정보를 뽑아내기 위한 패턴. 실경로에서 이 패턴에 맞는
# 텍스트를 찾지 못하면, 확인되지 않은 값을 마치 인식된 것처럼 보여주지 않도록 None을 반환한다.
_DOSAGE_COUNT_PATTERN = re.compile(r"1회\s*(\d+)\s*(정|캡슐|포)")
_DURATION_PATTERN = re.compile(r"(\d+)\s*일분")
_TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_INSTRUCTION_PATTERN = re.compile(r"(식후|식전|취침\s*전)\s*(\d+\s*분)?")


# T-DOC-2: e약은요(의약품개요정보) API 응답의 상호작용 문항("이 약을 사용하는 동안 주의해야 할
# 약 또는 음식은 무엇입니까?")은 실제로는 약물 간 상호작용과 음식/음주 주의사항이 한 텍스트에
# 섞여 있다(실 API로 확인 — 아스피린 사례 대부분이 다른 약과의 병용 얘기였고 음식 언급이 없거나
# 일부에 불과했다). "음식" 탭에 약물 간 상호작용까지 그대로 보여주면 오해를 주므로, 음식/음주
# 키워드가 있는 문장만 골라낸다.
_FOOD_GUIDE_CARD_TITLE = "복약 중 음식 주의사항"
_NO_FOOD_INTERACTION_MESSAGE = "확인된 음식·음주 관련 주의사항이 없습니다."
_FOOD_INFO_UNAVAILABLE_MESSAGE = (
    "식약처 e약은요에서 이 약의 정보를 찾지 못해 음식·음주 관련 주의사항을 확인할 수 없습니다."
)
_FOOD_KEYWORDS = (
    "음식",
    "식품",
    "식사",
    "자몽",
    "알코올",
    "술",
    "음주",
    "금주",
    "카페인",
    "커피",
    "우유",
    "유제품",
    "요구르트",
    "낫토",
    "청국장",
    "비타민K",
    "녹황색 채소",
    "녹차",
    "홍차",
    "탄산음료",
)


def _extract_food_related_sentences(intrc_text: str) -> str | None:
    """intrcQesitm 원문에서 음식/음주 키워드가 있는 문장만 골라 이어붙인다. 규칙(키워드 매칭)
    기반 1차 구현이며, 오탐(예: 약 이름에 우연히 겹치는 키워드)이 늘어나면 이 함수만 LLM 기반
    추출로 교체할 수 있게 분리해뒀다 — 호출부(`_build_food_interaction_guide_card`)는 그대로다.
    문장이 하나도 없으면 None(약물 간 상호작용만 있고 음식 관련 언급은 없다는 뜻)."""
    sentences = re.split(r"(?<=[.!?])\s+|\n+", intrc_text)
    food_sentences = [s.strip() for s in sentences if s.strip() and any(k in s for k in _FOOD_KEYWORDS)]
    return " ".join(food_sentences) if food_sentences else None


# T-DOC-3: e약은요 intrcQesitm 자유 텍스트 필터링은 약물-약물 상호작용과 음식 상호작용이 섞여있어
# 정확도에 한계가 있다. 공공데이터포털에는 음식-약물 상호작용 전담 API/데이터셋이 없어(식약처 DUR
# API 9개 카테고리에도 음식 카테고리가 없음을 확인함), 식약처가 직접 발간한 PDF 가이드북("약과
# 음식 상호작용을 피하는 복약안내서")을 파싱해 만든 성분 단위 참조 테이블을 우선 사용하고, 매칭되는
# 성분이 없으면(주로 상표명) 기존 e약은요 키워드 필터로 폴백한다.
# 참조 테이블은 MySQL(`food_drug_categories` 등, 2026-07-16 SQLite에서 이전)에서 앱 기동 시
# 1회 읽어 캐싱한다 — 상세: 저장소 docstring, `docs/decision_log/2026-07-16-food-drug-interaction-mysql-migration.md`.
_FOOD_DRUG_REFERENCE_SOURCE_NOTE = "(출처: 식약처 식품의약품안전평가원 「약과 음식 상호작용을 피하는 복약안내서」)"

_food_drug_interaction_repository = FoodDrugInteractionRepository()


async def refresh_food_drug_interaction_cache(session: AsyncSession) -> None:
    """앱 기동 시 1회 호출해 MySQL 참조 테이블을 프로세스 메모리 캐시로 읽어들인다."""
    await _food_drug_interaction_repository.refresh(session)


def _match_food_drug_reference(medication_name: str) -> dict | None:
    """품목명에 참조 테이블의 성분명(한글 또는 영문)이 부분 문자열로 포함되어 있으면 매칭한다.
    국내 일반의약품은 품목명에 성분명이 그대로 들어가는 경우가 흔하다(예: "암로디핀베실산염정5mg").
    상표명(예: "타이레놀")은 매칭되지 않고 기존 e약은요 폴백으로 넘어간다."""
    lowered_name = medication_name.lower()
    for entry in _food_drug_interaction_repository.load_categories():
        if not entry.get("food_interaction") and not entry.get("alcohol_interaction"):
            continue
        for ingredient in entry["ingredients"]:
            name_ko = ingredient.get("name_ko") or ""
            name_en = (ingredient.get("name_en") or "").lower()
            if (name_ko and name_ko in medication_name) or (name_en and name_en in lowered_name):
                return entry
    return None


def _format_food_drug_reference_content(entry: dict) -> str:
    parts = []
    if entry.get("food_interaction"):
        parts.append(f"[음식] {entry['food_interaction']}")
    if entry.get("alcohol_interaction"):
        parts.append(f"[알코올] {entry['alcohol_interaction']}")
    parts.append(_FOOD_DRUG_REFERENCE_SOURCE_NOTE)
    return "\n\n".join(parts)


def _food_items_from_reference(entry: dict) -> list[FoodItem]:
    """`entry["food_items"]`는 `build_food_drug_interaction_db.py`가 빌드 시점에
    `food_item_extraction.extract_food_items()`로 미리 계산해 DB에 저장해둔 결과다(요청마다
    다시 계산하지 않음). `polarity`("avoid"/"recommend")도 그대로 넘긴다 — 예를 들어 NSAIDs+우유는
    "피하라"가 아니라 "함께 먹으면 좋다"는 권장이라 다르게 표시해야 한다."""
    return [
        FoodItem(name=item["name"], detail=item["detail"], polarity=item.get("polarity", "avoid"))
        for item in entry.get("food_items", [])
    ]


# (T-DOC-4) 음식 상호작용 카드를 "이유 줄글"이 아니라 "음식명 칩 + 클릭 상세보기"로 보여주기 위해,
# 원문에서 구체적 음식/음료 명사를 찾아 문장 단위로 묶는다. e약은요 폴백 경로는 매 요청 원문이
# 새로 오므로 여기서 실행 시점에 추출한다. 식약처 참조 테이블 쪽은 정적 데이터라
# `app/scripts/build_food_drug_interaction_db.py`가 미리 계산해 DB(`food_drug_food_items`)에
# 저장해두고, `_match_food_drug_reference`가 그 결과를 그대로 읽어온다(아래
# `_build_food_interaction_guide_card` 참고) — 추출 로직 자체는 `food_item_extraction.py`로 분리해
# 두 경로가 공유한다. `_extract_food_items`는 기존 테스트(`test_medication_service_food_interaction.py`)
# 호출부 호환을 위해 남겨둔 별칭이다.
_extract_food_items = extract_food_items


class OcrField(NamedTuple):
    """CLOVA OCR General API `fields[]` 응답 원소 하나. `confidence`는 `inferConfidence`(0~1)."""

    text: str
    confidence: float


def _compute_match_rate(confidence: float, *, is_auto_created: bool) -> float:
    """(T-MED-6) OCR confidence를 실제 match_rate로 변환한다.

    마스터 DB에 없어 즉석 생성된(AUTO_ 더미) 약품은 OCR이 아무리 확신해도 검증되지 않은
    신규 등록이라는 리스크가 남으므로 상한을 둬 사용자 확인을 유도한다."""
    if is_auto_created:
        return min(confidence, _AUTO_CREATED_MATCH_RATE_CAP)
    return confidence


def _parse_dosage_fields(raw_text: str) -> dict[str, str | list[str] | None]:
    """(T-MED-13) OCR 원문에서 dosage/duration/times/instruction을 실제로 파싱한다.
    패턴에 맞는 텍스트를 찾지 못하면, 확인되지 않은 값을 인식된 것처럼 보여주지 않도록
    하드코딩된 대체값 대신 None을 반환한다."""
    dosage_match = _DOSAGE_COUNT_PATTERN.search(raw_text)
    dosage = f"{dosage_match.group(1)}{dosage_match.group(2)}" if dosage_match else None

    duration_match = _DURATION_PATTERN.search(raw_text)
    duration = f"{duration_match.group(1)}일" if duration_match else None

    time_matches = [f"{hour}:{minute}" for hour, minute in _TIME_PATTERN.findall(raw_text)]
    times = time_matches or None

    instruction_match = _INSTRUCTION_PATTERN.search(raw_text)
    instruction = instruction_match.group(0).strip() if instruction_match else None

    return {"dosage": dosage, "times": times, "duration": duration, "instruction": instruction}


def _dummy_dosage_fields() -> dict[str, str | list[str] | None]:
    return {
        "dosage": _DUMMY_DOSAGE,
        "times": _DUMMY_TIMES,
        "duration": _DUMMY_DURATION,
        "instruction": _DUMMY_INSTRUCTION,
    }


def _extract_item_seq(standard_code: str | None) -> str | None:
    """공공데이터 API(`medication_open_api_client.fetch_medication_master_data`)가 돌려주는
    `standard_code`(`PDP_{item_seq}` 형식)에서 item_seq만 뽑아낸다."""
    if not standard_code or not standard_code.startswith("PDP_"):
        return None
    item_seq = standard_code.removeprefix("PDP_")
    return item_seq or None


_TRAILING_DOSAGE_PATTERN = re.compile(r"(?P<lead>\s*)(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>mg|g|ml)\s*$", re.IGNORECASE)

# 공공데이터 API/MySQL의 정식 품목명은 'mg'가 아니라 '밀리그램'/'밀리그람' 등 한글 단위 표기를
# 쓰는 경우가 많다 - 같은 단어인데도 소스 테이블마다 표기가 다르다(예: item_ingredient_map은
# '밀리그램', dur_prod_master_list/drugs_data 품목명은 '밀리그람'을 쓴다 - 둘 다 실제 값으로
# 확인됨). 접미사를 그냥 떼는 것보다, 두 표기를 모두 후보로 만들어 순서대로 재시도하면 용량
# 정보를 잃지 않고 그 함량의 품목만 정확히 찾을 수 있다(예: "아스피린정100mg" ->
# ["아스피린정100밀리그램", "아스피린정100밀리그람"]).
_ENGLISH_UNIT_TO_KOREAN_VARIANTS: dict[str, list[str]] = {
    "mg": ["밀리그램", "밀리그람"],
    "g": ["그램", "그람"],
    "ml": ["밀리리터"],
}


def _translate_trailing_dosage_to_korean(name: str) -> list[str]:
    """이름 끝의 'NNmg' 형태 접미사를 DB 표기와 같은 한글 단위('NN밀리그램'/'NN밀리그람')로
    바꾼 재시도용 이름 후보들을 반환한다. 접미사가 없으면 빈 리스트."""
    match = _TRAILING_DOSAGE_PATTERN.search(name)
    if not match:
        return []
    variants = _ENGLISH_UNIT_TO_KOREAN_VARIANTS[match["unit"].lower()]
    candidates = [
        _TRAILING_DOSAGE_PATTERN.sub(f"{match['lead']}{match['amount']}{korean_unit}", name) for korean_unit in variants
    ]
    return [candidate for candidate in candidates if candidate != name]


def _strip_trailing_dosage(name: str) -> str | None:
    """한글 단위로 바꿔도(`_translate_trailing_dosage_to_korean`) 띄어쓰기/표기 차이로 여전히
    매칭이 안 될 수 있어, 최후 수단으로 'NNmg' 접미사 자체를 뗀 이름도 시도할 수 있게 한다.
    접미사가 없으면 None."""
    stripped = _TRAILING_DOSAGE_PATTERN.sub("", name).strip()
    return stripped if stripped and stripped != name else None


async def _find_interaction_warnings(item_seqs: set[str], names: dict[str, str]) -> list[InteractionWarning]:
    """(T-MED-16) 스케줄이 이제 item_seq를 직접 들고 있어(`_extract_item_seq`로 뽑아내던 과거의
    간접 경로가 불필요해짐), item_seq끼리 바로 병용금기를 대조한다."""
    warnings: list[InteractionWarning] = []
    seen_pairs: set[frozenset[str]] = set()

    for item_seq in item_seqs:
        try:
            dur_items = await medication_open_api_client.fetch_dur_item_info(item_seq=item_seq)
        except (httpx.HTTPError, medication_open_api_client.PublicDataApiError):
            # 공공데이터 API가 타임아웃/오류로 응답하지 않아도 그 약만 건너뛰고 나머지는 계속 확인한다.
            continue
        for dur in dur_items:
            mixture_seq = dur.get("MIXTURE_ITEM_SEQ")
            if not mixture_seq or mixture_seq not in item_seqs or mixture_seq == item_seq:
                continue

            pair_key = frozenset({item_seq, mixture_seq})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            warnings.append(
                InteractionWarning(
                    drug_a_name=names.get(item_seq, item_seq),
                    drug_b_name=names.get(mixture_seq, mixture_seq),
                    description=dur.get("PROHBT_CONTENT") or "병용금기 성분 조합으로 확인되었습니다.",
                )
            )

    return warnings


def _is_annotation_line(stripped: str) -> bool:
    """ "(Buprenorphine 10mg)"처럼 괄호로 감싼 성분/일반명 표기, "[한국먼디파마]"처럼
    대괄호로 감싼 제조사명 표기는 브랜드 약품명이 아니므로 후보(퍼지 매칭 포함)에서 제외한다."""
    return stripped.startswith("(") or stripped.endswith(")") or (stripped.startswith("[") and stripped.endswith("]"))


def _is_label_slash_without_digit(stripped: str) -> bool:
    return "/" in stripped and not any(ch.isdigit() for ch in stripped)


def _is_bare_dosage_line(stripped: str) -> bool:
    """(#128) "알마게이트 500mg"처럼 제형 접미사 없이 성분명+용량만 있는 줄은, 그 위 브랜드명
    카드가 이미 별도 OCR 필드로 잡히므로 여기서 또 약품 후보로 잡히면 같은 약이 브랜드명/성분명
    이름으로 중복 등록된다. 제형 접미사가 있으면(예: "노스판패취10ug/h") 오탈자 구제 대상으로
    계속 남겨야 하므로, 접미사가 없고 용량 패턴만 있는 경우에만 제외한다."""
    return bool(_DOSAGE_PATTERN.search(stripped)) and not _DRUG_FORM_SUFFIX_PATTERN.search(stripped)


# 화면에는 정/캡슐 같은 제품명만 노출하고 성분명은 노출하지 않기로 했다 - 복합제 처방전은
# "*에보글립틴타르타르산염 6.869mg", "*아토르바스타틴칼슘삼수화물 10.8", "*로베글리타존황산염
# 0.5mg"처럼 화학적 염/수화물 표기로 끝나는 성분명 줄을 "*" 불릿과 함께 나열한다. 이런 줄은
# "산염"/"수화물"로 끝나는 화학명 특유의 패턴이 있어, 마스터 DB 매칭 실패를 이유로 대충 필터링
# 못 하는 일반 약품명(테스트에서 흔히 쓰는 "낫모르는약100mg"류 플레이스홀더 등)과 구분할 수 있다.
_INGREDIENT_SALT_SUFFIX_PATTERN = re.compile(r"(산염|수화물)(?![가-힣])")


def _is_ingredient_salt_name(stripped: str) -> bool:
    return bool(_INGREDIENT_SALT_SUFFIX_PATTERN.search(stripped)) and not _DRUG_FORM_SUFFIX_PATTERN.search(stripped)


def _looks_like_drug_name(word: str) -> bool:
    stripped = word.lstrip("*").strip()
    if len(stripped) < _MIN_DRUG_NAME_LEN:
        return False
    if _is_annotation_line(stripped):
        return False
    if _INSTITUTION_SUFFIX_PATTERN.search(stripped):
        return False
    if _is_label_slash_without_digit(stripped):
        return False
    if not _KOREAN_TOKEN_PATTERN.search(stripped):
        return False
    # "*"가 붙어 있어도 화학적 염/수화물 이름(성분명)이면 후보에서 제외한다 - 그렇지 않으면
    # 복합제 처방전의 성분 breakdown 줄이 "*" 조건 하나만으로 제형 접미사 검사를 건너뛰어,
    # 화면에 성분명이 그대로 노출된다.
    if _is_ingredient_salt_name(stripped):
        return False
    # (#OCR-LLM-2) "*전액본인부담금이란"처럼 영수증/문서 설명 문구가 "*" 불릿과 함께 오인식되면,
    # 제형 접미사가 없어도 "*" 조건 하나만으로 통과해버려 매번 새 AUTO_ 더미로 재등록됐다. 조사/
    # 설명형 어미로 끝나는(완결되지 않은 문장 조각인) 텍스트는 "*"가 붙어 있어도 약품명일 수 없다.
    if _TRAILING_PARTICLE_PATTERN.search(stripped):
        return False
    return word.strip().startswith("*") or bool(_DRUG_FORM_SUFFIX_PATTERN.search(stripped))


def _dedupe_drug_names(names: set[str]) -> list[str]:
    """짧게 잘린 OCR 조각(예: '레마이드정')이 온전한 이름('레마이드정100mg')의 부분 문자열이면
    짧은 쪽을 버리고, 온전한 형태만 후보로 남긴다."""
    ordered = sorted(names, key=len, reverse=True)
    kept: list[str] = []
    for name in ordered:
        if not any(name != k and name in k for k in kept):
            kept.append(name)
    return kept


async def _resolve_unmatched_name(name: str) -> tuple[str, bool]:
    """마스터 DB(`dur_prod_master_list`)에 없는 약품명에 대해 Tier 3(공공 API)로 품목기준코드를
    조회 → 실패 시 AUTO_ 더미 코드 생성 순으로 item_seq를 확보한다(T-MED-4/T-MED-1: 등록 자체가
    막히지 않아야 한다). 반환값: (item_seq 또는 AUTO_ 더미 코드, 더미 생성 여부)."""
    try:
        fields = await medication_open_api_client.fetch_medication_master_data(name)
    except (httpx.HTTPError, medication_open_api_client.PublicDataApiError):
        fields = None

    item_seq = _extract_item_seq(fields.get("standard_code")) if fields else None
    if item_seq:
        return item_seq, False
    return f"AUTO_{uuid.uuid4().hex[:10].upper()}", True


async def _resolve_manual_registration_medication(db_session: AsyncSession, name: str) -> tuple[MatchedDrug, bool]:
    """수동/빠른 등록에서 마스터 DB에 정확히 일치하는 약이 없을 때, OCR 등록 경로
    (`_resolve_or_create_drug_like_names`)와 동일하게 마스터 DB → Tier3 공공 API → AUTO_ 더미
    순으로 확인한다. 반환값: (매칭/생성된 약, AUTO_ 더미 생성 여부)."""
    dur_repo = DurDrugRepository()
    tier1_results = await dur_repo.search_item_names(db_session, name, 5)
    tier1_item_seq = next((seq for seq, iname in tier1_results if iname == name), None)
    if tier1_item_seq:
        return MatchedDrug(item_seq=tier1_item_seq, item_name=name), False

    item_seq, is_auto_dummy = await _resolve_unmatched_name(name)
    return MatchedDrug(item_seq=item_seq, item_name=name), is_auto_dummy


async def _resolve_or_create_drug_like_names(
    db_session: AsyncSession, dur_repo: DurDrugRepository, ocr_fields: list[OcrField], seen_ids: set[str]
) -> tuple[list[MatchedDrug], set[str], dict[str, float]]:
    """마스터 DB에 없는 약이어도, OCR 텍스트가 약품명 형태(용량단위 또는 "*" 불릿 표시)로
    보이면 등록이 막히지 않도록 AUTO_ 더미 코드를 즉석에서 만들어 후보로 포함시킨다.
    "*"는 정규화 과정에서 제거하고, 잘려서 중복된 짧은 조각은 dedupe로 걸러낸다."""
    resolved: list[MatchedDrug] = []
    auto_created_ids: set[str] = set()
    confidences: dict[str, float] = {}

    name_confidence: dict[str, float] = {}
    for field in ocr_fields:
        if not _looks_like_drug_name(field.text):
            continue
        name = field.text.lstrip("*").strip()
        name_confidence[name] = max(name_confidence.get(name, 0.0), field.confidence)

    for name in _dedupe_drug_names(set(name_confidence)):
        confidence = name_confidence[name]
        tier1_results = await dur_repo.search_item_names(db_session, name, 5)
        exact_item_seq = next((seq for seq, iname in tier1_results if iname == name), None)
        if exact_item_seq:
            confidences[exact_item_seq] = max(confidences.get(exact_item_seq, 0.0), confidence)
            if exact_item_seq not in seen_ids:
                seen_ids.add(exact_item_seq)
                resolved.append(MatchedDrug(item_seq=exact_item_seq, item_name=name))
            continue

        item_seq, is_auto_dummy = await _resolve_unmatched_name(name)
        seen_ids.add(item_seq)
        if is_auto_dummy:
            auto_created_ids.add(item_seq)
        resolved.append(MatchedDrug(item_seq=item_seq, item_name=name))
        confidences[item_seq] = confidence

    return resolved, auto_created_ids, confidences


async def _fuzzy_match_unrecognized_fields(
    db_session: AsyncSession, dur_repo: DurDrugRepository, ocr_fields: list[OcrField], seen_ids: set[str]
) -> tuple[list[MatchedDrug], dict[str, float]]:
    """(#106) `_looks_like_drug_name`이 걸러낸(=용량/불릿/제형 접미사 조건을 하나도 못 만족한)
    텍스트 중, 한글 부분만 떼어 마스터 DB 약품명(마찬가지로 한글만 남긴 것)과 편집거리
    유사도를 비교한다. CLOVA가 글자 하나를 잘못 읽은 경우(예: "패취"→"매취")를 구제하는
    용도라, 기존 마스터 DB에 있는 것과 확실히 비슷할 때만(임계값 이상) 인정하고 새 레코드를
    만들지는 않는다 — 애매한 텍스트로 엉뚱한 약을 만들어내는 위험을 피하기 위함이다."""
    matched: list[MatchedDrug] = []
    confidences: dict[str, float] = {}
    for field in ocr_fields:
        if _looks_like_drug_name(field.text):
            continue  # 이미 기존 경로에서 처리 대상이 됨
        stripped = field.text.lstrip("*").strip()
        if _is_annotation_line(stripped):
            continue  # 성분/제조사명 표기 줄은 브랜드 약품명이 아니므로 퍼지 매칭도 제외
        if _is_bare_dosage_line(stripped):
            continue  # (#128) 제형 접미사 없는 성분명+용량 줄은 브랜드 카드 아래 붙는 설명이지 별도 약이 아니므로 제외
        if _INSTITUTION_SUFFIX_PATTERN.search(stripped):
            continue  # 약국/병원명은 브랜드 약품명이 아니므로 퍼지 매칭도 제외
        if _is_label_slash_without_digit(stripped):
            continue  # "성분/함량"류 문서 라벨이 오인식된 경우 — 브랜드 약품명이 아니므로 제외
        if _TRAILING_PARTICLE_PATTERN.search(stripped):
            continue  # 조사로 끝나는 문장 중간 단어는 완결된 약품명이 아니므로 퍼지 매칭도 제외
        query = _korean_only(field.text)
        if len(query) < _FUZZY_MATCH_MIN_KOREAN_LEN:
            continue

        matched_drug = await _fuzzy_match_one_field(db_session, dur_repo, query, seen_ids)
        if matched_drug is None:
            continue
        seen_ids.add(matched_drug.item_seq)
        matched.append(matched_drug)
        confidences[matched_drug.item_seq] = max(confidences.get(matched_drug.item_seq, 0.0), field.confidence)

    return matched, confidences


async def _fuzzy_match_one_field(
    db_session: AsyncSession, dur_repo: DurDrugRepository, query: str, seen_ids: set[str]
) -> MatchedDrug | None:
    """OCR 텍스트(한글만 남긴 것) 하나에 대해 마스터 DB 접두어 후보 안에서 가장 비슷한 것을 찾는다."""
    tier1_candidates = await dur_repo.search_item_names_by_prefix(
        db_session, query[:_FUZZY_TIER1_PREFIX_LEN], _FUZZY_TIER1_CANDIDATE_LIMIT
    )
    best_item_seq = _best_fuzzy_candidate(query, tier1_candidates, _FUZZY_MATCH_THRESHOLD)
    if best_item_seq is None or best_item_seq in seen_ids:
        return None
    item_name = next(name for seq, name in tier1_candidates if seq == best_item_seq)
    return MatchedDrug(item_seq=best_item_seq, item_name=item_name)


_LLM_DRUG_NAME_SYSTEM_PROMPT = (
    "다음은 처방전/약봉투를 OCR로 인식한 원문이다. 처방전에서 약품명은 보통 '정/캡슐/시럽/패취/"
    "점안액/디스커스/연고/겔/주' 같은 제형 접미사로 끝나고 그 뒤에 대괄호로 감싼 제조사명이 붙는 "
    "형식이다(예: '세레타이드500디스커스 [글락소스미스클라인]'). 이 패턴에 해당하는 텍스트는 "
    "OCR 오탈자로 글자가 깨져 있어도(예: '노스판매취10ug/h' → 실제로는 '노스판패취') 절대 생략하지 "
    "말고 반드시 약품명 후보로 포함하며, 실제 한글 의약품명 표기에 최대한 가깝게 교정해서 답하라 — "
    "개별 항목의 확신이 낮다는 이유만으로 빼지 않는다. 용량 단위는 mg/g/ml뿐 아니라 mcg, ug, IU, "
    "%, ug/h(패취류) 등 다양할 수 있다. 환자 정보, 약국/병원명, 복약 안내 문구, 성분명 단독 언급"
    "(제형 접미사가 없는 경우), 제조사명은 약품명이 아니므로 제외한다. 답에는 대괄호로 감싼 "
    "제조사명을 포함하지 말고 약품명(용량 포함)만 남긴다. 원문 전체가 약품명과 무관한 잡음일 "
    "때만 빈 목록을 반환한다."
)


class _LlmDrugNameCandidates(BaseModel):
    drug_names: list[str]


async def _llm_extract_drug_names(ocr_raw_text: str) -> list[str]:
    """(#OCR-LLM) 정규식(`_looks_like_drug_name`)/퍼지 매칭 결과와 무관하게 매번 호출해, 그
    규칙들이 놓쳤을 약을 추가로 구제하는 보완 경로. OCR 원문을 그대로 LLM에 넘겨 약품명 후보를
    뽑아낸다 — ai_worker가 꺼져있거나(AIWorkerUnavailableError) 요청이 잘못됐거나
    (AIWorkerInvalidRequestError) 응답 형식이 어긋나면(AIWorkerProcessingError) 빈 목록을
    반환해 정규식 매칭 결과만으로 계속 진행하게 한다 — 등록 자체가 막히지 않는다는 T-MED-1
    원칙을 그대로 유지."""
    if not ocr_raw_text.strip():
        return []
    gateway = AIWorkerGateway()
    try:
        result = await gateway.call_structured(
            system_prompt=_LLM_DRUG_NAME_SYSTEM_PROMPT,
            user_input=ocr_raw_text,
            schema=_LlmDrugNameCandidates,
        )
    except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
        logger.warning("LLM 약품명 추출 실패, 기존 폴백으로 넘어갑니다: %s", e)
        return []
    return [name.strip() for name in cast(_LlmDrugNameCandidates, result).drug_names if name.strip()]


def _is_plausible_llm_drug_name(name: str) -> bool:
    """(#OCR-LLM) LLM 제안 경로는 정규식 경로(`_looks_like_drug_name`)를 거치지 않으므로,
    프롬프트가 제외를 지시한 환자 정보/영수증 문구/숫자 코드(예: "전액본인부담금이란",
    "201501025")가 그대로 섞여 들어와도 막을 방법이 없었다. 실제 약품명이라면 제형 접미사
    (정/캡슐/...) 또는 용량 표기(mg/g/ml) 중 최소 하나는 있어야 하므로, 정규식 경로와 동일한
    최소 형태 조건으로 걸러낸다."""
    if not _KOREAN_TOKEN_PATTERN.search(name):
        return False
    if _is_annotation_line(name):
        return False
    if _INSTITUTION_SUFFIX_PATTERN.search(name):
        return False
    if _is_label_slash_without_digit(name):
        return False
    return bool(_DRUG_FORM_SUFFIX_PATTERN.search(name) or _DOSAGE_PATTERN.search(name))


async def _resolve_llm_suggested_names(
    db_session: AsyncSession,
    dur_repo: DurDrugRepository,
    names: list[str],
    seen_ids: set[str],
    seen_names: set[str],
) -> tuple[list[MatchedDrug], set[str]]:
    """LLM이 제안한 약품명 후보를 마스터 DB 정확일치 → Tier3(공공 API)/AUTO_ 더미 순으로 해석한다.
    OCR confidence 근거가 없는 경로라 호출부가 낮은 match_rate(`_NO_OCR_EVIDENCE_MATCH_RATE`)를
    매기도록 confidence는 채우지 않는다.

    `seen_names`(정규식/퍼지 경로가 이미 후보로 만든 약품명 문자열)에 이미 있는 이름은 건너뛴다 —
    마스터 DB에 없는 약은 Tier3/AUTO_ 더미 경로에서 매번 새 item_seq(공공 API 결과 또는 랜덤 UUID)를
    받기 때문에, seen_ids(item_seq 기준)만으로는 정규식 경로가 이미 만든 것과 같은 약품명을 LLM
    경로가 또 별도 항목으로 중복 추가하는 걸 막지 못한다."""
    resolved: list[MatchedDrug] = []
    auto_created_ids: set[str] = set()

    for name in _dedupe_drug_names(set(names)):
        if not _is_plausible_llm_drug_name(name):
            continue
        if name in seen_names:
            continue

        tier1_results = await dur_repo.search_item_names(db_session, name, 5)
        exact_item_seq = next((seq for seq, iname in tier1_results if iname == name), None)
        if exact_item_seq:
            if exact_item_seq not in seen_ids:
                seen_ids.add(exact_item_seq)
                resolved.append(MatchedDrug(item_seq=exact_item_seq, item_name=name))
            continue

        item_seq, is_auto_dummy = await _resolve_unmatched_name(name)
        seen_ids.add(item_seq)
        if is_auto_dummy:
            auto_created_ids.add(item_seq)
        resolved.append(MatchedDrug(item_seq=item_seq, item_name=name))

    return resolved, auto_created_ids


async def _match_or_create_medications(
    db_session: AsyncSession, dur_repo: DurDrugRepository, ocr_fields: list[OcrField]
) -> tuple[list[MatchedDrug], set[str], dict[str, float]]:
    """OCR 텍스트에서 약품명으로 보이는 조각을 마스터 DB와 매칭하고, 없으면 새로 생성한다.
    반환값: (매칭/생성된 약 목록, 이번에 새로 생성된 약의 item_seq 집합, item_seq별 OCR confidence)"""
    matched_drugs: list[MatchedDrug] = []
    auto_created_ids: set[str] = set()
    seen_ids: set[str] = set()
    match_confidence: dict[str, float] = {}

    # (#OCR-LLM) LLM 보완 경로(ai_worker 네트워크 호출)는 seen_ids에 의존하지 않고 OCR 원문만
    # 있으면 되므로, 아래 DB 매칭 패스들과 동시에 시작해 지연시간을 겹치게 한다 — LLM 호출을
    # 매번 순차적으로 맨 마지막에 기다리면 등록 전체 시간에 그대로 더해져 느려진다.
    llm_task: asyncio.Task[list[str]] | None = None
    if ocr_fields:
        ocr_raw_text = " ".join(f.text for f in ocr_fields)
        llm_task = asyncio.create_task(_llm_extract_drug_names(ocr_raw_text))

        resolved, auto_created_ids, resolved_confidence = await _resolve_or_create_drug_like_names(
            db_session, dur_repo, ocr_fields, seen_ids
        )
        matched_drugs.extend(resolved)
        match_confidence.update(resolved_confidence)

        fuzzy_matched, fuzzy_confidence = await _fuzzy_match_unrecognized_fields(
            db_session, dur_repo, ocr_fields, seen_ids
        )
        matched_drugs.extend(fuzzy_matched)
        match_confidence.update(fuzzy_confidence)

    # 정규식/퍼지 매칭 결과가 있어도, 그 규칙들이 놓쳤을 수 있는 약을 추가로 구제하기 위해 매번
    # LLM으로 한 번 더 보완한다. 마스터 DB에 있는 약은 `seen_ids`(item_seq)로 걸러지고, 마스터
    # DB에 없는 약은 이름이 같아도 매번 새 item_seq(Tier3 API/AUTO_ 더미)를 받으므로 `seen_names`
    # (약품명 문자열)로 따로 걸러야 정규식 경로가 이미 만든 후보를 LLM이 또 중복 추가하지 않는다.
    if llm_task is not None:
        llm_names = await llm_task
        if llm_names:
            seen_names = {drug.item_name for drug in matched_drugs}
            llm_matched, llm_auto_created_ids = await _resolve_llm_suggested_names(
                db_session, dur_repo, llm_names, seen_ids, seen_names
            )
            matched_drugs.extend(llm_matched)
            auto_created_ids |= llm_auto_created_ids
            for drug in llm_matched:
                match_confidence[drug.item_seq] = _NO_OCR_EVIDENCE_MATCH_RATE

    # 그래도 후보가 하나도 없으면(약품명으로 보이는 텍스트조차 없었던 경우)
    # 마스터 DB 상위 몇 개를 참고용으로 보여준다 — 이 경우엔 수동 검색으로의 전환을 기대한다.
    if not matched_drugs:
        top_results = await dur_repo.search_item_names(db_session, "", 3)
        matched_drugs = [MatchedDrug(item_seq=seq, item_name=name) for seq, name in top_results]

    return matched_drugs, auto_created_ids, match_confidence


_CLOVA_SUPPORTED_FORMATS = {"jpg", "jpeg", "png", "pdf"}


def _convert_to_clova_supported_format(file_bytes: bytes) -> tuple[bytes, str]:
    """webp 등 CLOVA가 지원하지 않는 포맷을 png로 변환한다. 예전에는 지원 목록에 없는
    확장자를 실제 바이트 변환 없이 그냥 "jpg"라고만 표시해 보냈는데, CLOVA가 그 바이트를
    jpg로 디코딩하지 못해 400(Request invalid)을 반환하고 조용히 더미 텍스트로 폴백되는
    문제가 있었다(webp 업로드 시 실제 사진 내용과 무관하게 항상 같은 더미 결과가 나옴).
    변환 자체가 실패하면(손상된 파일 등) 원본 바이트를 그대로 두고 호출부에서 CLOVA의
    거부 응답으로 실패를 감지하게 한다."""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "png"
    except Exception as exc:
        logger.warning("이미지 포맷 변환 실패, 원본 바이트를 그대로 전송합니다: %s", exc)
        return file_bytes, "jpg"


def _build_clova_ocr_request(file_bytes: bytes, file_name: str) -> tuple[dict, dict]:
    file_format = file_name.split(".")[-1].lower()
    if file_format not in _CLOVA_SUPPORTED_FORMATS:
        file_bytes, file_format = _convert_to_clova_supported_format(file_bytes)

    base64_data = base64.b64encode(file_bytes).decode("utf-8")
    payload = {
        "images": [{"format": file_format, "name": "medication_doc", "data": base64_data}],
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "version": "V2",
    }
    headers = {"X-OCR-SECRET": CLOVA_OCR_SECRET_KEY, "Content-Type": "application/json"}
    return payload, headers


def _parse_clova_ocr_response(response: httpx.Response) -> list[OcrField]:
    """2xx 응답의 JSON 구조가 기대와 다르면(필드 누락/타입 불일치) 재시도해도 결과가 같으므로
    빈 리스트로 처리하되, 어떤 응답이 문제였는지 알 수 있게 로그를 남긴다.

    (T-MED-6) `inferText`뿐 아니라 `inferConfidence`도 함께 뽑아, 매칭률 계산에 실제 OCR
    신뢰도를 반영할 수 있게 한다. confidence 필드가 없거나 숫자가 아니면 0.0으로 취급."""
    try:
        res_json = response.json()
        images = res_json.get("images", [])
        if not images:
            return []
        fields = images[0].get("fields", [])
        result = []
        for field in fields:
            text = field.get("inferText", "")
            if not text:
                continue
            try:
                confidence = float(field.get("inferConfidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            result.append(OcrField(text=text, confidence=confidence))
        return result
    except (ValueError, AttributeError, TypeError) as exc:
        logger.error("CLOVA OCR 응답 파싱 실패 (status=%s): %s", response.status_code, exc)
        return []


async def _call_clova_ocr(file_bytes: bytes, file_name: str) -> list[OcrField]:
    """CLOVA OCR을 호출해 인식된 텍스트 조각 목록을 반환한다. 호출 실패/빈 응답이면 빈 리스트.
    호출 전 `_clova_configured()`로 키/URL이 설정됐음을 확인했다는 전제 하에만 호출된다.

    타임아웃/네트워크 오류/5xx는 일시적일 수 있어 짧게 재시도하고, 인증 오류(401/403) 같은
    4xx는 재시도해도 결과가 같으므로 즉시 포기한다. 모든 실패 경로에 로그를 남겨 조용히
    더미 폴백으로 넘어가는 일이 없도록 한다(운영 중 CLOVA 키 만료 등을 감지하기 위함)."""
    assert CLOVA_OCR_SECRET_KEY is not None
    assert CLOVA_OCR_INVOKE_URL is not None
    payload, headers = _build_clova_ocr_request(file_bytes, file_name)

    for attempt in range(1, _CLOVA_OCR_MAX_ATTEMPTS + 1):
        is_last_attempt = attempt == _CLOVA_OCR_MAX_ATTEMPTS
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(CLOVA_OCR_INVOKE_URL, json=payload, headers=headers, timeout=10.0)
        except httpx.TimeoutException as exc:
            logger.warning("CLOVA OCR 호출 타임아웃 (attempt=%d/%d): %s", attempt, _CLOVA_OCR_MAX_ATTEMPTS, exc)
            if is_last_attempt:
                return []
            await asyncio.sleep(_CLOVA_OCR_RETRY_DELAY_SECONDS)
            continue
        except httpx.HTTPError as exc:
            logger.warning("CLOVA OCR 호출 네트워크 오류 (attempt=%d/%d): %s", attempt, _CLOVA_OCR_MAX_ATTEMPTS, exc)
            if is_last_attempt:
                return []
            await asyncio.sleep(_CLOVA_OCR_RETRY_DELAY_SECONDS)
            continue

        if response.status_code == 200:
            return _parse_clova_ocr_response(response)

        if response.status_code >= 500 and not is_last_attempt:
            logger.warning(
                "CLOVA OCR 서버 오류 (status=%d, attempt=%d/%d), 재시도합니다.",
                response.status_code,
                attempt,
                _CLOVA_OCR_MAX_ATTEMPTS,
            )
            await asyncio.sleep(_CLOVA_OCR_RETRY_DELAY_SECONDS)
            continue

        logger.error("CLOVA OCR 호출 실패 (status=%d): %s", response.status_code, response.text[:500])
        return []

    return []


def _clova_configured() -> bool:
    return bool(CLOVA_OCR_SECRET_KEY and CLOVA_OCR_INVOKE_URL and not CLOVA_OCR_SECRET_KEY.startswith("your_"))


def _dummy_ocr_fields() -> list[OcrField]:
    return [OcrField(text=t, confidence=_DUMMY_OCR_CONFIDENCE) for t in DUMMY_OCR_RAW_TEXT]


async def _resolve_ocr_fields(file_bytes: bytes, file_name: str, dummy_mode: bool) -> tuple[list[OcrField], bool]:
    """OCR 인식 필드(텍스트+confidence) 목록과 "더미 폴백이 사용됐는지"를 반환한다(T-MED-3).

    dummy_mode가 명시적으로 요청된 경우에만 결정적인 더미 텍스트로 폴백한다. CLOVA 미설정/호출
    실패/빈 응답은 실제 인식이 실패한 것이므로, 더미 텍스트를 실제 인식 결과인 것처럼 섞어 넣지
    않고 빈 필드 목록을 반환한다 — 호출부에서 candidates가 비어 status="failed"로 처리된다."""
    if dummy_mode:
        return _dummy_ocr_fields(), True

    if not _clova_configured():
        logger.warning("CLOVA OCR 키/URL이 설정되지 않아 인식에 실패했습니다.")
        return [], False

    ocr_fields = await _call_clova_ocr(file_bytes, file_name)
    if not ocr_fields:
        logger.warning("CLOVA OCR 호출 결과가 비어 있습니다.")
        return [], False
    return ocr_fields, False


async def _fetch_drug_summary_with_fallback(medication_name: str) -> list[dict]:
    """e약은요 `itemName` 파라미터는 정확/부분 일치라, OCR/사용자 입력의 'NNmg' 접미사가 실제
    품목명(대개 '밀리그램' 등 한글 단위 표기)과 안 맞으면 빈 결과가 흔하다(실 API로 확인 —
    "아스피린정 100mg"는 0건, "아스피린정"은 1건). `_fetch_master_data_with_fallback`과 동일한
    패턴으로 먼저 한글 단위로 바꾼 이름을, 그래도 안 되면 접미사를 뗀 이름으로 한 번 더 시도한다."""
    summaries = await medication_open_api_client.fetch_drug_summary(item_name=medication_name)
    if summaries:
        return summaries

    for translated_name in _translate_trailing_dosage_to_korean(medication_name):
        summaries = await medication_open_api_client.fetch_drug_summary(item_name=translated_name)
        if summaries:
            return summaries

    stripped_name = _strip_trailing_dosage(medication_name)
    if stripped_name:
        return await medication_open_api_client.fetch_drug_summary(item_name=stripped_name)
    return summaries


# (#195) 조회 결과는 약품명이 같으면 항상 같은 카드가 나온다(정적 공공 데이터) — 확정 등록
# 1건마다, 그리고 "음식(13번)" 탭을 열 때마다 등록약 전부에 대해 매번 다시 부르는 게 느린 원인
# 중 하나였다. 프로세스 메모리에 약품명 기준으로 캐싱해 반복 조회를 없앤다. 3단계(느린 실시간
# e약은요 API) 결과만 캐싱한다 — 1,2단계는 MySQL 조회라 이미 충분히 빠르다.
_food_guide_card_cache: dict[str, GuideCard] = {}


async def _fetch_food_intrc_from_local_db(session: AsyncSession, medication_name: str) -> str | None:
    """(T-DOC-5) 2단계: `drugs_data`(MySQL, e약은요 API를 미리 수집해둔 스냅샷, 4,758건)에서
    `intrc_qesitm`을 조회한다. 실시간 API 호출 없이 이미 저장된 범위 안이면 즉시 응답 가능하다.
    실API와 마찬가지로 'NNmg' 접미사가 실제 품목명과 안 맞는 경우가 있어 먼저 한글 단위로 바꾼
    이름을, 그래도 안 되면 접미사를 뗀 이름으로도 재시도한다. 반환값이 None이면 이 약이 스냅샷에
    아예 없다는 뜻 — 그 경우에만 3단계(느린 실시간 API, `_build_food_interaction_guide_card_slow`)
    호출이 필요하다."""
    dur_repo = DurDrugRepository()
    text_value = await dur_repo.find_food_intrc_text(session, medication_name)
    if text_value is None:
        for translated_name in _translate_trailing_dosage_to_korean(medication_name):
            text_value = await dur_repo.find_food_intrc_text(session, translated_name)
            if text_value is not None:
                break
    if text_value is None:
        stripped_name = _strip_trailing_dosage(medication_name)
        if stripped_name:
            text_value = await dur_repo.find_food_intrc_text(session, stripped_name)
    return text_value


async def _build_food_interaction_guide_card_fast(session: AsyncSession, medication_name: str) -> GuideCard | None:
    """(T-DOC-5) 1,2단계(식약처 참조 테이블 → MySQL `drugs_data` 스냅샷)만으로 확인한다 —
    실시간 API를 전혀 호출하지 않으므로 항상 빠르다. 둘 다 매칭되지 않으면(주로 상표명이면서
    e약은요 스냅샷에도 없는 약) None을 반환해, 호출부가 느린 3단계(`_build_food_interaction_guide_card_slow`)로
    넘어가야 함을 알린다."""
    title = f"{medication_name} · {_FOOD_GUIDE_CARD_TITLE}"

    reference_entry = _match_food_drug_reference(medication_name)
    if reference_entry is not None:
        return GuideCard(
            title=title,
            content=_format_food_drug_reference_content(reference_entry),
            severity="caution",
            food_items=_food_items_from_reference(reference_entry) or None,
        )

    raw_interaction_text = await _fetch_food_intrc_from_local_db(session, medication_name)
    if raw_interaction_text is None:
        return None

    food_text = _extract_food_related_sentences(raw_interaction_text) if raw_interaction_text.strip() else None
    if not food_text:
        return GuideCard(title=title, content=_NO_FOOD_INTERACTION_MESSAGE, severity="info")

    return GuideCard(
        title=title, content=food_text, severity="caution", food_items=_extract_food_items(food_text) or None
    )


async def _build_food_interaction_guide_card_slow(medication_name: str) -> GuideCard:
    """(T-DOC-5) 3단계: 실시간 e약은요 API 호출(느림). `_build_food_interaction_guide_card_fast`가
    None을 반환해 1,2단계로는 확인이 안 된 약에 대해서만 호출해야 한다."""
    title = f"{medication_name} · {_FOOD_GUIDE_CARD_TITLE}"

    try:
        summaries = await _fetch_drug_summary_with_fallback(medication_name)
    except (httpx.HTTPError, medication_open_api_client.PublicDataApiError):
        return GuideCard(title=title, content=_FOOD_INFO_UNAVAILABLE_MESSAGE, severity="info")

    if not summaries:
        return GuideCard(title=title, content=_FOOD_INFO_UNAVAILABLE_MESSAGE, severity="info")

    raw_interaction_text = (summaries[0].get("intrcQesitm") or "").strip()
    food_text = _extract_food_related_sentences(raw_interaction_text) if raw_interaction_text else None
    if not food_text:
        return GuideCard(title=title, content=_NO_FOOD_INTERACTION_MESSAGE, severity="info")

    return GuideCard(
        title=title, content=food_text, severity="caution", food_items=_extract_food_items(food_text) or None
    )


async def _build_food_interaction_guide_card_slow_cached(medication_name: str) -> GuideCard:
    cached = _food_guide_card_cache.get(medication_name)
    if cached is not None:
        return cached
    card = await _build_food_interaction_guide_card_slow(medication_name)
    _food_guide_card_cache[medication_name] = card
    return card


async def _build_food_interaction_guide_card(session: AsyncSession, medication_name: str) -> GuideCard:
    """(T-DOC-2) 1,2단계(참조 테이블/MySQL 스냅샷)로 확인되면 그 결과를 바로 반환하고,
    안 되면 3단계(느린 실시간 e약은요 API)까지 이어서 확인한다 — 등록 확정 시점의 1회성
    안내처럼 한 번에 완전한 결과가 필요한 호출부용이다. 등록약이 많아 반복 조회되는
    "음식(13번)" 탭은 이 함수 대신 `_build_food_interaction_guide_card_fast`로 즉시 응답하고
    미확인분만 별도 엔드포인트에서 `_build_food_interaction_guide_card_slow_cached`로 채운다."""
    fast_card = await _build_food_interaction_guide_card_fast(session, medication_name)
    if fast_card is not None:
        return fast_card
    return await _build_food_interaction_guide_card_slow_cached(medication_name)


async def _execute_ocr_logic(
    db_session: AsyncSession,
    job_id: str,
    source_type: str,
    file_bytes: bytes,
    file_name: str,
    dummy_mode: bool = False,
):
    repo = MedicationRepository()
    dur_repo = DurDrugRepository()

    # 1. 상태를 processing으로 변경
    await repo.update_recognition_job(db_session, job_id, "processing")

    # 2. OCR 텍스트 확보 (dummy_mode 명시 요청 또는 실제 OCR 실패 시 결정적 더미로 폴백)
    ocr_fields, used_dummy_fallback = await _resolve_ocr_fields(file_bytes, file_name, dummy_mode)

    # 3. OCR 파싱 결과 분석 & DB 매칭
    candidates = []
    ocr_raw_text = " ".join(f.text for f in ocr_fields)
    dosage_fields = _dummy_dosage_fields() if used_dummy_fallback else _parse_dosage_fields(ocr_raw_text)
    extracted_fields = {
        **dosage_fields,
        "ocr_raw_text": ocr_raw_text,
        "dummy_mode": used_dummy_fallback,
    }

    matched_drugs, auto_created_ids, match_confidence = await _match_or_create_medications(
        db_session, dur_repo, ocr_fields
    )

    for drug in matched_drugs:
        confidence = match_confidence.get(drug.item_seq, _NO_OCR_EVIDENCE_MATCH_RATE)
        match_rate = _compute_match_rate(confidence, is_auto_created=drug.item_seq in auto_created_ids)
        candidates.append(
            {
                "drug_name": drug.item_name,
                "match_rate": match_rate,
                "drug_code": drug.item_seq,
            }
        )

    candidates.sort(key=lambda x: cast(float, x["match_rate"]), reverse=True)

    # 4. 최종 상태 업데이트
    status = "done" if candidates else "failed"
    await repo.update_recognition_job(
        db_session, job_id, status=status, candidates=candidates, extracted_fields=extracted_fields
    )


async def run_ocr_task(
    job_id: str,
    source_type: str,
    file_bytes: bytes,
    file_name: str = "image.jpg",
    dummy_mode: bool = False,
):
    """
    비동기 OCR 및 약품 매칭 백그라운드 태스크.
    요청 스코프 세션은 응답 전송 시 닫히므로, 항상 자체 세션을 새로 열어 사용한다(BE-2).
    dummy_mode=True면 실제 OCR 호출 없이 결정적인 더미 인식 결과를 반환한다(T-MED-3).
    """
    async with AsyncSessionLocal() as db_session:
        await _execute_ocr_logic(db_session, job_id, source_type, file_bytes, file_name, dummy_mode)
        await db_session.commit()


async def _require_item_seq(session: AsyncSession, repo: MedicationRepository, item_seq: str) -> None:
    """(T-MED-16) `medication_schedules.item_seq`는 DB FK가 없으므로, 스케줄을 만들기 전
    앱 레벨에서 마스터 데이터 존재를 확인한다. AUTO_ 더미 코드는 마스터 데이터에 없는 게
    당연하므로(T-MED-1: 등록 자체가 막히지 않아야 한다) 검증을 건너뛴다."""
    if item_seq.startswith("AUTO_"):
        return
    if not await repo.item_seq_exists(session, item_seq):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 약품 정보를 찾을 수 없습니다.")


class MedicationService:
    def __init__(
        self,
        repository: MedicationRepository | None = None,
        dur_drug_repository: DurDrugRepository | None = None,
        side_effect_notification_service: SideEffectNotificationService | None = None,
    ) -> None:
        self._repository = repository or MedicationRepository()
        self._dur_drug_repository = dur_drug_repository or DurDrugRepository()
        self._family_repository = FamilyRepository()  # (가족관리) 대상자 권한검증용
        self._side_effect_notification_service = side_effect_notification_service or SideEffectNotificationService()

    async def create_recognition_job(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        file_bytes: bytes,
        file_name: str,
        background_tasks: BackgroundTasks,
        dummy_mode: bool = False,
    ) -> RecognitionJobCreateResult:
        if source_type not in ["pill_photo", "prescription", "medical_record", "medication_guide"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 source_type 입니다.")

        job_id = str(uuid.uuid4())
        job = MedicationRecognitionJob(
            id=job_id,
            profile_id=profile_id,
            status="pending",
            source_type=source_type,
            candidates=[],
            extracted_fields={},
        )
        await self._repository.create_recognition_job(session, job)

        # 백그라운드 태스크 등록 (요청 세션은 넘기지 않고, 태스크 내부에서 자체 세션을 생성한다)
        background_tasks.add_task(run_ocr_task, job_id, source_type, file_bytes, file_name, dummy_mode=dummy_mode)

        return RecognitionJobCreateResult(job_id=job_id, status="pending")

    async def get_recognition_job(self, session: AsyncSession, job_id: str, profile_id: int) -> RecognitionResult:
        job = await self._repository.get_recognition_job(session, job_id)
        if not job or job.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 작업(Job)을 찾을 수 없습니다.")

        candidates = [
            RecognitionCandidate(drug_name=c["drug_name"], match_rate=c["match_rate"], drug_code=c["drug_code"])
            for c in (job.candidates or [])
        ]

        return RecognitionResult(
            job_id=job.id,
            status=job.status,
            source_type=job.source_type,
            candidates=candidates,
            extracted_fields=job.extracted_fields,
        )

    async def confirm_recognition_job(
        self,
        session: AsyncSession,
        job_id: str,
        profile_id: int,
        selected_candidate_drug_code: str | None,
        confirmed_fields: dict | None,
    ) -> RecognitionConfirmResult:
        job = await self._repository.get_recognition_job(session, job_id)
        if not job or job.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 작업(Job)을 찾을 수 없습니다.")

        # 최종 약물 확정 및 등록 처리 - (T-MED-16) selected_candidate_drug_code는 이제 그 자체가
        # item_seq(또는 AUTO_ 더미 코드)다.
        drug_name: str | None = None
        if selected_candidate_drug_code:
            item_seq = selected_candidate_drug_code
            await _require_item_seq(session, self._repository, item_seq)

            candidate = next((c for c in (job.candidates or []) if c["drug_code"] == item_seq), None)
            drug_name = candidate["drug_name"] if candidate else item_seq
            display_name = drug_name if item_seq.startswith("AUTO_") else None

            # 9~10번: 시간대가 적혀있다면 추출된 시간 사용, 없으면 기본 슬롯 추천
            times = ["09:00", "13:00", "19:00"]
            if confirmed_fields and "times" in confirmed_fields:
                times = confirmed_fields["times"]
            elif job.extracted_fields and job.extracted_fields.get("times"):
                # (T-MED-13) 실제 OCR에서 시간 파싱에 실패하면 extracted_fields["times"]가
                # None일 수 있다 — MedicationSchedule.times는 non-nullable이라 그 경우
                # 기본값(위 3줄)으로 폴백해야 한다.
                times = job.extracted_fields["times"]

            schedule = MedicationSchedule(
                profile_id=profile_id,
                item_seq=item_seq,
                display_name=display_name,
                times=times,
                source_job_id=job_id,
            )
            await self._repository.create_schedule(session, schedule)
            await self._side_effect_notification_service.notify_if_side_effects(session, profile_id, drug_name)

        # 13번: 음식(T-DOC-2) — 등록된 약의 e약은요 상호작용 문항에서 음식/음주 주의사항을 안내한다.
        guide_cards = []
        if drug_name:
            guide_cards.append(await _build_food_interaction_guide_card(session, drug_name))

        return RecognitionConfirmResult(status="confirmed", guide_cards=guide_cards)

    async def list_schedules(self, session: AsyncSession, profile_id: int) -> list[MedicationScheduleResponse]:
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        names = await self._dur_drug_repository.get_names_by_item_seqs(session, {s.item_seq for s in schedules})
        return [
            MedicationScheduleResponse(
                id=s.id,
                item_seq=s.item_seq,
                drug_name=s.display_name or names.get(s.item_seq, s.item_seq),
                times=s.times,
                source_job_id=s.source_job_id,
                hospital_name=s.hospital_name,
            )
            for s in schedules
        ]

    async def update_schedule(
        self, session: AsyncSession, profile_id: int, schedule_id: int, req: MedicationScheduleUpdateRequest
    ) -> MedicationScheduleResponse:
        schedule = await self._repository.get_schedule_by_id(session, schedule_id)
        if not schedule or schedule.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 복약 스케줄을 찾을 수 없습니다.")

        if req.times is not None:
            schedule.times = req.times
        if req.hospital_name is not None:
            schedule.hospital_name = req.hospital_name
        await session.commit()
        await session.refresh(schedule)

        names = await self._dur_drug_repository.get_names_by_item_seqs(session, {schedule.item_seq})
        return MedicationScheduleResponse(
            id=schedule.id,
            item_seq=schedule.item_seq,
            drug_name=schedule.display_name or names.get(schedule.item_seq, schedule.item_seq),
            times=schedule.times,
            source_job_id=schedule.source_job_id,
            hospital_name=schedule.hospital_name,
        )

    async def delete_schedule(self, session: AsyncSession, profile_id: int, schedule_id: int) -> None:
        schedule = await self._repository.get_schedule_by_id(session, schedule_id)
        if not schedule or schedule.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 복약 스케줄을 찾을 수 없습니다.")
        await self._repository.delete_schedule(session, schedule)

    async def create_manual_schedule(
        self, session: AsyncSession, profile_id: int, req: MedicationScheduleCreateRequest
    ) -> MedicationScheduleResponse:
        item_seq = req.drug_code
        await _require_item_seq(session, self._repository, item_seq)
        names = await self._dur_drug_repository.get_names_by_item_seqs(session, {item_seq})
        drug_name = names.get(item_seq, item_seq)

        # (가족관리) target_profile_id가 있으면 "이 약을 실제로 먹을 사람"을 그 프로필로 등록한다.
        # 본인이 아닌 값이면 요청자가 그 프로필의 보호자로 등록되어 있는지 반드시 확인 -
        # 아니면 아무나 남의 이름으로 복약 스케줄을 만들 수 있게 되는 구멍이 생긴다.
        owner_profile_id = req.target_profile_id or profile_id
        if owner_profile_id != profile_id:
            is_guardian = await self._family_repository.is_guardian_of(session, profile_id, owner_profile_id)
            if not is_guardian:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="해당 프로필에 대한 복약 스케줄을 등록할 권한이 없습니다. 더보기 > 가족관리에서 먼저 연결해주세요.",
                )

        schedule = MedicationSchedule(
            profile_id=owner_profile_id, item_seq=item_seq, times=req.times, hospital_name=req.hospital_name
        )
        await self._repository.create_schedule(session, schedule)
        await self._side_effect_notification_service.notify_if_side_effects(session, owner_profile_id, drug_name)

        return MedicationScheduleResponse(
            id=schedule.id,
            item_seq=schedule.item_seq,
            drug_name=drug_name,
            times=schedule.times,
            hospital_name=schedule.hospital_name,
        )

    async def quick_register_medication(
        self,
        session: AsyncSession,
        profile_id: int,
        drug_name: str,
        times: list[str],
        hospital_name: str | None = None,
    ) -> QuickRegisterResult:
        """약품명을 직접 입력해 검색 단계 없이 한 번에 등록한다(T-MED-3).

        - 정확히 하나만 일치하면 즉시 등록.
        - 전혀 일치하지 않으면 OCR 자동생성 로직과 동일하게 새 약품을 즉석 생성해서라도 등록
          (등록 자체가 막히지 않아야 한다는 T-MED-1 원칙을 수동 등록에도 동일 적용).
        - 여러 개가 부분일치하면 자동 등록하지 않고 후보만 반환한다
          (T-MED-1 원칙: 후보가 여러 개면 사용자 최종 선택 없이는 등록되지 않는다)."""
        stripped_name = drug_name.strip()
        if not stripped_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="약품명을 입력해주세요.")

        matches = await self._dur_drug_repository.search_item_names(
            session, stripped_name, _SEARCH_TIER1_CANDIDATE_LIMIT
        )
        exact_matches = [(seq, name) for seq, name in matches if name == stripped_name]

        auto_created = False
        if len(exact_matches) == 1:
            item_seq, item_name = exact_matches[0]
        elif len(matches) == 1:
            item_seq, item_name = matches[0]
        elif len(matches) > 1:
            candidates = [QuickRegisterCandidate(drug_code=seq, medication_name=name) for seq, name in matches]
            return QuickRegisterResult(status="multiple_matches", candidates=candidates)
        else:
            matched_drug, auto_created = await _resolve_manual_registration_medication(session, stripped_name)
            item_seq, item_name = matched_drug.item_seq, matched_drug.item_name

        display_name = item_name if item_seq.startswith("AUTO_") else None
        schedule = MedicationSchedule(
            profile_id=profile_id,
            item_seq=item_seq,
            display_name=display_name,
            times=times,
            hospital_name=hospital_name,
        )
        schedule = await self._repository.create_schedule(session, schedule)
        await self._side_effect_notification_service.notify_if_side_effects(session, profile_id, item_name)

        return QuickRegisterResult(
            status="registered",
            schedule=MedicationScheduleResponse(
                id=schedule.id,
                item_seq=schedule.item_seq,
                drug_name=item_name,
                times=schedule.times,
                hospital_name=schedule.hospital_name,
            ),
            auto_created=auto_created,
        )

    async def check_interactions(self, session: AsyncSession, profile_id: int) -> InteractionCheckResult:
        """등록약 중 item_seq가 있는 약들을 서로 대조해 병용금기(DUR) 페어를 찾는다 (T-MED-2-2).
        지병(질병-성분) 기준 금기는 범위 밖 — 등록약 사이의 약물-약물 병용금기만 다룬다."""
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        item_seqs = {s.item_seq for s in schedules if not s.item_seq.startswith("AUTO_")}
        if len(item_seqs) < 2:
            return InteractionCheckResult(warnings=[], checked_count=len(item_seqs))

        names = await self._dur_drug_repository.get_names_by_item_seqs(session, item_seqs)
        warnings = await _find_interaction_warnings(item_seqs, names)
        return InteractionCheckResult(warnings=warnings, checked_count=len(item_seqs))

    async def check_food_interactions(self, session: AsyncSession, profile_id: int) -> FoodInteractionCheckResult:
        """(T-DOC-2/T-DOC-5) 등록약 전체를 대상으로 음식/음주 주의사항을 모은다. 1,2단계(식약처
        참조 테이블 → MySQL `drugs_data` 스냅샷)만으로 즉시 응답한다 — 느린 3단계(실시간 e약은요
        API)는 여기서 호출하지 않고, 확인 안 된 약 이름만 `pending_medication_names`에 담아
        돌려준다. 나머지는 `check_food_interactions_pending`을 별도로 호출해 채운다.
        confirm_recognition_job의 1회성 안내와 달리, OCR로 등록했든 수동으로 등록했든 상관없이
        "음식(13번)" 탭을 열 때마다 현재 등록약 전체 기준으로 조회한다."""
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        names = await self._dur_drug_repository.get_names_by_item_seqs(session, {s.item_seq for s in schedules})
        display_names = {s.display_name or names.get(s.item_seq, s.item_seq) for s in schedules}

        guide_cards: list[GuideCard] = []
        pending_medication_names: list[str] = []
        for name in display_names:
            card = await _build_food_interaction_guide_card_fast(session, name)
            if card is None:
                pending_medication_names.append(name)
                continue
            guide_cards.append(card)

        # (T-DOC-3) 실제 주의사항이 있는 카드(severity="caution")를 "확인 안 됨"/"주의사항 없음"
        # 카드(severity="info")보다 위로 올린다 — 등록약이 많을수록 실제로 봐야 할 카드가 뒤로
        # 밀려 놓치기 쉽다.
        guide_cards.sort(key=lambda card: card.severity != "caution")

        return FoodInteractionCheckResult(
            guide_cards=guide_cards,
            checked_count=len(display_names),
            pending_medication_names=pending_medication_names,
        )

    async def check_food_interactions_pending(
        self, session: AsyncSession, profile_id: int
    ) -> FoodInteractionCheckResult:
        """(T-DOC-5) `check_food_interactions`가 1,2단계로 확인하지 못해 넘긴(주로 상표명이면서
        `drugs_data` 스냅샷에도 없는) 약만 골라 느린 3단계(실시간 e약은요 API)로 확인한다.
        결과는 약품명 기준 프로세스 메모리 캐시에 저장되어(`_build_food_interaction_guide_card_slow_cached`)
        같은 약을 반복 호출해도 API를 다시 부르지 않는다."""
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        names = await self._dur_drug_repository.get_names_by_item_seqs(session, {s.item_seq for s in schedules})
        display_names = {s.display_name or names.get(s.item_seq, s.item_seq) for s in schedules}

        guide_cards: list[GuideCard] = []
        for name in display_names:
            fast_card = await _build_food_interaction_guide_card_fast(session, name)
            if fast_card is not None:
                continue
            guide_cards.append(await _build_food_interaction_guide_card_slow_cached(name))

        guide_cards.sort(key=lambda card: card.severity != "caution")

        return FoodInteractionCheckResult(guide_cards=guide_cards, checked_count=len(guide_cards))

    async def search_medications(self, session: AsyncSession, query: str) -> list[dict]:
        """수동 등록 검색창의 자동완성 — 마스터 DB(dur_prod_master_list)에서 이름으로 검색한다."""
        results = await self._dur_drug_repository.search_item_names(session, query, _SEARCH_TIER1_CANDIDATE_LIMIT)
        return [{"item_seq": item_seq, "medication_name": item_name} for item_seq, item_name in results]

    async def confirm_recognition_job_for_family(
        self,
        session: AsyncSession,
        job_id: str,
        requester_profile_id: int,
        target_profile_id: int,
        selected_candidate_drug_code: str | None,
        confirmed_fields: dict | None,
    ) -> RecognitionConfirmResult:
        """(가족관리) OCR로 인식한 처방전을 요청자 본인이 아니라, 요청자가 보호자로 등록된
        가족 구성원(target_profile_id) 몫으로 등록한다.

        [의도적 중복 - TODO] confirm_recognition_job과 로직이 거의 동일하다. 이 시점에 다른
        조원이 confirm_recognition_job(OCR/수동 등록 마스터 DB 매칭)을 계속 다듬고 있어서,
        공통 헬퍼로 묶는 리팩터링은 병합 충돌 위험이 있다고 판단해 완전히 분리된 함수로
        추가했다. 두 함수를 합칠지는 조원과 상의 후 결정 예정 - 상의 전까지는 이 함수를
        건드리지 않고 confirm_recognition_job 쪽만 개선/수정한다."""
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 프로필에 대한 권한이 없습니다. 더보기 > 가족관리에서 먼저 연결해주세요.",
            )

        job = await self._repository.get_recognition_job(session, job_id)
        if not job or job.profile_id != requester_profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 작업(Job)을 찾을 수 없습니다.")

        drug_name: str | None = None
        if selected_candidate_drug_code:
            item_seq = selected_candidate_drug_code
            await _require_item_seq(session, self._repository, item_seq)

            candidate = next((c for c in (job.candidates or []) if c["drug_code"] == item_seq), None)
            drug_name = candidate["drug_name"] if candidate else item_seq
            display_name = drug_name if item_seq.startswith("AUTO_") else None

            times = ["09:00", "13:00", "19:00"]
            if confirmed_fields and "times" in confirmed_fields:
                times = confirmed_fields["times"]
            elif job.extracted_fields and job.extracted_fields.get("times"):
                times = job.extracted_fields["times"]

            schedule = MedicationSchedule(
                profile_id=target_profile_id,
                item_seq=item_seq,
                display_name=display_name,
                times=times,
                source_job_id=job_id,
            )
            await self._repository.create_schedule(session, schedule)
            await self._side_effect_notification_service.notify_if_side_effects(session, target_profile_id, drug_name)

        guide_cards = []
        if drug_name:
            guide_cards.append(await _build_food_interaction_guide_card(session, drug_name))

        return RecognitionConfirmResult(status="confirmed", guide_cards=guide_cards)

    async def list_schedules_for_family(
        self, session: AsyncSession, requester_profile_id: int, target_profile_id: int
    ) -> list[MedicationScheduleResponse]:
        """(가족관리) 보호자가 가족 구성원의 복약 스케줄 전체를 조회 - 복약알림/트랙커의
        가족 화면에서 달력·목록에 쓴다."""
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 프로필에 대한 권한이 없습니다.")
        return await self.list_schedules(session, target_profile_id)

    async def check_interactions_for_family(
        self, session: AsyncSession, requester_profile_id: int, target_profile_id: int
    ) -> InteractionCheckResult:
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 프로필에 대한 권한이 없습니다.")
        return await self.check_interactions(session, target_profile_id)

    async def check_food_interactions_for_family(
        self, session: AsyncSession, requester_profile_id: int, target_profile_id: int
    ) -> FoodInteractionCheckResult:
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 프로필에 대한 권한이 없습니다.")
        return await self.check_food_interactions(session, target_profile_id)

    async def check_food_interactions_pending_for_family(
        self, session: AsyncSession, requester_profile_id: int, target_profile_id: int
    ) -> FoodInteractionCheckResult:
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 프로필에 대한 권한이 없습니다.")
        return await self.check_food_interactions_pending(session, target_profile_id)

    async def update_schedule_for_family(
        self, session: AsyncSession, requester_profile_id: int, schedule_id: int, req: MedicationScheduleUpdateRequest
    ) -> MedicationScheduleResponse:
        """(가족관리) 보호자가 가족 구성원 몫 복약 스케줄을 수정한다 - update_schedule(본인용)과
        delete_schedule_for_family(가족용 삭제)를 그대로 합친 패턴이다. 본인용은
        `schedule.profile_id != profile_id`로 소유자만 확인하지만, 여기서는 소유자 자신이
        아니라 "요청자가 그 소유자의 보호자인지"를 확인한다."""
        schedule = await self._repository.get_schedule_by_id(session, schedule_id)
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 복약 스케줄을 찾을 수 없습니다.")
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, schedule.profile_id)
        if not is_guardian:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="해당 복약 스케줄을 수정할 권한이 없습니다."
            )

        if req.times is not None:
            schedule.times = req.times
        if req.hospital_name is not None:
            schedule.hospital_name = req.hospital_name
        await session.commit()
        await session.refresh(schedule)

        names = await self._dur_drug_repository.get_names_by_item_seqs(session, {schedule.item_seq})
        return MedicationScheduleResponse(
            id=schedule.id,
            item_seq=schedule.item_seq,
            drug_name=schedule.display_name or names.get(schedule.item_seq, schedule.item_seq),
            times=schedule.times,
            source_job_id=schedule.source_job_id,
            hospital_name=schedule.hospital_name,
        )

    async def delete_schedule_for_family(
        self, session: AsyncSession, requester_profile_id: int, schedule_id: int
    ) -> None:
        """(가족관리) 보호자가 가족 구성원 몫 복약 스케줄을 삭제한다."""
        schedule = await self._repository.get_schedule_by_id(session, schedule_id)
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 복약 스케줄을 찾을 수 없습니다.")
        is_guardian = await self._family_repository.is_guardian_of(session, requester_profile_id, schedule.profile_id)
        if not is_guardian:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="해당 복약 스케줄을 삭제할 권한이 없습니다."
            )
        await self._repository.delete_schedule(session, schedule)
