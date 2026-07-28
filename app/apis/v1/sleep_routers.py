from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.sleep_dto import SleepLogCreateRequest, SleepRecentResult, SleepTodayResult
from app.models.profiles import Profile
from app.services.sleep_service import SleepService

sleep_router = APIRouter(prefix="/sleep", tags=["sleep"])


@sleep_router.post(
    "/logs",
    response_model=SleepTodayResult,
    status_code=status.HTTP_201_CREATED,
    summary="오늘 수면 기록 저장",
    description="더보기 > 마이다이어리 > 수면 기록 화면용. 하루 1건이라, 오늘 기록이 이미 있으면 값을 덮어쓴다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def log_sleep(
    body: SleepLogCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SleepTodayResult:
    service = SleepService()
    return await service.log_sleep(session, profile, body)


@sleep_router.get(
    "/today",
    response_model=SleepTodayResult,
    status_code=status.HTTP_200_OK,
    summary="오늘 수면 기록 조회",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_today(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SleepTodayResult:
    service = SleepService()
    return await service.get_today(session, profile)


@sleep_router.get(
    "/recent",
    response_model=SleepRecentResult,
    status_code=status.HTTP_200_OK,
    summary="최근 7일(오늘 포함) 일별 수면 기록 조회",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_recent(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SleepRecentResult:
    service = SleepService()
    return await service.get_recent(session, profile)
