from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.reason_feedback import FeedbackValue


class ReasonFeedbackRequest(BaseModel):
    value: Annotated[FeedbackValue, Field(description="이 설명이 도움이 됐는지 여부", examples=["UP"])]
    comment: Annotated[
        str | None, Field(default=None, max_length=500, description="자유 서술(선택). 왜 도움이 안 됐는지 등")
    ]


class ReasonFeedbackResponse(BaseModel):
    value: Annotated[FeedbackValue, Field(description="저장된 평가값")]
    updated_at: Annotated[datetime, Field(description="이 평가가 (재)등록된 시각")]
