from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class WeeklyReportItemResult(BaseModel):
    id: Annotated[int, Field(description="리포트 id")]
    week_start_date: Annotated[date, Field(description="집계 시작일(월요일)")]
    week_end_date: Annotated[date, Field(description="집계 종료일(일요일)")]
    content: Annotated[str, Field(description="AI가 작성한(또는 폴백 템플릿) 주간 리포트 본문")]
    created_at: Annotated[datetime, Field(description="생성 시각")]


class WeeklyReportListResult(BaseModel):
    reports: Annotated[list[WeeklyReportItemResult], Field(description="저장된 주간 리포트 목록(최신순)")]
