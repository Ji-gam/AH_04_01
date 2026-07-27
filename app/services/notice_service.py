import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.dtos.notice import NoticeCreateRequest
from app.models.notice import Notice, NoticeKind
from app.repositories.notice_repository import NoticeRepository
from app.repositories.notification_settings_repository import NotificationSettingsRepository
from app.services.push_service import PushService
from app.services.quiet_hours import is_in_quiet_hours

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
                settings_list = await self._settings_repo.list_settings_with_notice_enabled(session)
                push_title = "📢 새 공지사항"
            else:
                settings_list = await self._settings_repo.list_settings_with_marketing_enabled(session)
                push_title = "🎁 새 소식"
            now = datetime.now(tz=config.TIMEZONE)
            for setting in settings_list:
                # 공지/마케팅은 필수 알림이 아니라 무음 시간대엔 보류한다(F-NTFY-6).
                if is_in_quiet_hours(setting, now):
                    continue
                try:
                    await self._push_service.send_to_profile(
                        session, setting.profile_id, title=push_title, body=title, link_url="/notices"
                    )
                except Exception:
                    logger.exception("공지 알림 발송 실패 (profile_id=%s)", setting.profile_id)
        except Exception:
            logger.exception("공지 알림 브로드캐스트 실패")
