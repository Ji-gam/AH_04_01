from datetime import time
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.dtos.base import BaseSerializerModel
from app.models.notification_schedules import DayOfWeek, FrequencyType


class NotificationScheduleCreateRequest(BaseModel):
    medication_name: Annotated[str, Field(min_length=1, max_length=100, description="약 이름", examples=["타이레놀"])]
    frequency_type: Annotated[FrequencyType, Field(default=FrequencyType.DAILY, description="'DAILY' 또는 'WEEKLY'")]
    target_day_of_week: Annotated[
        DayOfWeek | None,
        Field(default=None, description="frequency_type이 WEEKLY일 때만 필수. 값: 일/월/화/수/목/금/토"),
    ]
    alarm_time: Annotated[time, Field(description="복용 시각. HH:MM:SS", examples=["08:30:00"])]

    @model_validator(mode="after")
    def check_weekly_requires_day(self) -> "NotificationScheduleCreateRequest":
        if self.frequency_type == FrequencyType.WEEKLY and self.target_day_of_week is None:
            raise ValueError("frequency_type이 WEEKLY이면 target_day_of_week가 필수입니다.")
        if self.frequency_type == FrequencyType.DAILY:
            self.target_day_of_week = None
        return self


class NotificationScheduleUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정)."""

    medication_name: Annotated[
        str | None, Field(None, min_length=1, max_length=100, description="약 이름", examples=["타이레놀"])
    ]
    frequency_type: Annotated[FrequencyType | None, Field(None, description="'DAILY' 또는 'WEEKLY'")]
    target_day_of_week: Annotated[DayOfWeek | None, Field(None, description="frequency_type이 WEEKLY일 때만 값 사용")]
    alarm_time: Annotated[time | None, Field(None, description="복용 시각. HH:MM:SS", examples=["08:30:00"])]
    is_active: Annotated[bool | None, Field(None, description="알림 on/off")]


class NotificationScheduleResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="알림 일정 PK", examples=[1])]
    medication_name: Annotated[str, Field(description="약 이름", examples=["타이레놀"])]
    frequency_type: Annotated[FrequencyType, Field(description="'DAILY' 또는 'WEEKLY'")]
    target_day_of_week: Annotated[DayOfWeek | None, Field(description="WEEKLY일 때만 값 존재")]
    alarm_time: Annotated[time, Field(description="복용 시각. HH:MM:SS", examples=["08:30:00"])]
    is_active: Annotated[bool, Field(description="알림 on/off", examples=[True])]
