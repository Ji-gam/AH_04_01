from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class FoodSearchResultItem(BaseModel):
    food_name: Annotated[str, Field(description="식품/음식명", examples=["흰쌀밥"])]
    serving_size_g: Annotated[float, Field(description="1회 제공량 기준(g). 인분 배율의 1인분 기준치")]
    calorie_kcal_per_100g: Annotated[float, Field(description="100g당 칼로리(kcal)")]
    protein_g_per_100g: Annotated[float, Field(description="100g당 단백질(g)")]
    carb_g_per_100g: Annotated[float, Field(description="100g당 탄수화물(g)")]
    fat_g_per_100g: Annotated[float, Field(description="100g당 지방(g)")]


class FoodSearchResult(BaseModel):
    results: Annotated[list[FoodSearchResultItem], Field(description="검색어와 부분 일치하는 식품 목록")]


class AIFoodSearchRequest(BaseModel):
    food_name: Annotated[
        str,
        Field(min_length=1, max_length=50, description="검색으로 못 찾아 AI에게 물어볼 음식 이름", examples=["김"]),
    ]


class DietLogCreateRequest(BaseModel):
    """검색 결과 카드를 그대로 다시 보내서 서버가 재검색 없이 배율만 곱해 기록한다."""

    food_name: Annotated[str, Field(description="기록할 식품명", examples=["흰쌀밥"])]
    serving_size_g: Annotated[float, Field(gt=0, description="검색 결과의 1회 제공량(g)")]
    serving_multiplier: Annotated[float, Field(gt=0, le=5, description="인분 배율 (0.5/1/1.5/2 등)")]
    calorie_kcal_per_100g: Annotated[float, Field(ge=0, description="검색 결과의 100g당 칼로리")]
    protein_g_per_100g: Annotated[float, Field(ge=0, description="검색 결과의 100g당 단백질")]
    carb_g_per_100g: Annotated[float, Field(ge=0, description="검색 결과의 100g당 탄수화물")]
    fat_g_per_100g: Annotated[float, Field(ge=0, description="검색 결과의 100g당 지방")]


class DietLogItemResult(BaseModel):
    id: Annotated[int, Field(description="기록 id. 삭제 API 호출 시 이 값을 쓴다.")]
    food_name: Annotated[str, Field(description="기록된 식품명")]
    serving_grams: Annotated[float, Field(description="실제 섭취량(g) = serving_size_g * serving_multiplier")]
    calorie_kcal: Annotated[float, Field(description="기록 시점 계산된 칼로리(kcal)")]
    protein_g: Annotated[float, Field(description="기록 시점 계산된 단백질(g)")]
    carb_g: Annotated[float, Field(description="기록 시점 계산된 탄수화물(g)")]
    fat_g: Annotated[float, Field(description="기록 시점 계산된 지방(g)")]
    logged_at: Annotated[datetime, Field(description="기록된 시각")]


class DietTodayResult(BaseModel):
    logs: Annotated[list[DietLogItemResult], Field(description="오늘 기록된 식사 목록")]
    total_kcal: Annotated[float, Field(description="오늘 총 섭취 칼로리(kcal)")]
    total_protein_g: Annotated[float, Field(description="오늘 총 단백질(g)")]
    total_carb_g: Annotated[float, Field(description="오늘 총 탄수화물(g)")]
    total_fat_g: Annotated[float, Field(description="오늘 총 지방(g)")]
    reference_kcal: Annotated[
        int,
        Field(description="비교 기준 칼로리 - 키/몸무게/나이/성별이 있으면 개인화 계산값, 없으면 일반 권장량(2000)"),
    ]
    reference_kcal_reason: Annotated[
        str, Field(description="기준 칼로리 산정 이유 한 줄 (AI 생성 또는 규칙 기반 폴백)")
    ]


class DietRecentDayResult(BaseModel):
    log_date: Annotated[date, Field(description="날짜")]
    total_kcal: Annotated[float, Field(description="그 날 총 섭취 칼로리(kcal)")]


class DietRecentResult(BaseModel):
    days: Annotated[list[DietRecentDayResult], Field(description="최근 7일(오늘 포함) 일별 총 칼로리")]
