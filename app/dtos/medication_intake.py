from typing import Literal

from pydantic import BaseModel


class IntakeToggleRequest(BaseModel):
    source_type: Literal["medication_schedule", "notification_schedule"]
    source_id: int
    scheduled_time: str  # "HH:MM"
    date: str  # "YYYY-MM-DD"
    checked: bool


class IntakeRecordResult(BaseModel):
    source_type: str
    source_id: int
    scheduled_time: str


class IntakeDailyCountResult(BaseModel):
    date: str
    checked_count: int
