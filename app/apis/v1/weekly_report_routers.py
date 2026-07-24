from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.weekly_report_dto import WeeklyReportListResult
from app.models.profiles import Profile
from app.services.weekly_report_service import WeeklyReportService

weekly_report_router = APIRouter(prefix="/weekly-reports", tags=["weekly-reports"])


@weekly_report_router.get(
    "",
    response_model=WeeklyReportListResult,
    status_code=status.HTTP_200_OK,
    summary="저장된 주간 AI 리포트 목록 조회",
    description=(
        "매주 일요일 오전 9시에 스케줄러가 자동으로 생성해 저장한 주간 리포트를 최신순으로 "
        "반환한다. 수동 생성 API는 없다 - 전적으로 스케줄러(push_scheduler.py)가 채운다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def list_weekly_reports(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WeeklyReportListResult:
    service = WeeklyReportService()
    return await service.list_reports(session, profile.id)
