from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.dtos.notifications import NotificationScheduleCreateRequest, NotificationScheduleUpdateRequest
from app.models.notification_schedules import FrequencyType, NotificationSchedule
from app.repositories.notification_repository import NotificationRepository


class NotificationScheduleService:
    def __init__(self):
        self.repo = NotificationRepository()

    async def list_schedules(self, session: AsyncSession, profile_id: int) -> list[NotificationSchedule]:
        return await self.repo.list_schedules_for_profile(session, profile_id)

    async def create_schedule(
        self, session: AsyncSession, profile_id: int, data: NotificationScheduleCreateRequest
    ) -> NotificationSchedule:
        schedule = await self.repo.create_schedule(
            session,
            profile_id=profile_id,
            medication_name=data.medication_name,
            frequency_type=data.frequency_type,
            target_day_of_week=data.target_day_of_week,
            alarm_time=data.alarm_time,
        )
        await session.commit()
        return schedule

    async def get_owned_schedule(
        self, session: AsyncSession, profile_id: int, schedule_id: int
    ) -> NotificationSchedule:
        schedule = await self.repo.get_schedule(session, schedule_id)
        if not schedule or schedule.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 알림 일정을 찾을 수 없습니다.")
        return schedule

    async def update_schedule(
        self, session: AsyncSession, profile_id: int, schedule_id: int, data: NotificationScheduleUpdateRequest
    ) -> NotificationSchedule:
        schedule = await self.get_owned_schedule(session, profile_id, schedule_id)
        update_fields = data.model_dump(exclude_unset=True)

        next_frequency = update_fields.get("frequency_type", schedule.frequency_type)
        next_day = update_fields.get("target_day_of_week", schedule.target_day_of_week)
        if next_frequency == FrequencyType.WEEKLY and next_day is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="frequency_type이 WEEKLY이면 target_day_of_week가 필수입니다.",
            )
        if next_frequency == FrequencyType.DAILY and "target_day_of_week" not in update_fields:
            update_fields["target_day_of_week"] = None

        await self.repo.update_instance(session, schedule, update_fields)
        await session.commit()
        return schedule

    async def delete_schedule(self, session: AsyncSession, profile_id: int, schedule_id: int) -> None:
        schedule = await self.get_owned_schedule(session, profile_id, schedule_id)
        await self.repo.delete_instance(session, schedule)
        await session.commit()
