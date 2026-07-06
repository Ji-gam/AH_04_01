import datetime

from app.dtos.base import BaseSerializerModel


class IntakeLogResponse(BaseSerializerModel):
    id: int
    schedule_id: int
    card_alias: str | None = None
    planned_date: datetime.date
    actual_take_time: datetime.datetime | None = None
    status: str
    verification_media_url: str | None = None


class IntakeLogUpdate(BaseSerializerModel):
    status: str  # COMPLETED / MISSED
    actual_take_time: datetime.datetime | None = None
    verification_media_url: str | None = None


class IntakeLogUpdateResponse(BaseSerializerModel):
    id: int
    status: str
    actual_take_time: datetime.datetime | None = None
    remaining_quantity_after: int | None = None
