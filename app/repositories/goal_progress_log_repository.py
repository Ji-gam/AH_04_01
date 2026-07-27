from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goal_progress_logs import GoalProgressLog

_RECENT_LIMIT = 7


class GoalProgressLogRepository:
    async def upsert(self, session: AsyncSession, goal_id: int, log_date: date, value: Decimal) -> GoalProgressLog:
        """하루 한 건 - 이미 그날 기록이 있으면 값을 덮어쓰고, 없으면 새로 만든다."""
        result = await session.execute(
            select(GoalProgressLog).where(GoalProgressLog.goal_id == goal_id, GoalProgressLog.log_date == log_date)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.value = value
            await session.commit()
            await session.refresh(existing)
            return existing

        log = GoalProgressLog(goal_id=goal_id, log_date=log_date, value=value)
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

    async def list_recent(self, session: AsyncSession, goal_id: int) -> list[GoalProgressLog]:
        result = await session.execute(
            select(GoalProgressLog)
            .where(GoalProgressLog.goal_id == goal_id)
            .order_by(GoalProgressLog.log_date.desc())
            .limit(_RECENT_LIMIT)
        )
        return list(reversed(result.scalars().all()))
