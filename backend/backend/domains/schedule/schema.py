# backend/domains/schedule/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class ScheduleCreate(BaseModel):
    medication_id: int
    record_id: Optional[int] = None
    card_alias: Optional[str] = None
    frequency_type: str = "DAILY"  # DAILY / WEEKLY
    target_day_of_week: Optional[str] = None
    alarm_time: str  # "HH:MM:SS"


class ScheduleResponse(BaseModel):
    schedule_id: int
    medication_id: int
    record_id: Optional[int] = None
    card_alias: Optional[str] = None
    frequency_type: str
    target_day_of_week: Optional[str] = None
    alarm_time: str
    is_active: bool
