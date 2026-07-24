from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class DiaryEntrySaveRequest(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=1000, description="오늘의 한 줄 내용")]
    image_base64: Annotated[
        str | None,
        Field(default=None, max_length=6_000_000, description="사진 첨부 1장(선택) - data URL 형태 base64 문자열"),
    ]


class DiaryEntryItemResult(BaseModel):
    id: Annotated[int, Field(description="기록 id")]
    entry_date: Annotated[date, Field(description="기록 날짜")]
    content: Annotated[str, Field(description="오늘의 한 줄 내용")]
    image_base64: Annotated[str | None, Field(description="첨부된 사진(data URL base64) - 없으면 null")]
    created_at: Annotated[datetime, Field(description="최초 작성 시각")]
    updated_at: Annotated[datetime, Field(description="마지막 수정 시각")]


class DiaryEntryListResult(BaseModel):
    entries: Annotated[list[DiaryEntryItemResult], Field(description="저장된 기록 목록(최신순)")]


class DiaryTodayResult(BaseModel):
    entry: Annotated[DiaryEntryItemResult | None, Field(description="오늘 이미 작성한 기록 - 없으면 null")]
