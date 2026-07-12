from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.habit import HabitsTodayResponse
from app.models.profiles import Profile
from app.services.habit_service import HabitService

habit_router = APIRouter(prefix="/habits", tags=["habits"])


@habit_router.get(
    "/today",
    response_model=HabitsTodayResponse,
    status_code=status.HTTP_200_OK,
    summary="오늘의 습관 목록 및 진행량 조회",
    description=(
        "홈 화면 '오늘의 건강 카드' 아래 습관 트래커용. 기본 세트(물 마시기 5잔, 산책 1회)에 "
        "등록된 진단병력마다 맞춤 습관이 하나씩 더해진다. 자정이 지나면 progress는 자동으로 0부터 다시 시작한다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_today_habits(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HabitsTodayResponse:
    service = HabitService()
    return await service.get_today(session, profile)


@habit_router.post(
    "/today/{habit_key}/check",
    response_model=HabitsTodayResponse,
    status_code=status.HTTP_200_OK,
    summary="습관 1회 체크(진행량 +1)",
    description=(
        "누를 때마다 progress가 1 증가한다(target을 넘어서지 않음). "
        "응답의 all_completed가 true면 프론트에서 칭찬 화면을 띄운다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "오늘 이 프로필의 습관 목록에 없는 habit_key"},
    },
)
async def check_habit(
    habit_key: str,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HabitsTodayResponse:
    service = HabitService()
    return await service.check_habit(session, profile, habit_key)
