# backend/domains/drug_food_interaction/router.py
# API_Specification_v3.pdf [M8] 약물-음식 상호작용 규칙 조회, 통합 위험도 분석(RAG)
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from backend.domains.food_intake.model import FoodIntakeLog
from backend.domains.schedule.model import MedicationSchedule
from .model import DrugFoodInteraction
from .schema import InteractionResponse, AnalyzeRequest, AnalyzeResponse

router = APIRouter()


@router.get("", response_model=list[InteractionResponse], summary="특정 의약품의 상호작용 규칙 조회")
def get_interactions(
    medication_id: int = Query(..., description="조회할 의약품 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rules = db.query(DrugFoodInteraction).filter(DrugFoodInteraction.medication_id == medication_id).all()
    return [
        {
            "interaction_id": r.id,
            "medication_id": r.medication_id,
            "substance_name": r.substance_name,
            "risk_level": r.risk_level,
            "guidance_text": r.guidance_text,
        }
        for r in rules
    ]


@router.post("/analyze", response_model=AnalyzeResponse, summary="식사-투약 통합 위험도 분석 [규칙기반 임시 구현, LLM RAG 미연동]")
def analyze_interaction(data: AnalyzeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # ⚠️ [단순화 안내] 실제로는 DRUG_FOOD_INTERACTIONS를 RAG 컨텍스트로 주입한 LLM이
    # 자연어 경고문을 생성해야 하지만(v3 명세 M8-2), 지금은 LLM 연동 전이라
    # 규칙을 그대로 이어붙이는 방식으로만 동작합니다. 나중에 LLM 연동 시 이 함수 내부만 교체하면 됩니다.
    food_log = db.query(FoodIntakeLog).filter(
        FoodIntakeLog.id == data.food_log_id, FoodIntakeLog.user_id == current_user.id
    ).first()
    if not food_log:
        raise HTTPException(status_code=404, detail="식사 기록을 찾을 수 없습니다.")

    active_medication_ids = {
        s.medication_id
        for s in db.query(MedicationSchedule).filter(
            MedicationSchedule.user_id == current_user.id, MedicationSchedule.is_active == True
        )
    }
    if not active_medication_ids:
        return {"food_log_id": food_log.id, "matched_rules": [], "interaction_notes": "현재 등록된 복약 스케줄이 없어 분석할 상호작용이 없습니다."}

    rules = db.query(DrugFoodInteraction).filter(DrugFoodInteraction.medication_id.in_(active_medication_ids)).all()
    if not rules:
        return {"food_log_id": food_log.id, "matched_rules": [], "interaction_notes": "해당 식사와 관련된 약물-음식 상호작용 규칙이 발견되지 않았습니다."}

    notes = " ".join(r.guidance_text or "" for r in rules)
    return {"food_log_id": food_log.id, "matched_rules": [r.id for r in rules], "interaction_notes": notes}
