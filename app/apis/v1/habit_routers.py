from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.habit import HabitRecommendationsResponse, HabitSelectionRequest, HabitsTodayResponse
from app.models.profiles import Profile
from app.services.habit_service import HabitService

habit_router = APIRouter(prefix="/habits", tags=["habits"])


@habit_router.get(
    "/recommendations",
    response_model=HabitRecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="오늘의 추천 습관 목록 조회 (선택용, 매일 5개)",
    description=(
        "더보기 > 생활습관 선택 화면용. 질환 유무와 무관한 기본 세트(물 2L 마시기, 산책 20분 등 "
        "8개)에 등록된 진단병력마다 맞춤 습관이 하나씩 더해진 후보군에서, 날짜 기준으로 매일 "
        "5개를 추천한다. 이 5개 중 몇 개를 실제로 할지는 POST /habits/selections으로 사용자가 "
        "직접 고른다(0~5개 모두 가능)."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_habit_recommendations(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HabitRecommendationsResponse:
    service = HabitService()
    return await service.get_recommendations(session, profile)


@habit_router.post(
    "/selections",
    response_model=HabitsTodayResponse,
    status_code=status.HTTP_200_OK,
    summary="오늘 할 습관 선택(최대 5개, 0개도 허용)",
    description=(
        "오늘의 추천 목록(GET /habits/recommendations) 중 실제로 할 습관을 고른다. 다시 호출하면 "
        "이전 선택은 전부 교체된다. 선택된 습관만 홈 화면 라이프스타일 카드/habits/today에 노출된다."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "오늘의 추천 목록에 없는 habit_key가 섞여 있음"},
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
    },
)
async def select_habits(
    body: HabitSelectionRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HabitsTodayResponse:
    service = HabitService()
    return await service.select_habits(session, profile, body.habit_keys)


@habit_router.get(
    "/today",
    response_model=HabitsTodayResponse,
    status_code=status.HTTP_200_OK,
    summary="오늘 선택한 습관 목록 및 진행량 조회",
    description=(
        "홈 화면 '오늘의 건강 카드' 아래 습관 트래커용. 오늘의 추천 목록 중 사용자가 실제로 선택한 "
        "습관만 반환한다(아직 하나도 안 골랐으면 빈 배열). 자정이 지나면 선택도 progress도 초기화된다."
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
