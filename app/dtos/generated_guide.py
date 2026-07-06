import datetime

from app.dtos.base import BaseSerializerModel


class GuideCreate(BaseSerializerModel):
    record_id: int | None = None
    guide_type: str = "MEDICATION"


class GuideTaskAccepted(BaseSerializerModel):
    task_id: str
    status: str
    created_at: datetime.datetime


class GuideResponse(BaseSerializerModel):
    id: int
    user_id: int
    record_id: int | None = None
    guide_type: str
    content: str | None = None
    created_at: datetime.datetime
