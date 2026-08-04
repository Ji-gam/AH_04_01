from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import CursorResult, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.diet_dto import (
    AIFoodSearchRequest,
    DietLogCreateRequest,
    DietRecentResult,
    DietTodayResult,
    FoodSearchResult,
)
from app.dtos.feedback import ReasonFeedbackRequest, ReasonFeedbackResponse
from app.models.food_nutrition_cache import FoodNutritionCache
from app.models.profiles import Profile
from app.repositories.diet_repository import DietRepository
from app.services.diet_service import DietService
from app.services.reason_feedback_service import ReasonFeedbackService

diet_router = APIRouter(prefix="/diet", tags=["diet"])


# TEMP(2026-08-04): FOOD_NUTRITION_API_KEY가 운영에 없던 동안(진단 테스트 포함) 캐시에
# 박힌 특정 검색어만 콕 집어 지우기 위한 임시 엔드포인트. 전체 DELETE는 "AI로 찾기"로
# 사용자가 일부러 만든 항목까지 지워버리므로 쓰지 않는다. 확인 끝나면 제거할 것.
@diet_router.post("/_debug/clear-food-cache", include_in_schema=False)
async def debug_clear_food_cache(
    query_names: list[str],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await session.execute(delete(FoodNutritionCache).where(FoodNutritionCache.query_name.in_(query_names)))
    await session.commit()
    return {"deleted": cast(CursorResult, result).rowcount}


@diet_router.get(
    "/search",
    response_model=FoodSearchResult,
    status_code=status.HTTP_200_OK,
    summary="음식 이름으로 영양성분 검색",
    description=(
        "더보기 > 마이다이어리 > 식단 기록 화면의 검색창용. 식품영양성분DB API(설정 안 됐거나 "
        "호출 실패 시 로컬 시드)에서 검색어와 부분 일치하는 음식을 100g 기준 영양성분과 함께 반환한다."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "검색어가 비어 있음"},
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
    },
)
async def search_food(
    query: str,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FoodSearchResult:
    service = DietService()
    return await service.search_food(session, query)


@diet_router.post(
    "/ai-food",
    response_model=FoodSearchResult,
    status_code=status.HTTP_200_OK,
    summary="검색으로 못 찾은 음식을 AI가 추정",
    description=(
        "식약처 DB 검색 결과에 사용자가 찾는 음식이 없을 때(예: '김'을 치면 김밥·김치 요리만 "
        "나옴) 화면의 'AI로 찾기' 버튼이 호출한다. AI가 100g당 영양성분과 1회 제공량을 추정해 "
        "1건으로 돌려주고, 그 검색어의 캐시 맨 앞에 넣어 다음 검색부터 함께 보이게 한다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "AI 호출 실패 또는 비상식적인 추정값"},
    },
)
async def find_food_by_ai(
    body: AIFoodSearchRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FoodSearchResult:
    service = DietService()
    return await service.find_food_by_ai(session, body.food_name)


@diet_router.post(
    "/logs",
    response_model=DietTodayResult,
    status_code=status.HTTP_201_CREATED,
    summary="식사 기록 추가",
    description="검색 결과 카드(음식명 + 100g당 영양성분 + 1회 제공량)와 고른 인분 배율을 그대로 보내면 오늘 기록으로 저장한다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def log_food(
    body: DietLogCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DietTodayResult:
    service = DietService()
    return await service.log_food(session, profile, body)


@diet_router.get(
    "/today",
    response_model=DietTodayResult,
    status_code=status.HTTP_200_OK,
    summary="오늘 식사 기록 및 총 영양성분 조회",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_today(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DietTodayResult:
    service = DietService()
    return await service.get_today(session, profile)


@diet_router.delete(
    "/logs/{log_id}",
    response_model=DietTodayResult,
    status_code=status.HTTP_200_OK,
    summary="식사 기록 삭제",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 기록"},
    },
)
async def delete_log(
    log_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DietTodayResult:
    service = DietService()
    return await service.delete_log(session, profile, log_id)


@diet_router.get(
    "/recent",
    response_model=DietRecentResult,
    status_code=status.HTTP_200_OK,
    summary="최근 7일(오늘 포함) 일별 총 칼로리 조회",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_recent(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DietRecentResult:
    service = DietService()
    return await service.get_recent(session, profile)


@diet_router.post(
    "/kcal-reason-feedback",
    response_model=ReasonFeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="오늘의 기준 칼로리 이유가 도움이 됐는지 평가(👍/👎)",
    description=(
        "GET /diet/today 응답의 reference_kcal_reason에 대한 평가를 남긴다. 같은 날 다시 "
        "호출하면 이전 평가를 덮어쓴다(재평가)."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "오늘의 기준 칼로리 이유가 아직 생성되지 않음"},
    },
)
async def submit_diet_kcal_reason_feedback(
    body: ReasonFeedbackRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReasonFeedbackResponse:
    today = date.today()
    diet_repository = DietRepository()
    if await diet_repository.get_kcal_reason(session, profile.id, today) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="오늘의 기준 칼로리 이유가 아직 생성되지 않았습니다."
        )

    feedback_service = ReasonFeedbackService()
    feedback = await feedback_service.submit_diet_kcal_reason_feedback(
        session, profile.id, today.isoformat(), body.value, body.comment
    )
    return ReasonFeedbackResponse(value=feedback.value, updated_at=feedback.updated_at)
