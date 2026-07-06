# backend/domains/emergency_card/router.py
# API_Specification_v3.pdf [M4] 응급 의료 카드 조회/등록(Upsert)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import EmergencyCard
from .schema import EmergencyCardUpsert, EmergencyCardResponse

router = APIRouter()


def _to_response(card: EmergencyCard) -> dict:
    return {
        "card_id": card.id,
        "user_id": card.user_id,
        "blood_type": card.blood_type,
        "food_allergies": card.food_allergies,
        "medication_allergies": card.medication_allergies,
        "past_history": card.past_history,
        "present_history": card.present_history,
        "family_history": card.family_history,
        "emergency_contacts": card.emergency_contacts,
    }


@router.get("", response_model=EmergencyCardResponse, summary="응급 의료 카드 조회")
def get_emergency_card(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = db.query(EmergencyCard).filter(EmergencyCard.user_id == current_user.id).first()
    if not card:
        raise HTTPException(status_code=404, detail="등록된 응급 의료 카드가 없습니다.")
    return _to_response(card)


@router.put("", response_model=EmergencyCardResponse, summary="응급 의료 카드 등록/수정 (Upsert)")
def upsert_emergency_card(data: EmergencyCardUpsert, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    card = db.query(EmergencyCard).filter(EmergencyCard.user_id == current_user.id).first()
    if card:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(card, field, value)
    else:
        card = EmergencyCard(user_id=current_user.id, **data.model_dump())
        db.add(card)
    db.commit()
    db.refresh(card)
    return _to_response(card)
