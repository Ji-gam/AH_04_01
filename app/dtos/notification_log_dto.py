from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class NotificationLogItemResult(BaseModel):
    id: Annotated[int, Field(description="알림 id")]
    title: Annotated[str, Field(description="알림 제목")]
    body: Annotated[str, Field(description="알림 본문")]
    is_read: Annotated[bool, Field(description="읽음 여부")]
    created_at: Annotated[datetime, Field(description="발송 시각")]


class NotificationLogListResult(BaseModel):
    items: Annotated[list[NotificationLogItemResult], Field(description="최근 알림 목록(최신순, 최대 50개)")]
    unread_count: Annotated[int, Field(description="안 읽은 알림 개수")]
