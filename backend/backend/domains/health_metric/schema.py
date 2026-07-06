# backend/domains/health_metric/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class HealthMetricCreate(BaseModel):
    weight: Optional[float] = None
    height: Optional[float] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    blood_glucose: Optional[int] = None
    recorded_at: Optional[datetime.datetime] = None


class HealthMetricResponse(BaseModel):
    metric_id: int
    weight: Optional[float] = None
    height: Optional[float] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    blood_glucose: Optional[int] = None
    source: str
    recorded_at: datetime.datetime
