# backend/domains/appointment/router.py
# API_Specification_v3.pdf [M9] 병원 예약 및 의사 등록
# TODO(조원 구현): 지금은 등록(POST)만 있습니다. 목록/상세 조회, 예약 취소 등은 필요에 맞게 추가해주세요.
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import Appointment
from .schema import AppointmentCreate, AppointmentResponse

router = APIRouter()


@router.post("", response_model=AppointmentResponse, status_code=201, summary="병원 예약 및 의사 등록")
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_appt = Appointment(user_id=current_user.id, **data.model_dump())
    db.add(new_appt)
    db.commit()
    db.refresh(new_appt)
    return {"appointment_id": new_appt.id, **data.model_dump()}
