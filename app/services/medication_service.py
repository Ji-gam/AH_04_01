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
    MedicationScheduleCreateRequest,
    MedicationScheduleResponse,
    RecognitionCandidate,
    RecognitionConfirmResult,
    RecognitionJobCreateResult,
    RecognitionResult,
)
from app.models.medication_model import Medication, MedicationRecognitionJob, MedicationSchedule
from app.repositories.medication_repository import MedicationRepository

CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")

# 약품명 후보로 볼 만한 OCR 텍스트 블록 판별 기준.
# "정"/"캡슐" 같은 제형 접미사만으로는 "환자정보", "서방정"(잘린 조각) 등 일반 텍스트도
# 걸려버려서, 반드시 (a) 용량 숫자+단위(mg/g/ml)가 붙어 있거나 (b) 처방전 약품 목록에서
# 흔히 쓰이는 "*" 불릿 표시가 있는 경우만 후보로 인정한다.
_KOREAN_TOKEN_PATTERN = re.compile(r"[가-힣]{2,}")
_DOSAGE_PATTERN = re.compile(r"\d+(mg|g|ml)", re.IGNORECASE)
_MIN_DRUG_NAME_LEN = 5


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


async def _match_or_create_medications(
    db_session: AsyncSession, repo: MedicationRepository, raw_text_list: list[str]
) -> tuple[list[Medication], set[int]]:
    """OCR 텍스트에서 약품명으로 보이는 조각을 마스터 DB와 매칭하고, 없으면 새로 생성한다.
    반환값: (매칭/생성된 약품 목록, 이번에 새로 생성된 약품의 id 집합)"""
    matched_meds: list[Medication] = []
    auto_created_ids: set[int] = set()
    seen_ids: set[int] = set()

    if raw_text_list:
        # 짧은 숫자/용량 조각("100mg" 등)까지 LIKE 검색에 넣으면 우연히 다른 약의 용량과
        # 겹쳐 엉뚱한 약이 매칭되므로(예: "100mg"이 "아스피린정 100mg"에 우연히 포함),
        # 약품명처럼 보이는 온전한 단어에 대해서만 실제 DB 매칭을 시도한다.
        for word in raw_text_list:
            if not _looks_like_drug_name(word):
                continue
            stripped = word.lstrip("*").strip()
            meds = await repo.search_medication_by_name(db_session, stripped)
            for med in meds:
                if med.id not in seen_ids:
                    seen_ids.add(med.id)
                    matched_meds.append(med)

        # 마스터 DB에 없는 약이어도, OCR 텍스트가 약품명 형태(용량단위 또는 "*" 불릿 표시)로
        # 보이면 등록이 막히지 않도록 새 마스터 레코드를 즉석에서 생성해 후보로 포함시킨다.
        # "*"는 정규화 과정에서 제거하고, 잘려서 중복된 짧은 조각은 dedupe로 걸러낸다.
        drug_like_words = {w.lstrip("*").strip() for w in raw_text_list if _looks_like_drug_name(w)}
        for name in _dedupe_drug_names(drug_like_words):
            existing = await repo.search_medication_by_name(db_session, name)
            exact = next((m for m in existing if m.medication_name == name), None)
            if exact:
                if exact.id not in seen_ids:
                    seen_ids.add(exact.id)
                    matched_meds.append(exact)
                continue

            new_med = Medication(medication_name=name, standard_code=f"AUTO_{uuid.uuid4().hex[:10].upper()}")
            new_med = await repo.create_medication(db_session, new_med)
            seen_ids.add(new_med.id)
            auto_created_ids.add(new_med.id)
            matched_meds.append(new_med)

    # 그래도 후보가 하나도 없으면(약품명으로 보이는 텍스트조차 없었던 경우)
    # 마스터 DB 상위 몇 개를 참고용으로 보여준다 — 이 경우엔 수동 검색으로의 전환을 기대한다.
    if not matched_meds:
        all_meds = await repo.search_medication_by_name(db_session, "")
        matched_meds = all_meds[:3]

    return matched_meds, auto_created_ids


async def _execute_ocr_logic(
    db_session: AsyncSession, job_id: str, source_type: str, file_bytes: bytes, file_name: str
):
    repo = MedicationRepository()

    # 1. 상태를 processing으로 변경
    await repo.update_recognition_job(db_session, job_id, "processing")

    raw_text_list = []

    # 2. CLOVA OCR API 호출 (설정되어 있고 실제 호출 성공 시)
    if CLOVA_OCR_SECRET_KEY and CLOVA_OCR_INVOKE_URL and not CLOVA_OCR_SECRET_KEY.startswith("your_"):
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
                        for field in fields:
                            text = field.get("inferText", "")
                            if text:
                                raw_text_list.append(text)
        except Exception:
            pass

    # 3. OCR 파싱 결과 분석 & DB 매칭
    candidates = []
    extracted_fields = {
        "dosage": "1정",
        "times": ["09:00", "13:00", "19:00"],
        "duration": "3일",
        "instruction": "식후 30분 복용",
        "ocr_raw_text": " ".join(raw_text_list) if raw_text_list else "MOCK OCR TEXT 타이레놀",
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
    job_id: str, source_type: str, file_bytes: bytes, file_name: str = "image.jpg", session: AsyncSession | None = None
):
    """
    비동기 OCR 및 약품 매칭 백그라운드 태스크.
    session이 제공되면 해당 session을 재사용하고(테스트 환경용), 그렇지 않으면 자체 세션을 생성합니다.
    """
    if session is not None:
        await _execute_ocr_logic(session, job_id, source_type, file_bytes, file_name)
    else:
        async with AsyncSessionLocal() as db_session:
            await _execute_ocr_logic(db_session, job_id, source_type, file_bytes, file_name)
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
        background_tasks.add_task(run_ocr_task, job_id, source_type, file_bytes, file_name, session=session)

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
            )
            for s in schedules
        ]

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

        schedule = MedicationSchedule(profile_id=profile_id, medication_id=med.id, times=req.times)
        await self._repository.create_schedule(session, schedule)

        return MedicationScheduleResponse(
            id=schedule.id, medication_id=schedule.medication_id, drug_name=med.medication_name, times=schedule.times
        )

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
