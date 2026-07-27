from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.diet_dto import DietLogCreateRequest, DietRecentResult, DietTodayResult, FoodSearchResult
from app.models.profiles import Profile
from app.services.diet_service import DietService

diet_router = APIRouter(prefix="/diet", tags=["diet"])


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
