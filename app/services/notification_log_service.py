from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.notification_log_dto import NotificationLogItemResult, NotificationLogListResult
from app.repositories.notification_log_repository import NotificationLogRepository


class NotificationLogService:
    def __init__(self, notification_log_repo: NotificationLogRepository | None = None) -> None:
        self._repo = notification_log_repo or NotificationLogRepository()

    async def list_inbox(self, session: AsyncSession, profile_id: int) -> NotificationLogListResult:
        logs = await self._repo.list_for_profile(session, profile_id)
        unread_count = await self._repo.count_unread(session, profile_id)
        return NotificationLogListResult(
            items=[
                NotificationLogItemResult(
                    id=log.id, title=log.title, body=log.body, is_read=log.is_read, created_at=log.created_at
                )
                for log in logs
            ],
            unread_count=unread_count,
        )

    async def mark_all_read(self, session: AsyncSession, profile_id: int) -> None:
        await self._repo.mark_all_read(session, profile_id)
