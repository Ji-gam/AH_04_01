from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.medication_intake import IntakeDailyCountResult, IntakeRecordResult, IntakeToggleRequest
from app.models.profiles import Profile
from app.services.medication_intake_service import MedicationIntakeService

intake_router = APIRouter(prefix="/intake", tags=["intake"])


@intake_router.post(
    "/toggle",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="복약 체크/체크해제 (F-ADH-1)",
)
async def toggle_intake(
    body: IntakeToggleRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[MedicationIntakeService, Depends(MedicationIntakeService)],
) -> None:
    await service.toggle(
        session, profile.id, body.source_type, body.source_id, body.scheduled_time, body.date, body.checked
    )


@intake_router.get(
    "",
    response_model=list[IntakeRecordResult],
    summary="특정 날짜의 복약 체크 목록 조회",
)
async def list_intake(
    date: Annotated[str, Query(description="YYYY-MM-DD")],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[MedicationIntakeService, Depends(MedicationIntakeService)],
) -> list[IntakeRecordResult]:
    return await service.list_for_date(session, profile.id, date)


@intake_router.get(
    "/daily-counts",
    response_model=list[IntakeDailyCountResult],
    summary="날짜 구간별 복약 체크 개수 (히트맵용)",
    description="[start, end] 구간(포함) 전체 날짜를 빠짐없이 반환한다 - 기록 없는 날은 0건.",
)
async def get_daily_counts(
    start: Annotated[str, Query(description="YYYY-MM-DD")],
    end: Annotated[str, Query(description="YYYY-MM-DD")],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[MedicationIntakeService, Depends(MedicationIntakeService)],
) -> list[IntakeDailyCountResult]:
    return await service.daily_counts(session, profile.id, start, end)
