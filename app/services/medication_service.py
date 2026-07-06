from fastapi import HTTPException, status

from app.models.medications import Medication


class MedicationService:
    async def get_medication_by_id(self, medication_id: int) -> Medication:
        med = await Medication.get_or_none(id=medication_id)
        if not med:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="의약품 정보를 찾을 수 없습니다.")
        return med
