from datetime import time
from typing import Annotated

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel


class NotificationSettingsUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정)."""

    push_enabled: Annotated[bool | None, Field(None, description="복약알림 푸시 on/off")]
    chatbot_reply_enabled: Annotated[bool | None, Field(None, description="AI챗봇 답변 알림 on/off")]
    notice_enabled: Annotated[bool | None, Field(None, description="공지사항 알림 on/off")]
    marketing_enabled: Annotated[bool | None, Field(None, description="마케팅 알림 on/off")]
    lifestyle_tip_enabled: Annotated[bool | None, Field(None, description="라이프스타일 팁 알림 on/off")]
    quiet_mode_enabled: Annotated[bool | None, Field(None, description="무음 모드 on/off")]
    quiet_start: Annotated[time | None, Field(None, description="무음 시작 시각. HH:MM", examples=["22:00"])]
    quiet_end: Annotated[time | None, Field(None, description="무음 종료 시각. HH:MM", examples=["07:00"])]
    sound_enabled: Annotated[bool | None, Field(None, description="알림 소리 on/off")]
    vibration_enabled: Annotated[bool | None, Field(None, description="알림 진동 on/off")]
    popup_enabled: Annotated[bool | None, Field(None, description="알림 팝업 on/off")]


class NotificationSettingsResponse(BaseSerializerModel):
    push_enabled: Annotated[bool, Field(description="복약알림 푸시 on/off")]
    chatbot_reply_enabled: Annotated[bool, Field(description="AI챗봇 답변 알림 on/off")]
    notice_enabled: Annotated[bool, Field(description="공지사항 알림 on/off")]
    marketing_enabled: Annotated[bool, Field(description="마케팅 알림 on/off")]
    lifestyle_tip_enabled: Annotated[bool, Field(description="라이프스타일 팁 알림 on/off")]
    quiet_mode_enabled: Annotated[bool, Field(description="무음 모드 on/off")]
    quiet_start: Annotated[time, Field(description="무음 시작 시각. HH:MM", examples=["22:00"])]
    quiet_end: Annotated[time, Field(description="무음 종료 시각. HH:MM", examples=["07:00"])]
    sound_enabled: Annotated[bool, Field(description="알림 소리 on/off")]
    vibration_enabled: Annotated[bool, Field(description="알림 진동 on/off")]
    popup_enabled: Annotated[bool, Field(description="알림 팝업 on/off")]
