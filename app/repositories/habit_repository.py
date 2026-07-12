from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.habit_logs import HabitLog


class HabitRepository:
    async def list_logs_for_date(self, session: AsyncSession, profile_id: int, log_date: date) -> list[HabitLog]:
        result = await session.execute(
            select(HabitLog).where(HabitLog.profile_id == profile_id, HabitLog.log_date == log_date)
        )
        return list(result.scalars().all())

    async def get_log(self, session: AsyncSession, profile_id: int, log_date: date, habit_key: str) -> HabitLog | None:
        result = await session.execute(
            select(HabitLog).where(
                HabitLog.profile_id == profile_id,
                HabitLog.log_date == log_date,
                HabitLog.habit_key == habit_key,
            )
        )
        return result.scalar_one_or_none()

    async def increment_progress(
        self, session: AsyncSession, profile_id: int, log_date: date, habit_key: str, cap: int
    ) -> HabitLog:
        log = await self.get_log(session, profile_id, log_date, habit_key)
        if log is None:
            log = HabitLog(profile_id=profile_id, log_date=log_date, habit_key=habit_key, progress=0)
            session.add(log)
        log.progress = min(log.progress + 1, cap)
        await session.commit()
        await session.refresh(log)
        return log
