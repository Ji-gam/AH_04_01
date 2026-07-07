from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.medication_dto import (
    MedicationScheduleCreateRequest,
    MedicationScheduleResponse,
    RecognitionConfirmRequest,
    RecognitionConfirmResult,
    RecognitionJobCreateResult,
    RecognitionResult,
)
from app.models.profiles import Profile
from app.services.medication_service import MedicationService

medication_router = APIRouter(tags=["Medications"])


@medication_router.post(
    "/recognition/jobs",
    response_model=RecognitionJobCreateResult,
    status_code=202,
    summary="알약/처방전/진료기록 인식 요청",
    description="비동기로 처방전/알약 이미지를 업로드하고 분석 작업을 시작합니다.",
)
async def create_recognition_job(
    background_tasks: BackgroundTasks,
    source_type: Annotated[str, Form(...)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File(...)],
) -> RecognitionJobCreateResult:
    service = MedicationService()
    file_bytes = await file.read()
    return await service.create_recognition_job(
        session=session,
        profile_id=profile.id,
        source_type=source_type,
        file_bytes=file_bytes,
        file_name=file.filename or "image.jpg",
        background_tasks=background_tasks,
    )


@medication_router.get(
    "/recognition/jobs/{job_id}",
    response_model=RecognitionResult,
    summary="인식 결과 조회",
    description="비동기 OCR 및 분석 작업 결과를 확인합니다.",
)
async def get_recognition_job(
    job_id: str,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecognitionResult:
    service = MedicationService()
    return await service.get_recognition_job(session, job_id, profile.id)


@medication_router.post(
    "/recognition/jobs/{job_id}/confirm",
    response_model=RecognitionConfirmResult,
    summary="사용자 최종 확인 → 복약 스케줄 자동 반영",
    description="사용자가 인식을 완료하고 최종 선택한 의약품 코드를 복약 스케줄에 반영합니다.",
)
async def confirm_recognition_job(
    job_id: str,
    body: RecognitionConfirmRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecognitionConfirmResult:
    service = MedicationService()
    return await service.confirm_recognition_job(
        session=session,
        job_id=job_id,
        profile_id=profile.id,
        selected_candidate_drug_code=body.selected_candidate_drug_code,
        confirmed_fields=body.confirmed_fields,
    )


@medication_router.get(
    "/medications",
    response_model=list[MedicationScheduleResponse],
    summary="등록된 복약 스케줄 목록",
    description="현재 프로필에 등록되어 활성화된 복약 스케줄 목록을 가져옵니다.",
)
async def list_medication_schedules(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MedicationScheduleResponse]:
    service = MedicationService()
    return await service.list_schedules(session, profile.id)


@medication_router.post(
    "/medications",
    response_model=MedicationScheduleResponse,
    status_code=201,
    summary="복약 스케줄 수동 등록",
    description="의약품 코드를 직접 선택하여 시간을 지정하고 복약 스케줄을 직접 등록합니다.",
)
async def create_manual_schedule(
    body: MedicationScheduleCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MedicationScheduleResponse:
    service = MedicationService()
    return await service.create_manual_schedule(session, profile.id, body)


@medication_router.delete(
    "/medications/{schedule_id}",
    status_code=204,
    summary="복약 스케줄 삭제",
    description="잘못 등록되었거나 더 이상 필요 없는 복약 스케줄을 삭제합니다.",
)
async def delete_medication_schedule(
    schedule_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = MedicationService()
    await service.delete_schedule(session, profile.id, schedule_id)


@medication_router.get(
    "/medications/search",
    summary="의약품 마스터 수동 검색",
    description="약품명 또는 외형 검색 fallback을 위한 검색창의 자동완성 API입니다.",
)
async def search_medications(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    query: str = Query(..., min_length=1),
):
    service = MedicationService()
    return await service.search_medications(session, query)
