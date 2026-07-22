from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.dtos.base import BaseSerializerModel


class NoticeCreateRequest(BaseModel):
    kind: Annotated[Literal["NOTICE", "MARKETING"], Field(description="'NOTICE'(공지) 또는 'MARKETING'(마케팅)")]
    title: Annotated[str, Field(min_length=1, max_length=200, description="공지 제목")]
    body: Annotated[str, Field(min_length=1, description="공지 본문")]


class NoticeResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="공지 PK")]
    kind: Annotated[str, Field(description="'NOTICE' 또는 'MARKETING'")]
    title: Annotated[str, Field(description="공지 제목")]
    body: Annotated[str, Field(description="공지 본문")]
    created_at: Annotated[datetime, Field(description="등록 시각")]
    is_new: Annotated[bool, Field(description="가장 최근에 등록된 공지인지 여부(NEW 배지용)")]
