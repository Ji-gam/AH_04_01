from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.notifications import (
    NotificationScheduleCreateRequest,
    NotificationScheduleResponse,
    NotificationScheduleUpdateRequest,
)
from app.models.profiles import Profile
from app.services.notifications import NotificationScheduleService

notification_router = APIRouter(prefix="/notifications/schedules", tags=["notifications"])


@notification_router.get(
    "",
    response_model=list[NotificationScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="복약 알림 일정 목록 조회",
    description="로그인한 프로필의 복약 알림 일정을 모두 반환한다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def list_notification_schedules(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> Response:
    schedules = await service.list_schedules(session, profile.id)
    return Response(
        content=[NotificationScheduleResponse.model_validate(s).model_dump(mode="json") for s in schedules],
        status_code=status.HTTP_200_OK,
    )


@notification_router.post(
    "",
    response_model=NotificationScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="복약 알림 일정 등록",
    description="새 복약 알림 일정을 등록한다. frequency_type이 WEEKLY면 target_day_of_week가 필수다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "WEEKLY인데 target_day_of_week가 없는 등 입력값이 유효하지 않음"
        },
    },
)
async def create_notification_schedule(
    data: NotificationScheduleCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> Response:
    schedule = await service.create_schedule(session, profile.id, data)
    return Response(
        content=NotificationScheduleResponse.model_validate(schedule).model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
    )


@notification_router.patch(
    "/{schedule_id}",
    response_model=NotificationScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="복약 알림 일정 수정",
    description="전달한 필드만 부분 수정한다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 일정"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "WEEKLY인데 target_day_of_week가 없는 등 입력값이 유효하지 않음"
        },
    },
)
async def update_notification_schedule(
    schedule_id: int,
    data: NotificationScheduleUpdateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> Response:
    schedule = await service.update_schedule(session, profile.id, schedule_id, data)
    return Response(
        content=NotificationScheduleResponse.model_validate(schedule).model_dump(mode="json"),
        status_code=status.HTTP_200_OK,
    )


@notification_router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="복약 알림 일정 삭제",
    description="본인 소유의 복약 알림 일정을 삭제한다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 일정"},
    },
)
async def delete_notification_schedule(
    schedule_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> None:
    await service.delete_schedule(session, profile.id, schedule_id)


@notification_router.get(
    "/family/{target_profile_id}",
    response_model=list[NotificationScheduleResponse],
    status_code=status.HTTP_200_OK,
    summary="가족 구성원의 복약 알림 일정 목록 조회 (가족관리)",
    description="보호자가 자신이 관리하는 가족 구성원의 복약 알림 일정을 조회한다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_403_FORBIDDEN: {"description": "해당 프로필의 보호자가 아님"},
    },
)
async def list_notification_schedules_for_family(
    target_profile_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> Response:
    schedules = await service.list_schedules_for_family(session, profile.id, target_profile_id)
    return Response(
        content=[NotificationScheduleResponse.model_validate(s).model_dump(mode="json") for s in schedules],
        status_code=status.HTTP_200_OK,
    )


@notification_router.post(
    "/family/{target_profile_id}",
    response_model=NotificationScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="가족 구성원 몫 복약 알림 등록 (가족관리)",
    description="보호자가 자신이 관리하는 가족 구성원 몫으로 새 복약 알림을 등록한다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_403_FORBIDDEN: {"description": "해당 프로필의 보호자가 아님"},
    },
)
async def create_notification_schedule_for_family(
    target_profile_id: int,
    data: NotificationScheduleCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> Response:
    schedule = await service.create_schedule_for_family(session, profile.id, target_profile_id, data)
    return Response(
        content=NotificationScheduleResponse.model_validate(schedule).model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
    )


@notification_router.patch(
    "/{schedule_id}/for-family",
    response_model=NotificationScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="가족 구성원 몫 복약 알림 수정/토글 (가족관리)",
    description="보호자가 가족 구성원 몫 알림을 수정한다. is_active만 보내면 on/off 토글로 쓸 수 있다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_403_FORBIDDEN: {"description": "해당 알림에 대한 권한이 없음"},
    },
)
async def update_notification_schedule_for_family(
    schedule_id: int,
    data: NotificationScheduleUpdateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> Response:
    schedule = await service.update_schedule_for_family(session, profile.id, schedule_id, data)
    return Response(
        content=NotificationScheduleResponse.model_validate(schedule).model_dump(mode="json"),
        status_code=status.HTTP_200_OK,
    )


@notification_router.delete(
    "/{schedule_id}/for-family",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="가족 구성원 몫 복약 알림 삭제 (가족관리)",
    description="보호자가 가족 구성원 몫 알림을 삭제한다.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"},
        status.HTTP_403_FORBIDDEN: {"description": "해당 알림에 대한 권한이 없음"},
    },
)
async def delete_notification_schedule_for_family(
    schedule_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationScheduleService, Depends(NotificationScheduleService)],
) -> None:
    await service.delete_schedule_for_family(session, profile.id, schedule_id)
