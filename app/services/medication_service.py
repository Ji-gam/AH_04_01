import os
import uuid
import time
import base64
import httpx
from fastapi import HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import AsyncSessionLocal
from app.models.medication_model import MedicationSchedule, MedicationRecognitionJob, Medication
from app.repositories.medication_repository import MedicationRepository
from app.dtos.medication_dto import (
    RecognitionJobCreateResult,
    RecognitionResult,
    RecognitionCandidate,
    RecognitionConfirmResult,
    MedicationScheduleResponse,
    MedicationScheduleCreateRequest,
    GuideCard
)

CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")


async def _execute_ocr_logic(
    db_session: AsyncSession,
    job_id: str,
    source_type: str,
    file_bytes: bytes,
    file_name: str
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
                "images": [
                    {
                        "format": file_format,
                        "name": "medication_doc",
                        "data": base64_data
                    }
                ],
                "requestId": str(uuid.uuid4()),
                "timestamp": int(time.time() * 1000),
                "version": "V2"
            }
            
            headers = {
                "X-OCR-SECRET": CLOVA_OCR_SECRET_KEY,
                "Content-Type": "application/json"
            }
            
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
        "ocr_raw_text": " ".join(raw_text_list) if raw_text_list else "MOCK OCR TEXT 타이레놀"
    }

    matched_meds = []
    if raw_text_list:
        seen_ids = set()
        for word in raw_text_list:
            if len(word) < 2:
                continue
            meds = await repo.search_medication_by_name(db_session, word)
            for med in meds:
                if med.id not in seen_ids:
                    seen_ids.add(med.id)
                    matched_meds.append(med)

    # 검색된 약품이 없다면 더미 데이터베이스를 매칭하여 후보 제공
    if not matched_meds:
        all_meds = await repo.search_medication_by_name(db_session, "")
        matched_meds = all_meds[:3]

    for med in matched_meds:
        match_rate = 1.0 if "타이레놀" in med.medication_name else 0.85
        candidates.append({
            "drug_name": med.medication_name,
            "match_rate": match_rate,
            "drug_code": med.standard_code or f"CODE_{med.id}"
        })

    candidates.sort(key=lambda x: x["match_rate"], reverse=True)

    # 4. 최종 상태 업데이트
    status = "done" if candidates else "failed"
    await repo.update_recognition_job(
        db_session,
        job_id,
        status=status,
        candidates=candidates,
        extracted_fields=extracted_fields
    )


async def run_ocr_task(
    job_id: str,
    source_type: str,
    file_bytes: bytes,
    file_name: str = "image.jpg",
    session: AsyncSession | None = None
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
        background_tasks: BackgroundTasks
    ) -> RecognitionJobCreateResult:
        if source_type not in ["pill_photo", "prescription", "medical_record", "medication_guide"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 source_type 입니다."
            )

        job_id = str(uuid.uuid4())
        job = MedicationRecognitionJob(
            id=job_id,
            profile_id=profile_id,
            status="pending",
            source_type=source_type,
            candidates=[],
            extracted_fields={}
        )
        await self._repository.create_recognition_job(session, job)

        # 백그라운드 태스크 등록
        background_tasks.add_task(run_ocr_task, job_id, source_type, file_bytes, file_name, session=session)

        return RecognitionJobCreateResult(job_id=job_id, status="pending")

    async def get_recognition_job(
        self,
        session: AsyncSession,
        job_id: str,
        profile_id: int
    ) -> RecognitionResult:
        job = await self._repository.get_recognition_job(session, job_id)
        if not job or job.profile_id != profile_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 작업(Job)을 찾을 수 없습니다."
            )

        candidates = [
            RecognitionCandidate(
                drug_name=c["drug_name"],
                match_rate=c["match_rate"],
                drug_code=c["drug_code"]
            )
            for c in (job.candidates or [])
        ]

        return RecognitionResult(
            job_id=job.id,
            status=job.status,
            source_type=job.source_type,
            candidates=candidates,
            extracted_fields=job.extracted_fields
        )

    async def confirm_recognition_job(
        self,
        session: AsyncSession,
        job_id: str,
        profile_id: int,
        selected_candidate_drug_code: str | None,
        confirmed_fields: dict | None
    ) -> RecognitionConfirmResult:
        job = await self._repository.get_recognition_job(session, job_id)
        if not job or job.profile_id != profile_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 작업(Job)을 찾을 수 없습니다."
            )

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
                    profile_id=profile_id,
                    medication_id=med.id,
                    times=times,
                    source_job_id=job_id
                )
                await self._repository.create_schedule(session, schedule)

        # 12, 13번: 추후 확장을 위한 구조 설계
        guide_cards = []
        if selected_candidate_drug_code:
            guide_cards.append(
                GuideCard(
                    title="복약 주의사항 안내",
                    content="등록하신 약품의 부작용 및 상호작용 정보(DUR)는 추후 연동될 예정입니다.",
                    severity="info"
                )
            )

        return RecognitionConfirmResult(status="confirmed", guide_cards=guide_cards)

    async def list_schedules(
        self,
        session: AsyncSession,
        profile_id: int
    ) -> list[MedicationScheduleResponse]:
        schedules = await self._repository.list_schedules_by_profile(session, profile_id)
        return [
            MedicationScheduleResponse(
                id=s.id,
                medication_id=s.medication_id,
                drug_name=s.medication.medication_name,
                times=s.times,
                source_job_id=s.source_job_id
            )
            for s in schedules
        ]

    async def create_manual_schedule(
        self,
        session: AsyncSession,
        profile_id: int,
        req: MedicationScheduleCreateRequest
    ) -> MedicationScheduleResponse:
        med = await self._repository.get_medication_by_code(session, req.drug_code)
        if not med:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="해당 약품 정보를 찾을 수 없습니다."
            )

        schedule = MedicationSchedule(
            profile_id=profile_id,
            medication_id=med.id,
            times=req.times
        )
        await self._repository.create_schedule(session, schedule)

        return MedicationScheduleResponse(
            id=schedule.id,
            medication_id=schedule.medication_id,
            drug_name=med.medication_name,
            times=schedule.times
        )

    async def search_medications(self, session: AsyncSession, query: str) -> list[dict]:
        meds = await self._repository.search_medication_by_name(session, query)
        return [
            {
                "id": m.id,
                "standard_code": m.standard_code,
                "medication_name": m.medication_name,
                "form_type": m.form_type
            }
            for m in meds
        ]
