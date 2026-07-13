import asyncio
import base64
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


def _looks_like_drug_name(word: str) -> bool:
    stripped = word.lstrip("*").strip()
    if len(stripped) < _MIN_DRUG_NAME_LEN:
        return False
    # "(Buprenorphine 10mg)"처럼 괄호로 감싼 성분/일반명 표기 줄은 브랜드 약품명이 아니라
    # 별도 후보로 취급하면 안 되므로 제외한다.
    if stripped.startswith("(") or stripped.endswith(")"):
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

        new_med, is_auto_dummy = await _create_medication_for_unmatched_name(db_session, repo, name)
        seen_ids.add(new_med.id)
        if is_auto_dummy:
            auto_created_ids.add(new_med.id)
        resolved.append(new_med)
        confidences[new_med.id] = confidence

    return resolved, auto_created_ids, confidences


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

    dummy_mode가 명시적으로 요청됐거나, 실제 OCR 호출이 불가능/실패/빈 응답이면
    결정적인 더미 텍스트로 폴백해 등록 자체가 막히지 않게 한다."""
    if dummy_mode:
        return _dummy_ocr_fields(), True

    if not _clova_configured():
        logger.warning("CLOVA OCR 키/URL이 설정되지 않아 더미 텍스트로 폴백합니다.")
        return _dummy_ocr_fields(), True

    ocr_fields = await _call_clova_ocr(file_bytes, file_name)
    if not ocr_fields:
        logger.warning("CLOVA OCR 호출 결과가 비어 있어 더미 텍스트로 폴백합니다.")
        return _dummy_ocr_fields(), True
    return ocr_fields, False


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
    extracted_fields = {
        "dosage": "1정",
        "times": ["09:00", "13:00", "19:00"],
        "duration": "3일",
        "instruction": "식후 30분 복용",
        "ocr_raw_text": " ".join(f.text for f in ocr_fields),
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
    session: AsyncSession | None = None,
    dummy_mode: bool = False,
):
    """
    비동기 OCR 및 약품 매칭 백그라운드 태스크.
    session이 제공되면 해당 session을 재사용하고(테스트 환경용), 그렇지 않으면 자체 세션을 생성합니다.
    dummy_mode=True면 실제 OCR 호출 없이 결정적인 더미 인식 결과를 반환한다(T-MED-3).
    """
    if session is not None:
        await _execute_ocr_logic(session, job_id, source_type, file_bytes, file_name, dummy_mode)
    else:
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

        # 백그라운드 태스크 등록
        background_tasks.add_task(
            run_ocr_task, job_id, source_type, file_bytes, file_name, session=session, dummy_mode=dummy_mode
        )

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
                elif job.extracted_fields and "times" in job.extracted_fields:
                    times = job.extracted_fields["times"]

                schedule = MedicationSchedule(
                    profile_id=profile_id, medication_id=med.id, times=times, source_job_id=job_id
                )
                await self._repository.create_schedule(session, schedule)

        # 12, 13번: 추후 확장을 위한 구조 설계
        guide_cards = []
        if selected_candidate_drug_code:
            guide_cards.append(
                GuideCard(
                    title="복약 주의사항 안내",
                    content="등록하신 약품의 부작용 및 상호작용 정보(DUR)는 추후 연동될 예정입니다.",
                    severity="info",
                )
            )

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
