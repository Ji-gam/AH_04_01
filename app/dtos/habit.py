from typing import Annotated

from pydantic import BaseModel, Field


class HabitItemResponse(BaseModel):
    key: Annotated[str, Field(description="습관 식별 키. 체크 API 호출 시 이 값을 그대로 쓴다.")]
    label: Annotated[str, Field(description="화면에 보여줄 습관 이름", examples=["물 마시기"])]
    icon: Annotated[str, Field(description="습관 카드에 표시할 이모지", examples=["🥤"])]
    unit: Annotated[str, Field(description="진행량 단위", examples=["잔"])]
    target: Annotated[int, Field(description="오늘 목표량", examples=[5])]
    progress: Annotated[int, Field(description="오늘 지금까지 체크한 횟수(target 이상으로 올라가지 않는다)")]
    completed: Annotated[bool, Field(description="progress가 target에 도달했는지")]


class HabitsTodayResponse(BaseModel):
    habits: Annotated[
        list[HabitItemResponse], Field(description="오늘 사용자가 실제로 선택한 습관 목록(0~5개, 선택 전이면 빈 배열)")
    ]
    all_completed: Annotated[
        bool, Field(description="선택한 습관이 1개 이상이고 전부 목표치까지 채웠는지 - 칭찬 화면 트리거 기준")
    ]


class HabitRecommendationItem(BaseModel):
    key: Annotated[str, Field(description="습관 식별 키. 선택 API 호출 시 이 값을 그대로 쓴다.")]
    label: Annotated[str, Field(description="화면에 보여줄 습관 이름", examples=["물 마시기"])]
    icon: Annotated[str, Field(description="습관 카드에 표시할 이모지", examples=["🥤"])]
    unit: Annotated[str, Field(description="진행량 단위", examples=["잔"])]
    target: Annotated[int, Field(description="오늘 목표량", examples=[5])]


class HabitRecommendationsResponse(BaseModel):
    habits: Annotated[
        list[HabitRecommendationItem],
        Field(description="오늘의 추천 습관 목록(매일 5개 - 기본 세트 + 등록 질환별 맞춤 항목에서 날짜 기준 회전)"),
    ]
    selected_keys: Annotated[
        list[str], Field(description="이 중 오늘 이미 선택해둔 항목의 key 목록(화면에 미리 체크 표시용)")
    ]


class HabitSelectionRequest(BaseModel):
    habit_keys: Annotated[
        list[str],
        Field(max_length=5, description="오늘 하기로 고른 습관 key 목록. 최대 5개, 0개(전부 해제)도 허용된다."),
    ]
