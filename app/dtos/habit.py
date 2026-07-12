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
    habits: Annotated[list[HabitItemResponse], Field(description="오늘의 습관 목록(기본 세트 + 등록 질환별 맞춤 항목)")]
    all_completed: Annotated[bool, Field(description="오늘의 습관을 전부 목표치까지 채웠는지 - 칭찬 화면 트리거 기준")]
