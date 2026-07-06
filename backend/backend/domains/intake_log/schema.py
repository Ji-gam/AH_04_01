# backend/domains/intake_log/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class IntakeLogResponse(BaseModel):
    log_id: int
    schedule_id: int
    card_alias: Optional[str] = None
    planned_date: datetime.date
    actual_take_time: Optional[datetime.datetime] = None
    status: str
    verification_media_url: Optional[str] = None


class IntakeLogUpdate(BaseModel):
    status: str  # COMPLETED / MISSED
    actual_take_time: Optional[datetime.datetime] = None
    verification_media_url: Optional[str] = None


class IntakeLogUpdateResponse(BaseModel):
    log_id: int
    status: str
    actual_take_time: Optional[datetime.datetime] = None
    remaining_quantity_after: Optional[int] = None
