# backend/domains/chat/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class SessionCreate(BaseModel):
    session_title: Optional[str] = None
    session_intent_mode: str = "DIET_ASSIST"  # DIET_ASSIST / PARENT_MONITOR
    has_injected_context: bool = False


class SessionResponse(BaseModel):
    session_id: int
    user_id: int
    session_title: Optional[str] = None
    session_intent_mode: str
    has_injected_context: bool
    created_at: datetime.datetime


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    message_id: int
    sender_type: str
    message_text: str
