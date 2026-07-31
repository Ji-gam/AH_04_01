from datetime import date, time
from typing import Annotated

from pydantic import BaseModel, Field


class SleepLogCreateRequest(BaseModel):
    """오늘 하루치 수면 기록. 이미 오늘 기록이 있으면 덮어쓴다(하루 1건)."""

    hours: Annotated[float, Field(ge=0, le=24, description="수면 시간(직접 입력, 시간 단위)")]
    bed_time: Annotated[time | None, Field(description="취침 시각(참고용, 선택)")] = None
    quality: Annotated[
        int, Field(ge=1, le=5, description="수면의 질 - 5:매우 잘 잤음 4:잘 잤음 3:보통 2:잘 못 잠 1:1시간도 못 잠")
    ]
    reason: Annotated[str | None, Field(max_length=200, description="못 잔 이유(선택, 자유 텍스트)")] = None


class SleepLogResult(BaseModel):
    log_date: Annotated[date, Field(description="기록 날짜")]
    hours: Annotated[float, Field(description="수면 시간")]
    bed_time: Annotated[time | None, Field(description="취침 시각")]
    quality: Annotated[int, Field(description="수면의 질(1~5)")]
    reason: Annotated[str | None, Field(description="못 잔 이유")]


class SleepTodayResult(BaseModel):
    log: Annotated[SleepLogResult | None, Field(description="오늘 기록(아직 없으면 null)")]
    reference_hours: Annotated[int, Field(description="비교 기준 수면시간 - 일반 권장량(8) 고정")]


class SleepRecentDayResult(BaseModel):
    log_date: Annotated[date, Field(description="날짜")]
    hours: Annotated[float, Field(description="그 날 수면 시간")]
    quality: Annotated[int | None, Field(description="그 날 수면의 질(기록 없으면 null)")]


class SleepRecentResult(BaseModel):
    days: Annotated[list[SleepRecentDayResult], Field(description="최근 7일(오늘 포함) 일별 수면 기록")]
