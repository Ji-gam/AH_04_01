# backend/domains/generated_guide/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class GuideCreate(BaseModel):
    record_id: Optional[int] = None
    guide_type: str = "MEDICATION"


class GuideTaskAccepted(BaseModel):
    task_id: str
    status: str
    created_at: datetime.datetime


class GuideResponse(BaseModel):
    guide_id: int
    user_id: int
    record_id: Optional[int] = None
    guide_type: str
    content: Optional[str] = None
    created_at: datetime.datetime
