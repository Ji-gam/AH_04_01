from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

ExerciseInputMode = Literal["duration", "speed", "count"]


class ExerciseSearchResultItem(BaseModel):
    exercise_name: Annotated[str, Field(description="운동명", examples=["달리기"])]
    met_value: Annotated[
        float | None,
        Field(description="MET(대사당량) 값. input_mode가 'speed'면 속도로 실시간 계산하므로 null"),
    ]
    input_mode: Annotated[
        ExerciseInputMode,
        Field(description="'duration'(시간만 입력) / 'speed'(속도+시간 입력) / 'count'(횟수 입력)"),
    ]


class ExerciseSearchResult(BaseModel):
    results: Annotated[list[ExerciseSearchResultItem], Field(description="검색어와 부분 일치하는 운동 목록")]


class ExerciseLogCreateRequest(BaseModel):
    """검색 결과 카드를 그대로 다시 보내서 서버가 재검색 없이 소모 칼로리를 계산한다.
    input_mode에 따라 아래 필드 중 필요한 것만 채워서 보낸다:
    - duration: met_value, duration_minutes
    - speed: speed_kmh, duration_minutes (met_value는 서버가 속도로 계산하므로 안 보내도 된다)
    - count: count (duration_minutes는 서버가 분당 100회 가정으로 환산하므로 안 보내도 된다)
    """

    exercise_name: Annotated[str, Field(description="기록할 운동명", examples=["달리기"])]
    input_mode: Annotated[ExerciseInputMode, Field(description="입력 방식")]
    met_value: Annotated[float | None, Field(default=None, gt=0, description="duration 모드에서 검색 결과의 MET 값")]
    duration_minutes: Annotated[
        float | None, Field(default=None, gt=0, le=600, description="duration/speed 모드의 운동 시간(분)")
    ]
    speed_kmh: Annotated[float | None, Field(default=None, gt=0, le=50, description="speed 모드의 속도(km/h)")]
    count: Annotated[int | None, Field(default=None, gt=0, le=100000, description="count 모드의 횟수")]


class ExerciseLogItemResult(BaseModel):
    id: Annotated[int, Field(description="기록 id. 삭제 API 호출 시 이 값을 쓴다.")]
    exercise_name: Annotated[str, Field(description="기록된 운동명")]
    duration_minutes: Annotated[float, Field(description="운동 시간(분) - count 모드도 환산값이 채워진다")]
    distance_km: Annotated[float | None, Field(description="speed 모드에서 계산된 거리(km)")]
    count: Annotated[int | None, Field(description="count 모드에서 입력한 횟수")]
    calorie_kcal: Annotated[float, Field(description="기록 시점 계산된 소모 칼로리(kcal)")]
    logged_at: Annotated[datetime, Field(description="기록된 시각")]


class ExerciseTodayResult(BaseModel):
    logs: Annotated[list[ExerciseLogItemResult], Field(description="오늘 기록된 운동 목록")]
    total_kcal: Annotated[float, Field(description="오늘 총 소모 칼로리(kcal)")]
    total_duration_minutes: Annotated[float, Field(description="오늘 총 운동 시간(분)")]
    reference_minutes: Annotated[int, Field(description="비교 기준 운동시간 - 일반 권장량(30분) 고정")]


class ExerciseRecentDayResult(BaseModel):
    log_date: Annotated[date, Field(description="날짜")]
    total_kcal: Annotated[float, Field(description="그 날 총 소모 칼로리(kcal)")]


class ExerciseRecentResult(BaseModel):
    days: Annotated[list[ExerciseRecentDayResult], Field(description="최근 7일(오늘 포함) 일별 총 소모 칼로리")]
