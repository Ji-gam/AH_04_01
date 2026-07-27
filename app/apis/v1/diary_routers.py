from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.diary_dto import DiaryEntryItemResult, DiaryEntryListResult, DiaryEntrySaveRequest, DiaryTodayResult
from app.models.profiles import Profile
from app.services.diary_service import DiaryService

diary_router = APIRouter(prefix="/diary", tags=["diary"])


@diary_router.get(
    "/today",
    response_model=DiaryTodayResult,
    status_code=status.HTTP_200_OK,
    summary="오늘 이미 작성한 '오늘의 한 줄' 조회",
    description="오늘 이미 저장한 기록이 있으면 그대로 내려준다(수정 화면에 미리 채워 넣기용) - 없으면 entry가 null.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_today(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiaryTodayResult:
    service = DiaryService()
    return await service.get_today(session, profile)


@diary_router.post(
    "/today",
    response_model=DiaryEntryItemResult,
    status_code=status.HTTP_200_OK,
    summary="오늘의 한 줄 저장(다시 호출하면 오늘 기록을 덮어씀)",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def save_today(
    body: DiaryEntrySaveRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiaryEntryItemResult:
    service = DiaryService()
    return await service.save_today(session, profile, body)


@diary_router.get(
    "",
    response_model=DiaryEntryListResult,
    status_code=status.HTTP_200_OK,
    summary="저장된 '오늘의 한 줄' 전체 목록 조회(최신순)",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def list_entries(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiaryEntryListResult:
    service = DiaryService()
    return await service.list_entries(session, profile)


@diary_router.delete(
    "/{entry_id}",
    response_model=DiaryEntryListResult,
    status_code=status.HTTP_200_OK,
    summary="'오늘의 한 줄' 기록 삭제",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 기록"},
    },
)
async def delete_entry(
    entry_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DiaryEntryListResult:
    service = DiaryService()
    return await service.delete_entry(session, profile, entry_id)
