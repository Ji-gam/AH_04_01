import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.notice import NoticeCreateRequest
from app.models.notice import Notice, NoticeKind
from app.repositories.notice_repository import NoticeRepository
from app.repositories.notification_settings_repository import NotificationSettingsRepository
from app.services.push_service import PushService

logger = logging.getLogger("app.notice_service")


class NoticeService:
    def __init__(self) -> None:
        self._repo = NoticeRepository()
        self._settings_repo = NotificationSettingsRepository()
        self._push_service = PushService()

    async def list_notices(self, session: AsyncSession) -> list[Notice]:
        return await self._repo.list_all(session)

    async def create_notice(self, session: AsyncSession, data: NoticeCreateRequest) -> Notice:
        kind = NoticeKind(data.kind)
        notice = await self._repo.create(session, kind, data.title, data.body)
        # 알림 발송은 공지 등록 자체와 별개로 다룬다 - 발송이 몇 건 실패해도 이미 커밋된
        # 공지 등록 자체는 되돌리지 않는다.
        await self._broadcast(session, kind, data.title)
        return notice

    async def _broadcast(self, session: AsyncSession, kind: NoticeKind, title: str) -> None:
        try:
            if kind == NoticeKind.NOTICE:
                profile_ids = await self._settings_repo.list_profile_ids_with_notice_enabled(session)
                push_title = "📢 새 공지사항"
            else:
                profile_ids = await self._settings_repo.list_profile_ids_with_marketing_enabled(session)
                push_title = "🎁 새 소식"
            for profile_id in profile_ids:
                try:
                    await self._push_service.send_to_profile(session, profile_id, title=push_title, body=title)
                except Exception:
                    logger.exception("공지 알림 발송 실패 (profile_id=%s)", profile_id)
        except Exception:
            logger.exception("공지 알림 브로드캐스트 실패")
