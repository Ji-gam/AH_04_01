import asyncio
import base64
import os
import re
import time
import uuid
from typing import cast

import httpx
from fastapi import BackgroundTasks, HTTPException, status
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

CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")

# 약품명 후보로 볼 만한 OCR 텍스트 블록 판별 기준.
# "정"/"캡슐" 같은 제형 접미사만으로는 "환자정보", "서방정"(잘린 조각) 등 일반 텍스트도
# 걸려버려서, 반드시 (a) 용량 숫자+단위(mg/g/ml)가 붙어 있거나 (b) 처방전 약품 목록에서
# 흔히 쓰이는 "*" 불릿 표시가 있는 경우만 후보로 인정한다.
_KOREAN_TOKEN_PATTERN = re.compile(r"[가-힣]{2,}")
_DOSAGE_PATTERN = re.compile(r"\d+(mg|g|ml)", re.IGNORECASE)
_MIN_DRUG_NAME_LEN = 5

# T-MED-3: OCR이 실패했거나(키 미설정/호출 예외/빈 응답) QA가 dummy_mode를 명시적으로 요청했을 때
# 쓰는 고정 더미 인식 텍스트. 처방전 목록 표기 관례("*" 불릿)를 그대로 따라야 기존 매칭 로직
# (_looks_like_drug_name)을 그대로 태워서 "실제 인식됐을 때와 동일한 흐름"으로 검증할 수 있다.
DUMMY_OCR_RAW_TEXT = ["*타이레놀정", "*아스피린정"]


def _extract_item_seq(standard_code: str | None) -> str | None:
    """`Medication.standard_code`가 품목기준코드 유래(`PDP_{item_seq}`)일 때만 item_seq를 뽑아낸다.
    로컬 라이트 DB 등 다른 경로로 채워진 코드(예: `KD_...`)는 병용금기 DUR 조회에 쓸 수 없어 None."""
    if not standard_code or not standard_code.startswith("PDP_"):
        return None
    item_seq = standard_code.removeprefix("PDP_")
    return item_seq or None


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
        *[medication_open_api_client.fetch_medication_master_data(med.medication_name) for med in meds_without_seq]
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
        dur_items = await medication_open_api_client.fetch_dur_item_info(item_seq=item_seq)
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
    if not _KOREAN_TOKEN_PATTERN.search(stripped):
        return False
    return bool(_DOSAGE_PATTERN.search(stripped)) or word.strip().startswith("*")


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
    db_session: AsyncSession, repo: MedicationRepository, raw_text_list: list[str], seen_ids: set[int]
) -> list[Medication]:
    """짧은 숫자/용량 조각("100mg" 등)까지 LIKE 검색에 넣으면 우연히 다른 약의 용량과 겹쳐
    엉뚱한 약이 매칭되므로(예: "100mg"이 "아스피린정 100mg"에 우연히 포함), 약품명처럼
    보이는 온전한 단어에 대해서만 실제 DB 매칭을 시도한다."""
    matched: list[Medication] = []
    for word in raw_text_list:
        if not _looks_like_drug_name(word):
            continue
        stripped = word.lstrip("*").strip()
        for med in await repo.search_medication_by_name(db_session, stripped):
            if med.id not in seen_ids:
                seen_ids.add(med.id)
                matched.append(med)
    return matched


async def _resolve_or_create_drug_like_names(
    db_session: AsyncSession, repo: MedicationRepository, raw_text_list: list[str], seen_ids: set[int]
) -> tuple[list[Medication], set[int]]:
    """마스터 DB에 없는 약이어도, OCR 텍스트가 약품명 형태(용량단위 또는 "*" 불릿 표시)로
    보이면 등록이 막히지 않도록 새 마스터 레코드를 즉석에서 생성해 후보로 포함시킨다.
    "*"는 정규화 과정에서 제거하고, 잘려서 중복된 짧은 조각은 dedupe로 걸러낸다."""
    resolved: list[Medication] = []
    auto_created_ids: set[int] = set()

    drug_like_words = {w.lstrip("*").strip() for w in raw_text_list if _looks_like_drug_name(w)}
    for name in _dedupe_drug_names(drug_like_words):
        existing = await repo.search_medication_by_name(db_session, name)
        exact = next((m for m in existing if m.medication_name == name), None)
        if exact:
            if exact.id not in seen_ids:
                seen_ids.add(exact.id)
                resolved.append(exact)
            continue

        new_med, is_auto_dummy = await _create_medication_for_unmatched_name(db_session, repo, name)
        seen_ids.add(new_med.id)
        if is_auto_dummy:
            auto_created_ids.add(new_med.id)
        resolved.append(new_med)

    return resolved, auto_created_ids


async def _match_or_create_medications(
    db_session: AsyncSession, repo: MedicationRepository, raw_text_list: list[str]
) -> tuple[list[Medication], set[int]]:
    """OCR 텍스트에서 약품명으로 보이는 조각을 마스터 DB와 매칭하고, 없으면 새로 생성한다.
    반환값: (매칭/생성된 약품 목록, 이번에 새로 생성된 약품의 id 집합)"""
    matched_meds: list[Medication] = []
    auto_created_ids: set[int] = set()
    seen_ids: set[int] = set()

    if raw_text_list:
        matched_meds.extend(await _match_existing_by_word(db_session, repo, raw_text_list, seen_ids))
        resolved, auto_created_ids = await _resolve_or_create_drug_like_names(db_session, repo, raw_text_list, seen_ids)
        matched_meds.extend(resolved)

    # 그래도 후보가 하나도 없으면(약품명으로 보이는 텍스트조차 없었던 경우)
    # 마스터 DB 상위 몇 개를 참고용으로 보여준다 — 이 경우엔 수동 검색으로의 전환을 기대한다.
    if not matched_meds:
        all_meds = await repo.search_medication_by_name(db_session, "")
        matched_meds = all_meds[:3]

    return matched_meds, auto_created_ids


async def _call_clova_ocr(file_bytes: bytes, file_name: str) -> list[str]:
    """CLOVA OCR을 호출해 인식된 텍스트 조각 목록을 반환한다. 호출 실패/빈 응답이면 빈 리스트.
    호출 전 `_clova_configured()`로 키/URL이 설정됐음을 확인했다는 전제 하에만 호출된다."""
    assert CLOVA_OCR_SECRET_KEY is not None
    assert CLOVA_OCR_INVOKE_URL is not None
    raw_text_list: list[str] = []
    try:
        base64_data = base64.b64encode(file_bytes).decode("utf-8")
        file_format = file_name.split(".")[-1].lower()
        if file_format not in ["jpg", "jpeg", "png", "pdf"]:
            file_format = "jpg"

        payload = {
            "images": [{"format": file_format, "name": "medication_doc", "data": base64_data}],
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "version": "V2",
        }
        headers = {"X-OCR-SECRET": CLOVA_OCR_SECRET_KEY, "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(CLOVA_OCR_INVOKE_URL, json=payload, headers=headers, timeout=10.0)
            if response.status_code == 200:
                res_json = response.json()
                images = res_json.get("images", [])
                if images:
                    fields = images[0].get("fields", [])
                    raw_text_list = [field.get("inferText", "") for field in fields if field.get("inferText")]
    except Exception:
        pass
    return raw_text_list


def _clova_configured() -> bool:
    return bool(CLOVA_OCR_SECRET_KEY and CLOVA_OCR_INVOKE_URL and not CLOVA_OCR_SECRET_KEY.startswith("your_"))


async def _resolve_ocr_raw_text(file_bytes: bytes, file_name: str, dummy_mode: bool) -> tuple[list[str], bool]:
    """OCR 인식 텍스트 목록과 "더미 폴백이 사용됐는지"를 반환한다(T-MED-3).

    dummy_mode가 명시적으로 요청됐거나, 실제 OCR 호출이 불가능/실패/빈 응답이면
    결정적인 더미 텍스트로 폴백해 등록 자체가 막히지 않게 한다."""
    if dummy_mode:
        return list(DUMMY_OCR_RAW_TEXT), True

    raw_text_list: list[str] = []
    if _clova_configured():
        raw_text_list = await _call_clova_ocr(file_bytes, file_name)

    if not raw_text_list:
        return list(DUMMY_OCR_RAW_TEXT), True
    return raw_text_list, False


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
    raw_text_list, used_dummy_fallback = await _resolve_ocr_raw_text(file_bytes, file_name, dummy_mode)

    # 3. OCR 파싱 결과 분석 & DB 매칭
    candidates = []
    extracted_fields = {
        "dosage": "1정",
        "times": ["09:00", "13:00", "19:00"],
        "duration": "3일",
        "instruction": "식후 30분 복용",
        "ocr_raw_text": " ".join(raw_text_list),
        "dummy_mode": used_dummy_fallback,
    }

    matched_meds, auto_created_ids = await _match_or_create_medications(db_session, repo, raw_text_list)

    for med in matched_meds:
        if med.id in auto_created_ids:
            match_rate = 0.5  # 마스터 DB에 없어 새로 생성된 미검증 약품
        else:
            match_rate = 1.0 if "타이레놀" in med.medication_name else 0.85
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
