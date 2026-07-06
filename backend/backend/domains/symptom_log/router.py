# backend/domains/symptom_log/router.py
# API_Specification_v3.pdf [M9] 증상 기록 및 심각도 등록
# TODO(조원 구현): 지금은 등록(POST)만 있습니다. 목록 조회 등은 필요에 맞게 추가해주세요.
import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import SymptomLog
from .schema import SymptomLogCreate, SymptomLogResponse

router = APIRouter()


@router.post("", response_model=SymptomLogResponse, status_code=201, summary="증상 기록 및 심각도 등록")
def create_symptom_log(data: SymptomLogCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_log = SymptomLog(
        user_id=current_user.id,
        symptom_notes=data.symptom_notes,
        severity_level=data.severity_level,
        recorded_at=data.recorded_at or datetime.datetime.utcnow(),
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {
        "symptom_id": new_log.id,
        "symptom_notes": new_log.symptom_notes,
        "severity_level": new_log.severity_level,
        "recorded_at": new_log.recorded_at,
    }
