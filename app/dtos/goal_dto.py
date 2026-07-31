from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models.goals import GoalType

GoalTerm = Literal["단기", "장기"]


class GoalCreateRequest(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=100, description="목표명(예: 3kg 감량하기)")]
    goal_type: Annotated[
        GoalType,
        Field(
            default=GoalType.NUMERIC,
            description=(
                "NUMERIC(수치형, 기본값) - 체중감량처럼 현재 수치를 직접 입력. "
                "FREQUENCY(횟수형) - 운동하기처럼 하루 1회 '완료' 처리로 수치가 자동 증가."
            ),
        ),
    ]
    start_value: Annotated[float | None, Field(default=None, description="시작 시점 수치(예: 68)")]
    target_value: Annotated[float | None, Field(default=None, description="목표 수치(예: 65)")]
    current_value: Annotated[float | None, Field(default=None, description="현재 수치 - 없으면 start_value와 동일")]
    unit: Annotated[str | None, Field(default=None, max_length=20, description="단위(예: kg, 시간, 회)")]
    start_date: Annotated[date, Field(description="시작일")]
    end_date: Annotated[date, Field(description="종료일 - 이 날짜와 시작일 간격으로 단기/장기가 자동 판별된다")]


class GoalUpdateRequest(BaseModel):
    """부분 수정 - 값을 준 필드만 바뀐다. current_value만 갱신해 진행 상황만 업데이트하는
    용도로도 쓴다. 어떤 필드든 값이 바뀌면 F-GOAL-2 가이드가 자동으로 다시 생성된다."""

    title: Annotated[str | None, Field(default=None, min_length=1, max_length=100)]
    start_value: Annotated[float | None, Field(default=None)]
    target_value: Annotated[float | None, Field(default=None)]
    current_value: Annotated[float | None, Field(default=None)]
    unit: Annotated[str | None, Field(default=None, max_length=20)]
    start_date: Annotated[date | None, Field(default=None)]
    end_date: Annotated[date | None, Field(default=None)]
    is_achieved: Annotated[bool | None, Field(default=None)]


class GoalProgressLogCreateRequest(BaseModel):
    value: Annotated[float, Field(description="오늘(또는 지정한 날짜) 측정한 수치(예: 66.5)")]
    log_date: Annotated[date | None, Field(default=None, description="기록 날짜 - 생략하면 오늘")]


class GoalProgressLogItemResult(BaseModel):
    log_date: Annotated[date, Field(description="기록 날짜")]
    value: Annotated[float, Field(description="그날 기록한 수치")]


class GoalItemResult(BaseModel):
    id: Annotated[int, Field(description="목표 id")]
    title: Annotated[str, Field(description="목표명")]
    goal_type: Annotated[GoalType, Field(description="NUMERIC(수치형) 또는 FREQUENCY(횟수형) - 생성 후 변경 불가")]
    start_value: Annotated[float | None, Field(description="시작 시점 수치")]
    target_value: Annotated[float | None, Field(description="목표 수치")]
    current_value: Annotated[float | None, Field(description="현재 수치")]
    unit: Annotated[str | None, Field(description="단위")]
    start_date: Annotated[date, Field(description="시작일")]
    end_date: Annotated[date, Field(description="종료일")]
    term: Annotated[GoalTerm, Field(description="기간이 31일 이하면 단기, 초과면 장기로 자동 판별")]
    progress_rate: Annotated[
        float | None,
        Field(description="(현재-시작)/(목표-시작)을 0~1로 clamp한 값. 수치를 하나라도 안 넣었으면 null"),
    ]
    is_achieved: Annotated[bool, Field(description="달성 여부")]
    guide_content: Annotated[str | None, Field(description="F-GOAL-2 AI가 작성한(또는 폴백 템플릿) 맞춤 가이드")]
    guide_generated_at: Annotated[datetime | None, Field(description="가이드 생성 시각")]
    created_at: Annotated[datetime, Field(description="생성 시각")]
    recent_logs: Annotated[
        list[GoalProgressLogItemResult], Field(description="최근 일일 기록(최대 7건, 날짜 오름차순)")
    ]


class GoalListResult(BaseModel):
    goals: Annotated[list[GoalItemResult], Field(description="이 프로필의 목표 목록(종료일 임박순)")]
