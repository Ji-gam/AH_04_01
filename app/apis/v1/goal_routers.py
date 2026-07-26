from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.goal_dto import (
    GoalCreateRequest,
    GoalItemResult,
    GoalListResult,
    GoalProgressLogCreateRequest,
    GoalUpdateRequest,
)
from app.models.profiles import Profile
from app.services.goal_service import GoalService

goal_router = APIRouter(prefix="/goals", tags=["goals"])


@goal_router.get(
    "",
    response_model=GoalListResult,
    status_code=status.HTTP_200_OK,
    summary="목표(F-GOAL-1) 목록 조회",
    description="이 프로필의 목표를 종료일 임박순으로 반환한다. 각 목표에는 F-GOAL-2 AI 가이드가 함께 담긴다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def list_goals(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalListResult:
    return await GoalService().list_goals(session, profile.id)


@goal_router.post(
    "",
    response_model=GoalItemResult,
    status_code=status.HTTP_201_CREATED,
    summary="목표 생성",
    description="생성 즉시 F-GOAL-2 AI 가이드도 함께 생성해서 반환한다(AI 실패 시 폴백 템플릿으로 저장).",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def create_goal(
    body: GoalCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalItemResult:
    return await GoalService().create(session, profile.id, body)


@goal_router.patch(
    "/{goal_id}",
    response_model=GoalItemResult,
    status_code=status.HTTP_200_OK,
    summary="목표 수정",
    description="값을 준 필드만 바뀐다. 제목/수치/기간이 바뀌면 F-GOAL-2 가이드가 자동으로 재생성된다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 목표"},
    },
)
async def update_goal(
    goal_id: int,
    body: GoalUpdateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalItemResult:
    result = await GoalService().update(session, profile.id, goal_id, body)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 목표를 찾을 수 없습니다.")
    return result


@goal_router.post(
    "/{goal_id}/logs",
    response_model=GoalItemResult,
    status_code=status.HTTP_200_OK,
    summary="목표 일일 수치 기록(오늘 기록하기)",
    description=(
        "하루 한 건 - 같은 날 다시 기록하면 그날 값을 덮어쓴다. 이 값이 목표의 현재 수치로도 "
        "반영되어 진행률이 즉시 갱신되지만, 수정(PATCH)과 달리 F-GOAL-2 가이드는 다시 생성하지 않는다."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 목표"},
    },
)
async def log_goal_progress(
    goal_id: int,
    body: GoalProgressLogCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GoalItemResult:
    result = await GoalService().log_progress(session, profile.id, goal_id, body.value, body.log_date)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 목표를 찾을 수 없습니다.")
    return result


@goal_router.delete(
    "/{goal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="목표 삭제",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 목표"},
    },
)
async def delete_goal(
    goal_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    deleted = await GoalService().delete(session, profile.id, goal_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 목표를 찾을 수 없습니다.")
