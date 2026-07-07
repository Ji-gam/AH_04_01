from datetime import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_schedules import DayOfWeek, FrequencyType, NotificationSchedule

ALLOWED_UPDATE_FIELDS = ["medication_name", "frequency_type", "target_day_of_week", "alarm_time", "is_active"]


class NotificationRepository:
    async def get_schedule(self, session: AsyncSession, schedule_id: int) -> NotificationSchedule | None:
        return await session.get(NotificationSchedule, schedule_id)

    async def list_schedules_for_profile(self, session: AsyncSession, profile_id: int) -> list[NotificationSchedule]:
        result = await session.execute(
            select(NotificationSchedule).where(NotificationSchedule.profile_id == profile_id)
        )
        return list(result.scalars().all())

    async def create_schedule(
        self,
        session: AsyncSession,
        profile_id: int,
        medication_name: str,
        frequency_type: FrequencyType,
        target_day_of_week: DayOfWeek | None,
        alarm_time: time,
    ) -> NotificationSchedule:
        schedule = NotificationSchedule(
            profile_id=profile_id,
            medication_name=medication_name,
            frequency_type=frequency_type,
            target_day_of_week=target_day_of_week,
            alarm_time=alarm_time,
        )
        session.add(schedule)
        await session.flush()
        return schedule

    async def update_instance(
        self, session: AsyncSession, schedule: NotificationSchedule, data: dict[str, Any]
    ) -> None:
        for key, value in data.items():
            if key in ALLOWED_UPDATE_FIELDS:
                setattr(schedule, key, value)
        await session.flush()

    async def delete_instance(self, session: AsyncSession, schedule: NotificationSchedule) -> None:
        await session.delete(schedule)
        await session.flush()
