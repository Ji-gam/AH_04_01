import uuid
from typing import Any

from fastapi import HTTPException, status

from app.dtos.record import RecordCreate
from app.models.medications import Medication
from app.models.records import MedicalRecord, OcrTask, RecordMedicationMapping
from app.models.users import User


class RecordService:
    async def create_ocr_task(self, user: User, filename: str) -> OcrTask:
        task_id = f"ocr_task_{uuid.uuid4().hex[:12]}"

        fake_image_url = f"https://healthai-storage.example.com/records/{user.id}/{filename}"
        fake_ocr_result: dict[str, Any] = {
            "hospital_name": "미인식(수동 확인 필요)",
            "pharmacy_name": None,
            "diagnosis_name": None,
            "medications_detected": [],
        }

        task = await OcrTask.create(
            task_id=task_id,
            status="SUCCESS",  # 임시 스텁 즉시 완료
            image_s3_url=fake_image_url,
            ocr_raw_json=fake_ocr_result,
        )
        return task

    async def get_ocr_task(self, task_id: str) -> OcrTask:
        task = await OcrTask.get_or_none(task_id=task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 task_id를 찾을 수 없습니다.")
        return task

    def _calc_initial_remaining(self, med: dict[str, Any]) -> int:
        device_type = med.get("device_type")
        if device_type == "MULTI_DOSE_PEN":
            return med.get("total_clicks_or_doses") or 0
        return med.get("total_prescribed_quantity") or 1

    async def create_medical_record(self, user: User, data: RecordCreate) -> MedicalRecord:
        # MedicalRecord 생성
        record_data = data.model_dump(exclude={"medications"})
        new_record = await MedicalRecord.create(user=user, **record_data)

        # Medication Mapping 생성
        for med in data.medications:
            medication = await Medication.get_or_none(id=med.medication_id)
            if not medication:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"medication_id={med.medication_id} 를 찾을 수 없습니다.",
                )

            med_dict = med.model_dump()
            await RecordMedicationMapping.create(
                record=new_record,
                medication=medication,
                **med_dict,
                remaining_quantity=self._calc_initial_remaining(med_dict),
            )

        return new_record

    async def get_medical_record_detail(self, user: User, record_id: int) -> MedicalRecord:
        record = await MedicalRecord.get_or_none(id=record_id, user=user).prefetch_related("medications__medication")
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="진료 기록을 찾을 수 없거나 접근 권한이 없습니다."
            )
        return record
