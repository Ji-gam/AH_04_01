# backend/domains/health_metric/router.py
# API_Specification_v3.pdf [M9] 건강 생체 지표 등록
# TODO(조원 구현): 지금은 등록(POST)만 있습니다. 조회 API, 기간별 추이 등은 필요에 맞게 추가해주세요.
import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import HealthMetric
from .schema import HealthMetricCreate, HealthMetricResponse

router = APIRouter()


@router.post("", response_model=HealthMetricResponse, status_code=201, summary="건강 생체 지표 등록")
def create_health_metric(data: HealthMetricCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_metric = HealthMetric(
        user_id=current_user.id,
        **data.model_dump(exclude={"recorded_at"}),
        recorded_at=data.recorded_at or datetime.datetime.utcnow(),
    )
    db.add(new_metric)
    db.commit()
    db.refresh(new_metric)
    return {
        "metric_id": new_metric.id,
        "weight": new_metric.weight,
        "height": new_metric.height,
        "blood_pressure_systolic": new_metric.blood_pressure_systolic,
        "blood_pressure_diastolic": new_metric.blood_pressure_diastolic,
        "blood_glucose": new_metric.blood_glucose,
        "source": new_metric.source,
        "recorded_at": new_metric.recorded_at,
    }
