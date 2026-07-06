# backend/domains/schedule/router.py
# API_Specification_v3.pdf [M6] 복약 알림 일정 등록/조회
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import MedicationSchedule
from .schema import ScheduleCreate, ScheduleResponse

router = APIRouter()


def _parse_time(value: str) -> datetime.time:
    fmt = "%H:%M:%S" if value.count(":") == 2 else "%H:%M"
    return datetime.datetime.strptime(value, fmt).time()


def _to_response(s: MedicationSchedule) -> dict:
    return {
        "schedule_id": s.id,
        "medication_id": s.medication_id,
        "record_id": s.record_id,
        "card_alias": s.card_alias,
        "frequency_type": s.frequency_type,
        "target_day_of_week": s.target_day_of_week,
        "alarm_time": s.alarm_time.strftime("%H:%M:%S"),
        "is_active": s.is_active,
    }


@router.post("", response_model=ScheduleResponse, status_code=201, summary="복약 알림 일정 등록")
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_schedule = MedicationSchedule(
        user_id=current_user.id,
        medication_id=data.medication_id,
        record_id=data.record_id,
        card_alias=data.card_alias,
        frequency_type=data.frequency_type,
        target_day_of_week=data.target_day_of_week,
        alarm_time=_parse_time(data.alarm_time),
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)
    return _to_response(new_schedule)


@router.get("", response_model=list[ScheduleResponse], summary="복약 알림 일정 조회")
def get_schedules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    schedules = db.query(MedicationSchedule).filter(MedicationSchedule.user_id == current_user.id).all()
    return [_to_response(s) for s in schedules]
