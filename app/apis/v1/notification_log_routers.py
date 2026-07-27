from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.notification_log_dto import NotificationLogListResult
from app.models.profiles import Profile
from app.services.notification_log_service import NotificationLogService

notification_log_router = APIRouter(prefix="/notifications/inbox", tags=["notification-log"])


@notification_log_router.get(
    "",
    response_model=NotificationLogListResult,
    status_code=status.HTTP_200_OK,
    summary="홈 상단 🔔 알림함 - 최근 알림 목록 조회",
    description=(
        "복약알림/공지/가족알림/주간·월간 리포트/부작용안내 등 이 프로필에게 발송된 모든 "
        "알림을 최신순으로 반환한다(최대 50건). 실제 웹푸시/FCM 전달 성공 여부와 무관하게, "
        "발송이 결정된 알림은 전부 여기 남는다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "토큰이 없거나 유효하지 않음"}},
)
async def get_notification_inbox(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationLogListResult:
    service = NotificationLogService()
    return await service.list_inbox(session, profile.id)


@notification_log_router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="알림함 전체 읽음 처리",
    description="🔔 아이콘을 눌러 알림함을 열었을 때 호출 - 안 읽은 알림을 전부 읽음으로 표시한다.",
)
async def mark_all_notifications_read(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = NotificationLogService()
    await service.mark_all_read(session, profile.id)
