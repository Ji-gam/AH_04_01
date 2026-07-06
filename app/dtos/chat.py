import datetime

from app.dtos.base import BaseSerializerModel


class SessionCreate(BaseSerializerModel):
    session_title: str | None = None
    session_intent_mode: str = "DIET_ASSIST"  # DIET_ASSIST / PARENT_MONITOR
    has_injected_context: bool = False


class SessionResponse(BaseSerializerModel):
    id: int
    user_id: int
    session_title: str | None = None
    session_intent_mode: str
    has_injected_context: bool
    created_at: datetime.datetime


class MessageCreate(BaseSerializerModel):
    content: str


class MessageResponse(BaseSerializerModel):
    id: int
    sender_type: str
    message_text: str
