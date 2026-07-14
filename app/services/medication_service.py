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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import AsyncSessionLocal
from app.dtos.medication_dto import (
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
from app.models.medication_model import Medication, MedicationRecognitionJob, MedicationSchedule
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.services import medication_open_api_client

logger = logging.getLogger("app.medication_service")

CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")

# 타임아웃/5xx처럼 재시도하면 성공할 여지가 있는 실패에 한해서만 재시도한다.
# 401/403 같은 인증 오류나 응답 파싱 실패는 재시도해도 결과가 같으므로 즉시 실패 처리한다.
_CLOVA_OCR_MAX_ATTEMPTS = 2
_CLOVA_OCR_RETRY_DELAY_SECONDS = 0.5

# 약품명 후보로 볼 만한 OCR 텍스트 블록 판별 기준.
# "정"/"캡슐" 같은 제형 접미사만으로는 "환자정보", "서방정"(잘린 조각) 등 일반 텍스트도
# 걸려버려서, 반드시 (a) 용량 숫자+단위(mg/g/ml)가 붙어 있거나 (b) 처방전 약품 목록에서
# 흔히 쓰이는 "*" 불릿 표시가 있거나 (c) 흔한 약품 제형 접미사로 끝나는 경우만 후보로
# 인정한다. (c)는 최소 길이(_MIN_DRUG_NAME_LEN) 조건과 함께 적용되므로 "환자정보"/"서방정"
# 같은 짧은 일반 텍스트 조각은 그 단계에서 이미 걸러진다.
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

# (#120) "아스피린에 과민증이 있는 경우..."처럼 처방전 복약안내 문구에 성분명이 조사와 함께
# 언급되면("아스피린에"), 실제로는 완결된 약품명이 아닌 문장 중간 단어인데도 편집거리상 다른
# 실약품명("아스피린정")과 우연히 비슷해(1글자 차이) 임계값을 넘겨버릴 수 있다. 조사는 한국어에서
# 띄어쓰기 없이 명사 바로 뒤에 붙으므로, 이런 조사로 끝나는 토큰은 완결된 약품명일 수 없다고 보고
# 퍼지 매칭 대상에서 제외한다.
_TRAILING_PARTICLE_PATTERN = re.compile(r"(?:에서|부터|까지|으로|처럼|이나|은|는|이|가|을|를|도|만|와|과|의|에|로|나)$")

# (#106) CLOVA OCR이 "패취"를 "매취"로 읽는 것처럼 글자 하나를 비슷한 글자로 잘못 읽으면,
# 접미사/용량 패턴이 아예 안 맞아 _looks_like_drug_name을 통과하지 못한다. 이런 텍스트를
# 구제하기 위해 숫자/기호를 떼고 한글만 남긴 뒤 마스터 DB 약품명(마찬가지로 한글만 남긴 것)과
# 편집거리 기반 유사도를 비교한다. 임계값은 실제 오탈자 케이스("노스판매취" vs "노스판패취" ≈
# 0.8)와 노이즈 텍스트(처방전 설명 문구 등, 대부분 0.3 미만)를 실측해 분리되는 지점으로 정했다.
_FUZZY_MATCH_THRESHOLD = 0.8
_FUZZY_MATCH_CANDIDATE_LIMIT = 2000
_FUZZY_MATCH_MIN_KOREAN_LEN = 3

# (#108) MySQL(Tier2) 캐시는 실제 조회된 약만 그때그때 쌓이는 지연 적재 구조라 아직 작다.
# 로컬에 이미 있는 Tier1 SQLite 마스터 DB(27,000여 개, app/database/dur_drug_light.db)를
# 매칭/퍼지 후보에도 같이 써서, MySQL에 없는 약도 정확/유사 매칭될 수 있게 한다. 27,000개
# 전체를 매번 편집거리로 비교하면 느리므로, 한글 쿼리의 앞 몇 글자를 접두어로 SQLite에서
# 먼저 후보를 좁힌다(대부분의 OCR 오인식은 뒷글자에서 발생하고 앞글자는 맞는 경우가 많다).
_FUZZY_TIER1_PREFIX_LEN = 2
_FUZZY_TIER1_CANDIDATE_LIMIT = 300


def _korean_only(text: str) -> str:
    return "".join(_KOREAN_TOKEN_PATTERN.findall(text))


def _best_fuzzy_candidate(query: str, candidates: list[tuple[str, str]], threshold: float) -> str | None:
    """`candidates`((key, 이름)) 중 `query`(한글만 남긴 OCR 텍스트)와 가장 유사하면서 임계값
    이상인 것의 key를 반환한다. key는 호출부에 따라 MySQL Medication.id(문자열화) 또는 Tier1
    item_seq일 수 있다 — 이 함수는 키의 의미를 모른 채 순수 문자열 유사도만 비교한다.

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


async def _get_or_create_medication_from_tier1(
    db_session: AsyncSession, repo: MedicationRepository, item_seq: str, item_name: str
) -> Medication:
    """(#108) Tier1 SQLite에서 찾은 약을 MySQL(Tier2)에 캐싱한다. 이미 이 item_seq로 캐싱된
    적이 있으면(다른 처방전에서 이미 조회됐던 약이면) 재사용하고, 없으면 새로 만든다 — 같은
    약이 조회될 때마다 중복 레코드가 쌓이지 않게 한다."""
    standard_code = f"PDP_{item_seq}"
    existing = await repo.get_medication_by_code(db_session, standard_code)
    if existing:
        return existing
    return await repo.create_medication(db_session, Medication(medication_name=item_name, standard_code=standard_code))


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
# 약 또는 음식은 무엇입니까?")에서 음식/음주 관련 주의사항을 그대로 노출한다. 원문 재가공(요약/
# 재작성)은 하지 않는다 — 면책 목적상 식약처 원문 그대로가 더 안전하다.
_FOOD_GUIDE_CARD_TITLE = "복약 중 음식 주의사항"
_NO_FOOD_INTERACTION_MESSAGE = "확인된 음식·음주 관련 주의사항이 없습니다."


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
    """`Medication.standard_code`가 품목기준코드 유래(`PDP_{item_seq}`)일 때만 item_seq를 뽑아낸다.
    로컬 라이트 DB 등 다른 경로로 채워진 코드(예: `KD_...`)는 병용금기 DUR 조회에 쓸 수 없어 None."""
    if not standard_code or not standard_code.startswith("PDP_"):
        return None
    item_seq = standard_code.removeprefix("PDP_")
    return item_seq or None


_TRAILING_DOSAGE_PATTERN = re.compile(r"\s*\d+(\.\d+)?\s*(mg|g|ml)\s*$", re.IGNORECASE)


def _strip_trailing_dosage(name: str) -> str | None:
    """공공데이터 API의 정식 품목명은 'mg'가 아니라 '밀리그램' 등 한글 단위 표기를 쓰는 경우가
    많아, OCR/사용자 입력이 'NNmg' 형태 접미사로 끝나면 그 부분을 뗀 이름으로도 재시도할 수 있게
    한다. 접미사가 없으면 None."""
    stripped = _TRAILING_DOSAGE_PATTERN.sub("", name).strip()
    return stripped if stripped and stripped != name else None


async def _fetch_master_data_safely(name: str) -> dict | None:
    """공공데이터 API가 타임아웃/오류로 응답하지 않아도 등록약 백필 전체가 500으로 죽지 않게
    한다 — 그 약만 이번 조회에서 건너뛴다."""
    try:
        return await medication_open_api_client.fetch_medication_master_data(name)
    except (httpx.HTTPError, medication_open_api_client.PublicDataApiError):
        return None


async def _fetch_master_data_with_fallback(name: str) -> dict | None:
    master_data = await _fetch_master_data_safely(name)
    if master_data and master_data.get("standard_code"):
        return master_data

    stripped_name = _strip_trailing_dosage(name)
    if stripped_name:
        return await _fetch_master_data_safely(stripped_name)
    return master_data


async def _resolve_medications_with_item_seq(
    session: AsyncSession, medications: list[Medication]
) -> list[tuple[str, Medication]]:
    """등록약을 item_seq 유무로 나누고, 없는 약은 공공데이터 API로 한 번 더 보완을 시도한다.
    수동/OCR 빠른 등록(T-MED-3)은 공공데이터 조회 없이 AUTO_ 더미 코드로 등록하는 경우가 많다 —
    조회 시점에 실제 품목기준코드를 찾으면 DB에도 반영해 다음 조회부터는 재조회가 필요 없게 한다."""
    meds_with_seq: list[tuple[str, Medication]] = []
    meds_without_seq: list[Medication] = []
    for med in medications:
        item_seq = _extract_item_seq(med.standard_code)
        if item_seq:
            meds_with_seq.append((item_seq, med))
        else:
            meds_without_seq.append(med)

    if not meds_without_seq:
        return meds_with_seq

    master_data_results = await asyncio.gather(
        *[_fetch_master_data_with_fallback(med.medication_name) for med in meds_without_seq]
    )
    resolved_any = False
    for med, master_data in zip(meds_without_seq, master_data_results, strict=True):
        new_code = master_data.get("standard_code") if master_data else None
        item_seq = _extract_item_seq(new_code)
        if item_seq:
            med.standard_code = new_code
            meds_with_seq.append((item_seq, med))
            resolved_any = True
    if resolved_any:
        await session.commit()

    return meds_with_seq


async def _find_interaction_warnings(meds_with_seq: list[tuple[str, Medication]]) -> list[InteractionWarning]:
    seq_to_med = {item_seq: med for item_seq, med in meds_with_seq}
    name_to_med = {med.medication_name: med for _, med in meds_with_seq}

    warnings: list[InteractionWarning] = []
    seen_pairs: set[frozenset[int]] = set()

    for item_seq, med in meds_with_seq:
        try:
            dur_items = await medication_open_api_client.fetch_dur_item_info(item_seq=item_seq)
        except (httpx.HTTPError, medication_open_api_client.PublicDataApiError):
            # 공공데이터 API가 타임아웃/오류로 응답하지 않아도 그 약만 건너뛰고 나머지는 계속 확인한다.
            continue
        for dur in dur_items:
            mixture_seq = dur.get("MIXTURE_ITEM_SEQ")
            mixture_name = dur.get("MIXTURE_ITEM_NAME")
            other_med = seq_to_med.get(mixture_seq) if mixture_seq else None
            if other_med is None and mixture_name:
                other_med = name_to_med.get(mixture_name)
            if other_med is None or other_med.id == med.id:
                continue

            pair_key = frozenset({med.id, other_med.id})
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            warnings.append(
                InteractionWarning(
                    drug_a_name=med.medication_name,
                    drug_b_name=other_med.medication_name,
                    description=dur.get("PROHBT_CONTENT") or "병용금기 성분 조합으로 확인되었습니다.",
                )
            )

    return warnings


def _is_annotation_line(stripped: str) -> bool:
    """ "(Buprenorphine 10mg)"처럼 괄호로 감싼 성분/일반명 표기, "[한국먼디파마]"처럼
    대괄호로 감싼 제조사명 표기는 브랜드 약품명이 아니므로 후보(퍼지 매칭 포함)에서 제외한다."""
    return stripped.startswith("(") or stripped.endswith(")") or (stripped.startswith("[") and stripped.endswith("]"))


def _looks_like_drug_name(word: str) -> bool:
    stripped = word.lstrip("*").strip()
    if len(stripped) < _MIN_DRUG_NAME_LEN:
        return False
    if _is_annotation_line(stripped):
        return False
    if _INSTITUTION_SUFFIX_PATTERN.search(stripped):
        return False
    if not _KOREAN_TOKEN_PATTERN.search(stripped):
        return False
    return (
        bool(_DOSAGE_PATTERN.search(stripped))
        or word.strip().startswith("*")
        or bool(_DRUG_FORM_SUFFIX_PATTERN.search(stripped))
    )


def _dedupe_drug_names(names: set[str]) -> list[str]:
    """짧게 잘린 OCR 조각(예: '레마이드정')이 온전한 이름('레마이드정100mg')의 부분 문자열이면
    짧은 쪽을 버리고, 온전한 형태만 후보로 남긴다."""
    ordered = sorted(names, key=len, reverse=True)
    kept: list[str] = []
    for name in ordered:
        if not any(name != k and name in k for k in kept):
            kept.append(name)
    return kept


async def _fetch_medication_from_public_api(name: str) -> Medication | None:
    """Tier 3: 로컬 DB(Tier 1/2)에 없는 약품을 공공데이터포털 API로 실시간 조회한다(T-MED-4).
    `PUBLIC_DATA_API_KEY` 미설정/호출 실패/빈 응답이면 None을 반환해 기존 `AUTO_` 더미 생성
    폴백으로 넘어가게 한다 — 등록 자체가 막히지 않는다는 T-MED-1 원칙을 그대로 유지."""
    try:
        fields = await medication_open_api_client.fetch_medication_master_data(name)
    except medication_open_api_client.PublicDataApiError:
        return None
    if fields is None:
        return None

    standard_code = fields.pop("standard_code") or f"AUTO_{uuid.uuid4().hex[:10].upper()}"
    return Medication(medication_name=name, standard_code=standard_code, **fields)


async def _create_medication_for_unmatched_name(
    db_session: AsyncSession, repo: MedicationRepository, name: str
) -> tuple[Medication, bool]:
    """DB(Tier 2)에 없는 약품명에 대해 Tier 3(공공 API) 조회 → 실패 시 AUTO_ 더미 생성 순으로
    레코드를 만든다. 반환값: (생성된 Medication, 더미 생성 여부)."""
    new_med = await _fetch_medication_from_public_api(name)
    is_auto_dummy = new_med is None
    if new_med is None:
        new_med = Medication(medication_name=name, standard_code=f"AUTO_{uuid.uuid4().hex[:10].upper()}")
    new_med = await repo.create_medication(db_session, new_med)
    return new_med, is_auto_dummy


async def _match_existing_by_word(
    db_session: AsyncSession, repo: MedicationRepository, ocr_fields: list[OcrField], seen_ids: set[int]
) -> tuple[list[Medication], dict[int, float]]:
    """짧은 숫자/용량 조각("100mg" 등)까지 LIKE 검색에 넣으면 우연히 다른 약의 용량과 겹쳐
    엉뚱한 약이 매칭되므로(예: "100mg"이 "아스피린정 100mg"에 우연히 포함), 약품명처럼
    보이는 온전한 단어에 대해서만 실제 DB 매칭을 시도한다.

    반환값의 두 번째 요소는 (T-MED-6) 각 매칭 약품에 연결된 OCR 필드의 confidence —
    같은 약이 여러 단어로 매칭되면 그중 가장 높은 confidence를 취한다."""
    matched: list[Medication] = []
    confidences: dict[int, float] = {}
    for field in ocr_fields:
        if not _looks_like_drug_name(field.text):
            continue
        stripped = field.text.lstrip("*").strip()
        for med in await repo.search_medication_by_name(db_session, stripped):
            if med.id not in seen_ids:
                seen_ids.add(med.id)
                matched.append(med)
            confidences[med.id] = max(confidences.get(med.id, 0.0), field.confidence)
    return matched, confidences


async def _resolve_or_create_drug_like_names(
    db_session: AsyncSession, repo: MedicationRepository, ocr_fields: list[OcrField], seen_ids: set[int]
) -> tuple[list[Medication], set[int], dict[int, float]]:
    """마스터 DB에 없는 약이어도, OCR 텍스트가 약품명 형태(용량단위 또는 "*" 불릿 표시)로
    보이면 등록이 막히지 않도록 새 마스터 레코드를 즉석에서 생성해 후보로 포함시킨다.
    "*"는 정규화 과정에서 제거하고, 잘려서 중복된 짧은 조각은 dedupe로 걸러낸다."""
    resolved: list[Medication] = []
    auto_created_ids: set[int] = set()
    confidences: dict[int, float] = {}
    dur_repo = DurDrugRepository()

    name_confidence: dict[str, float] = {}
    for field in ocr_fields:
        if not _looks_like_drug_name(field.text):
            continue
        name = field.text.lstrip("*").strip()
        name_confidence[name] = max(name_confidence.get(name, 0.0), field.confidence)

    for name in _dedupe_drug_names(set(name_confidence)):
        confidence = name_confidence[name]
        existing = await repo.search_medication_by_name(db_session, name)
        exact = next((m for m in existing if m.medication_name == name), None)
        if exact:
            confidences[exact.id] = max(confidences.get(exact.id, 0.0), confidence)
            if exact.id not in seen_ids:
                seen_ids.add(exact.id)
                resolved.append(exact)
            continue

        # (#108) MySQL(Tier2)에 없어도 AUTO_ 더미를 만들기 전에, 로컬에 이미 있는 Tier1
        # SQLite 마스터 DB(27,000여 개)에 정확히 같은 이름이 있는지 먼저 확인한다.
        tier1_results = await asyncio.to_thread(dur_repo.search_item_names, name, 5)
        tier1_item_seq = next((seq for seq, iname in tier1_results if iname == name), None)
        if tier1_item_seq:
            tier1_med = await _get_or_create_medication_from_tier1(db_session, repo, tier1_item_seq, name)
            confidences[tier1_med.id] = max(confidences.get(tier1_med.id, 0.0), confidence)
            if tier1_med.id not in seen_ids:
                seen_ids.add(tier1_med.id)
                resolved.append(tier1_med)
            continue

        new_med, is_auto_dummy = await _create_medication_for_unmatched_name(db_session, repo, name)
        seen_ids.add(new_med.id)
        if is_auto_dummy:
            auto_created_ids.add(new_med.id)
        resolved.append(new_med)
        confidences[new_med.id] = confidence

    return resolved, auto_created_ids, confidences


async def _fuzzy_match_unrecognized_fields(
    db_session: AsyncSession, repo: MedicationRepository, ocr_fields: list[OcrField], seen_ids: set[int]
) -> tuple[list[Medication], dict[int, float]]:
    """(#106) `_looks_like_drug_name`이 걸러낸(=용량/불릿/제형 접미사 조건을 하나도 못 만족한)
    텍스트 중, 한글 부분만 떼어 마스터 DB 약품명(마찬가지로 한글만 남긴 것)과 편집거리
    유사도를 비교한다. CLOVA가 글자 하나를 잘못 읽은 경우(예: "패취"→"매취")를 구제하는
    용도라, 기존 마스터 DB에 있는 것과 확실히 비슷할 때만(임계값 이상) 인정하고 새 레코드를
    만들지는 않는다 — 애매한 텍스트로 엉뚱한 약을 만들어내는 위험을 피하기 위함이다.

    (#108) MySQL(Tier2)에서 못 찾으면, 로컬 Tier1 SQLite 마스터 DB(27,000여 개)에서도
    같은 방식으로 시도한다 — 이번엔 찾으면 MySQL에 새로 캐싱한다(다음엔 정확일치로 바로
    잡히도록)."""
    mysql_candidates = await repo.list_medication_names(db_session, limit=_FUZZY_MATCH_CANDIDATE_LIMIT)
    if len(mysql_candidates) >= _FUZZY_MATCH_CANDIDATE_LIMIT:
        logger.warning(
            "퍼지 매칭 비교 대상을 %d개로 제한합니다 — 마스터 DB가 더 많으면 일부만 비교됩니다.",
            _FUZZY_MATCH_CANDIDATE_LIMIT,
        )
    dur_repo = DurDrugRepository()

    matched: list[Medication] = []
    confidences: dict[int, float] = {}
    for field in ocr_fields:
        if _looks_like_drug_name(field.text):
            continue  # 이미 기존 경로에서 처리 대상이 됨
        stripped = field.text.lstrip("*").strip()
        if _is_annotation_line(stripped):
            continue  # 성분/제조사명 표기 줄은 브랜드 약품명이 아니므로 퍼지 매칭도 제외
        if _INSTITUTION_SUFFIX_PATTERN.search(stripped):
            continue  # 약국/병원명은 브랜드 약품명이 아니므로 퍼지 매칭도 제외
        if _TRAILING_PARTICLE_PATTERN.search(stripped):
            continue  # 조사로 끝나는 문장 중간 단어는 완결된 약품명이 아니므로 퍼지 매칭도 제외
        query = _korean_only(field.text)
        if len(query) < _FUZZY_MATCH_MIN_KOREAN_LEN:
            continue

        med = await _fuzzy_match_one_field(db_session, repo, dur_repo, query, mysql_candidates, seen_ids)
        if med is None:
            continue
        seen_ids.add(med.id)
        matched.append(med)
        confidences[med.id] = max(confidences.get(med.id, 0.0), field.confidence)

    return matched, confidences


async def _fuzzy_match_one_field(
    db_session: AsyncSession,
    repo: MedicationRepository,
    dur_repo: DurDrugRepository,
    query: str,
    mysql_candidates: list[tuple[int, str]],
    seen_ids: set[int],
) -> Medication | None:
    """OCR 텍스트(한글만 남긴 것) 하나에 대해 MySQL(Tier2) 후보를 먼저 시도하고, 없으면
    Tier1 SQLite 후보를 시도한다."""
    mysql_pool = [(str(med_id), name) for med_id, name in mysql_candidates if med_id not in seen_ids]
    best_mysql_key = _best_fuzzy_candidate(query, mysql_pool, _FUZZY_MATCH_THRESHOLD)
    if best_mysql_key is not None:
        return await repo.get_medication_by_id(db_session, int(best_mysql_key))

    tier1_candidates = await asyncio.to_thread(
        dur_repo.search_item_names_by_prefix, query[:_FUZZY_TIER1_PREFIX_LEN], _FUZZY_TIER1_CANDIDATE_LIMIT
    )
    best_item_seq = _best_fuzzy_candidate(query, tier1_candidates, _FUZZY_MATCH_THRESHOLD)
    if best_item_seq is None:
        return None
    item_name = next(name for seq, name in tier1_candidates if seq == best_item_seq)
    med = await _get_or_create_medication_from_tier1(db_session, repo, best_item_seq, item_name)
    return med if med.id not in seen_ids else None


async def _match_or_create_medications(
    db_session: AsyncSession, repo: MedicationRepository, ocr_fields: list[OcrField]
) -> tuple[list[Medication], set[int], dict[int, float]]:
    """OCR 텍스트에서 약품명으로 보이는 조각을 마스터 DB와 매칭하고, 없으면 새로 생성한다.
    반환값: (매칭/생성된 약품 목록, 이번에 새로 생성된 약품의 id 집합, 약품별 OCR confidence)"""
    matched_meds: list[Medication] = []
    auto_created_ids: set[int] = set()
    seen_ids: set[int] = set()
    match_confidence: dict[int, float] = {}

    if ocr_fields:
        existing_matched, existing_confidence = await _match_existing_by_word(db_session, repo, ocr_fields, seen_ids)
        matched_meds.extend(existing_matched)
        match_confidence.update(existing_confidence)

        resolved, auto_created_ids, resolved_confidence = await _resolve_or_create_drug_like_names(
            db_session, repo, ocr_fields, seen_ids
        )
        matched_meds.extend(resolved)
        match_confidence.update(resolved_confidence)

        fuzzy_matched, fuzzy_confidence = await _fuzzy_match_unrecognized_fields(db_session, repo, ocr_fields, seen_ids)
        matched_meds.extend(fuzzy_matched)
        match_confidence.update(fuzzy_confidence)

    # 그래도 후보가 하나도 없으면(약품명으로 보이는 텍스트조차 없었던 경우)
    # 마스터 DB 상위 몇 개를 참고용으로 보여준다 — 이 경우엔 수동 검색으로의 전환을 기대한다.
    if not matched_meds:
        all_meds = await repo.search_medication_by_name(db_session, "")
        matched_meds = all_meds[:3]

    return matched_meds, auto_created_ids, match_confidence


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


async def _build_food_interaction_guide_card(medication_name: str) -> GuideCard | None:
    """(T-DOC-2) e약은요 API의 `intrcQesitm`(상호작용 문항)에서 음식/음주 관련 주의사항을 가져와
    GuideCard로 변환한다. API 호출 실패(타임아웃/오류)와 "확인 결과 주의사항 없음"은 의미가
    다르므로, 실패 시에는 "주의사항 없음"이라고 잘못 안내하지 않도록 카드 자체를 생략(None)한다."""
    try:
        summaries = await medication_open_api_client.fetch_drug_summary(item_name=medication_name)
    except (httpx.HTTPError, medication_open_api_client.PublicDataApiError):
        return None

    if not summaries:
        return None

    interaction_text = (summaries[0].get("intrcQesitm") or "").strip()
    if not interaction_text:
        return GuideCard(title=_FOOD_GUIDE_CARD_TITLE, content=_NO_FOOD_INTERACTION_MESSAGE, severity="info")

    return GuideCard(title=_FOOD_GUIDE_CARD_TITLE, content=interaction_text, severity="caution")


async def _execute_ocr_logic(
    db_session: AsyncSession,
    job_id: str,
    source_type: str,
    file_bytes: bytes,
    file_name: str,
    dummy_mode: bool = False,
):
    repo = MedicationRepository()

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

    matched_meds, auto_created_ids, match_confidence = await _match_or_create_medications(db_session, repo, ocr_fields)

    for med in matched_meds:
        confidence = match_confidence.get(med.id, _NO_OCR_EVIDENCE_MATCH_RATE)
        match_rate = _compute_match_rate(confidence, is_auto_created=med.id in auto_created_ids)
        candidates.append(
            {
                "drug_name": med.medication_name,
                "match_rate": match_rate,
                "drug_code": med.standard_code or f"CODE_{med.id}",
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


class MedicationService:
    def __init__(self, repository: MedicationRepository | None = None) -> None:
        self._repository = repository or MedicationRepository()

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

        # 최종 약물 확정 및 등록 처리
        med: Medication | None = None
        if selected_candidate_drug_code:
            med = await self._repository.get_medication_by_code(session, selected_candidate_drug_code)
            if not med:
                # 만약 코드로 못 찾으면 ID로 재시도
                try:
                    med_id = int(selected_candidate_drug_code.replace("CODE_", ""))
                    med = await self._repository.get_medication_by_id(session, med_id)
                except ValueError:
                    pass

            if med:
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
                    profile_id=profile_id, medication_id=med.id, times=times, source_job_id=job_id
                )
                await self._repository.create_schedule(session, schedule)

        # 13번: 음식(T-DOC-2) — 등록된 약의 e약은요 상호작용 문항에서 음식/음주 주의사항을 안내한다.
        guide_cards = []
        if med:
            food_card = await _build_food_interaction_guide_card(med.medication_name)
            if food_card:
                guide_cards.append(food_card)

        return RecognitionConfirmResult(status="confirmed", guide_cards=guide_cards)

    async def list_schedules(self, session: AsyncSession, profile_id: int) -> list[MedicationScheduleResponse]:
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        return [
            MedicationScheduleResponse(
                id=s.id,
                medication_id=s.medication_id,
                drug_name=s.medication.medication_name,
                times=s.times,
                source_job_id=s.source_job_id,
                form_type=s.medication.form_type,
                dosage_guideline=s.medication.dosage_guideline,
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

        return MedicationScheduleResponse(
            id=schedule.id,
            medication_id=schedule.medication_id,
            drug_name=schedule.medication.medication_name,
            times=schedule.times,
            source_job_id=schedule.source_job_id,
            form_type=schedule.medication.form_type,
            dosage_guideline=schedule.medication.dosage_guideline,
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
        med = await self._repository.get_medication_by_code(session, req.drug_code)
        if not med:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 약품 정보를 찾을 수 없습니다.")

        schedule = MedicationSchedule(
            profile_id=profile_id, medication_id=med.id, times=req.times, hospital_name=req.hospital_name
        )
        await self._repository.create_schedule(session, schedule)

        return MedicationScheduleResponse(
            id=schedule.id,
            medication_id=schedule.medication_id,
            drug_name=med.medication_name,
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

        matches = await self._repository.search_medication_by_name(session, stripped_name)
        exact_matches = [m for m in matches if m.medication_name == stripped_name]

        auto_created = False
        if len(exact_matches) == 1:
            med = exact_matches[0]
        elif len(matches) == 1:
            med = matches[0]
        elif len(matches) > 1:
            candidates = [
                QuickRegisterCandidate(
                    drug_code=m.standard_code or f"CODE_{m.id}",
                    medication_name=m.medication_name,
                    form_type=m.form_type,
                )
                for m in matches
            ]
            return QuickRegisterResult(status="multiple_matches", candidates=candidates)
        else:
            med = Medication(medication_name=stripped_name, standard_code=f"AUTO_{uuid.uuid4().hex[:10].upper()}")
            med = await self._repository.create_medication(session, med)
            auto_created = True

        schedule = MedicationSchedule(
            profile_id=profile_id, medication_id=med.id, times=times, hospital_name=hospital_name
        )
        schedule = await self._repository.create_schedule(session, schedule)

        return QuickRegisterResult(
            status="registered",
            schedule=MedicationScheduleResponse(
                id=schedule.id,
                medication_id=schedule.medication_id,
                drug_name=med.medication_name,
                times=schedule.times,
                hospital_name=schedule.hospital_name,
            ),
            auto_created=auto_created,
        )

    async def check_interactions(self, session: AsyncSession, profile_id: int) -> InteractionCheckResult:
        """등록약 중 item_seq가 있는 약들을 서로 대조해 병용금기(DUR) 페어를 찾는다 (T-MED-2-2).
        지병(질병-성분) 기준 금기는 범위 밖 — 등록약 사이의 약물-약물 병용금기만 다룬다."""
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        medications = list({s.medication_id: s.medication for s in schedules}.values())

        meds_with_seq = await _resolve_medications_with_item_seq(session, medications)
        if len(meds_with_seq) < 2:
            return InteractionCheckResult(warnings=[], checked_count=len(meds_with_seq))

        warnings = await _find_interaction_warnings(meds_with_seq)
        return InteractionCheckResult(warnings=warnings, checked_count=len(meds_with_seq))

    async def search_medications(self, session: AsyncSession, query: str) -> list[dict]:
        meds = await self._repository.search_medication_by_name(session, query)
        return [
            {
                "id": m.id,
                "standard_code": m.standard_code,
                "medication_name": m.medication_name,
                "form_type": m.form_type,
            }
            for m in meds
        ]
