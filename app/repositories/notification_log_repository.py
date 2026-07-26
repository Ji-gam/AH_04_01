from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_log import NotificationLog

_LIST_LIMIT = 50


class NotificationLogRepository:
    async def create(self, session: AsyncSession, profile_id: int, title: str, body: str) -> NotificationLog:
        log = NotificationLog(profile_id=profile_id, title=title, body=body)
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

    async def list_for_profile(self, session: AsyncSession, profile_id: int) -> list[NotificationLog]:
        result = await session.execute(
            select(NotificationLog)
            .where(NotificationLog.profile_id == profile_id)
            # created_at이 초 단위라 같은 초에 여러 알림이 쌓이면 순서가 뒤섞일 수 있어,
            # id desc를 2차 정렬로 둬서 항상 최신 순서를 보장한다.
            .order_by(NotificationLog.created_at.desc(), NotificationLog.id.desc())
            .limit(_LIST_LIMIT)
        )
        return list(result.scalars().all())

    async def count_unread(self, session: AsyncSession, profile_id: int) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(NotificationLog)
            .where(NotificationLog.profile_id == profile_id, NotificationLog.is_read.is_(False))
        )
        return result.scalar_one()

    async def mark_all_read(self, session: AsyncSession, profile_id: int) -> None:
        await session.execute(
            update(NotificationLog)
            .where(NotificationLog.profile_id == profile_id, NotificationLog.is_read.is_(False))
            .values(is_read=True)
        )
        await session.commit()
