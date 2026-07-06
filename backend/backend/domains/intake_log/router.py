# backend/domains/intake_log/router.py
# API_Specification_v3.pdf [M6] 복약 수행 이력 조회(쿼리파라미터), 완료 체크(+잔여량 자동차감)
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from backend.domains.schedule.model import MedicationSchedule
from backend.domains.record.model import RecordMedicationMapping
from .model import IntakeLog
from .schema import IntakeLogResponse, IntakeLogUpdate, IntakeLogUpdateResponse

router = APIRouter()


@router.get("", response_model=list[IntakeLogResponse], summary="복약 수행 이력 조회 (캘린더 뷰 연계)")
def get_intake_logs(
    start_date: Optional[datetime.date] = Query(None, description="조회 시작일 (YYYY-MM-DD)"),
    end_date: Optional[datetime.date] = Query(None, description="조회 종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(IntakeLog)
        .join(MedicationSchedule, IntakeLog.schedule_id == MedicationSchedule.id)
        .filter(MedicationSchedule.user_id == current_user.id)
    )
    if start_date:
        query = query.filter(IntakeLog.planned_date >= start_date)
    if end_date:
        query = query.filter(IntakeLog.planned_date <= end_date)

    logs = query.all()
    return [
        {
            "log_id": log.id,
            "schedule_id": log.schedule_id,
            "card_alias": log.schedule.card_alias if log.schedule else None,
            "planned_date": log.planned_date,
            "actual_take_time": log.actual_take_time,
            "status": log.status,
            "verification_media_url": log.verification_media_url,
        }
        for log in logs
    ]


def _decrement_remaining_quantity(schedule: MedicationSchedule, db: Session) -> Optional[int]:
    """복약 완료 체크 시, 해당 스케줄과 연결된 처방 매핑의 잔여량을 차감합니다.
    (device_type이 MULTI_DOSE_PEN이면 dosage_per_take 만큼, 아니면 1개 차감)
    """
    if not schedule.record_id:
        return None
    mapping = (
        db.query(RecordMedicationMapping)
        .filter(
            RecordMedicationMapping.record_id == schedule.record_id,
            RecordMedicationMapping.medication_id == schedule.medication_id,
        )
        .first()
    )
    if not mapping or mapping.remaining_quantity is None:
        return None

    if mapping.device_type == "MULTI_DOSE_PEN":
        try:
            decrement = int("".join(filter(str.isdigit, mapping.dosage_per_take or "1")) or 1)
        except ValueError:
            decrement = 1
    else:
        decrement = 1

    mapping.remaining_quantity = max(0, mapping.remaining_quantity - decrement)
    db.commit()
    return mapping.remaining_quantity


@router.patch("/{log_id}", response_model=IntakeLogUpdateResponse, summary="복약 완료 수행 체크")
def update_intake_log(
    log_id: int,
    data: IntakeLogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log = (
        db.query(IntakeLog)
        .join(MedicationSchedule, IntakeLog.schedule_id == MedicationSchedule.id)
        .filter(IntakeLog.id == log_id, MedicationSchedule.user_id == current_user.id)
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="복약 수행 기록을 찾을 수 없습니다.")

    log.status = data.status
    log.actual_take_time = data.actual_take_time or datetime.datetime.utcnow()
    log.verification_media_url = data.verification_media_url
    db.commit()
    db.refresh(log)

    remaining_after = None
    if data.status == "COMPLETED":
        remaining_after = _decrement_remaining_quantity(log.schedule, db)

    return {
        "log_id": log.id,
        "status": log.status,
        "actual_take_time": log.actual_take_time,
        "remaining_quantity_after": remaining_after,
    }
