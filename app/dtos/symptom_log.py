import datetime

from app.dtos.base import BaseSerializerModel


class SymptomLogCreate(BaseSerializerModel):
    symptom_notes: str
    severity_level: int = 1
    recorded_at: datetime.datetime | None = None


class SymptomLogResponse(BaseSerializerModel):
    id: int
    symptom_notes: str
    severity_level: int
    recorded_at: datetime.datetime
