from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.notification_settings import NotificationSettingsResponse, NotificationSettingsUpdateRequest
from app.models.profiles import Profile
from app.services.notification_settings_service import NotificationSettingsService

notification_settings_router = APIRouter(prefix="/notifications/settings", tags=["notifications"])


@notification_settings_router.get(
    "",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="알림 커스터마이징 설정 조회",
    description="로그인한 프로필의 알림 설정을 반환한다. 아직 설정한 적이 없으면 기본값으로 새로 만들어 반환한다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_notification_settings(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationSettingsService, Depends(NotificationSettingsService)],
) -> NotificationSettingsResponse:
    setting = await service.get_settings(session, profile.id)
    return NotificationSettingsResponse.model_validate(setting)


@notification_settings_router.patch(
    "",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="알림 커스터마이징 설정 수정",
    description="전달한 필드만 부분 수정한다.",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def update_notification_settings(
    data: NotificationSettingsUpdateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[NotificationSettingsService, Depends(NotificationSettingsService)],
) -> NotificationSettingsResponse:
    setting = await service.update_settings(session, profile.id, data)
    return NotificationSettingsResponse.model_validate(setting)
