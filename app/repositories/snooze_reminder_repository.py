from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snooze_reminders import SnoozeReminder


class SnoozeReminderRepository:
    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        medication_name: str,
        alarm_time: str,
        remind_at: datetime,
    ) -> SnoozeReminder:
        reminder = SnoozeReminder(
            profile_id=profile_id,
            source_type=source_type,
            source_id=source_id,
            medication_name=medication_name,
            alarm_time=alarm_time,
            remind_at=remind_at,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder

    async def list_due(self, session: AsyncSession, now: datetime) -> list[SnoozeReminder]:
        result = await session.execute(select(SnoozeReminder).where(SnoozeReminder.remind_at <= now))
        return list(result.scalars().all())

    async def delete(self, session: AsyncSession, reminder_id: int) -> None:
        reminder = await session.get(SnoozeReminder, reminder_id)
        if reminder is not None:
            await session.delete(reminder)
            await session.commit()
