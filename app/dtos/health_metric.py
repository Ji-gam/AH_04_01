import datetime

from app.dtos.base import BaseSerializerModel


class HealthMetricCreate(BaseSerializerModel):
    weight: float | None = None
    height: float | None = None
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    blood_glucose: int | None = None
    recorded_at: datetime.datetime | None = None


class HealthMetricResponse(BaseSerializerModel):
    id: int
    weight: float | None = None
    height: float | None = None
    blood_pressure_systolic: int | None = None
    blood_pressure_diastolic: int | None = None
    blood_glucose: int | None = None
    source: str
    recorded_at: datetime.datetime
