from fastapi import HTTPException, status

from app.dtos.drug_interaction import AnalyzeRequest
from app.models.drug_interactions import DrugFoodInteraction
from app.models.food_intakes import FoodIntakeLog
from app.models.schedules import MedicationSchedule
from app.models.users import User


class DrugInteractionService:
    async def get_medication_interactions(self, medication_id: int) -> list[DrugFoodInteraction]:
        return await DrugFoodInteraction.filter(medication_id=medication_id).all()

    async def analyze_food_interaction(self, user: User, data: AnalyzeRequest) -> dict:
        food_log = await FoodIntakeLog.get_or_none(id=data.food_log_id, user=user)
        if not food_log:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="식사 기록을 찾을 수 없습니다.")

        # 활성화된 복약 스케줄의 약품 ID들 수집
        active_schedules = await MedicationSchedule.filter(user=user, is_active=True).all()
        active_medication_ids = {s.medication_id for s in active_schedules}

        if not active_medication_ids:
            return {
                "food_log_id": food_log.id,
                "matched_rules": [],
                "interaction_notes": "현재 등록된 복약 스케줄이 없어 분석할 상호작용이 없습니다.",
            }

        # 관련 상호작용 규칙 조회
        rules = await DrugFoodInteraction.filter(medication_id__in=list(active_medication_ids)).all()
        if not rules:
            return {
                "food_log_id": food_log.id,
                "matched_rules": [],
                "interaction_notes": "해당 식사와 관련된 약물-음식 상호작용 규칙이 발견되지 않았습니다.",
            }

        notes = " ".join(r.guidance_text or "" for r in rules)
        return {"food_log_id": food_log.id, "matched_rules": [r.id for r in rules], "interaction_notes": notes}
