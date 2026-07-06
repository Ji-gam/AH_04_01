# backend/domains/symptom_log/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class SymptomLogCreate(BaseModel):
    symptom_notes: str
    severity_level: int = 1
    recorded_at: Optional[datetime.datetime] = None


class SymptomLogResponse(BaseModel):
    symptom_id: int
    symptom_notes: str
    severity_level: int
    recorded_at: datetime.datetime
