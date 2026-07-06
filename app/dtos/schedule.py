import datetime

from app.dtos.base import BaseSerializerModel


class ScheduleCreate(BaseSerializerModel):
    medication_id: int
    record_id: int | None = None
    card_alias: str | None = None
    frequency_type: str = "DAILY"  # DAILY / WEEKLY
    target_day_of_week: str | None = None
    alarm_time: str  # "HH:MM:SS" or "HH:MM"


class ScheduleResponse(BaseSerializerModel):
    id: int
    medication_id: int
    record_id: int | None = None
    card_alias: str | None = None
    frequency_type: str
    target_day_of_week: str | None = None
    alarm_time: datetime.time
    is_active: bool
