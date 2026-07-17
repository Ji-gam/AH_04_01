from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.dtos.notifications import NotificationScheduleCreateRequest, NotificationScheduleUpdateRequest
from app.models.notification_schedules import FrequencyType, NotificationSchedule
from app.repositories.family_repository import FamilyRepository
from app.repositories.notification_repository import NotificationRepository


class NotificationScheduleService:
    def __init__(self):
        self.repo = NotificationRepository()
        self._family_repo = FamilyRepository()  # (가족관리) 대상자 권한검증용

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

    async def list_schedules_for_family(
        self, session: AsyncSession, requester_profile_id: int, target_profile_id: int
    ) -> list[NotificationSchedule]:
        """(가족관리) 보호자가 가족 구성원의 복약 알림 목록을 조회한다. 기존 list_schedules와
        로직이 겹치지만, 다른 조원분이 만든 이 서비스 파일을 안전하게 건드리기 위해 별도 메서드로
        추가했다(같은 이유로 medication_service.py에 confirm_recognition_job_for_family 등을
        분리 추가한 것과 동일한 패턴 - docs/decision_log/2026-07-16-... 참고)."""
        is_guardian = await self._family_repo.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="해당 프로필의 알림을 조회할 권한이 없습니다."
            )
        return await self.repo.list_schedules_for_profile(session, target_profile_id)

    async def create_schedule_for_family(
        self,
        session: AsyncSession,
        requester_profile_id: int,
        target_profile_id: int,
        data: NotificationScheduleCreateRequest,
    ) -> NotificationSchedule:
        """(가족관리) 보호자가 가족 구성원 몫으로 복약 알림을 새로 등록한다."""
        is_guardian = await self._family_repo.is_guardian_of(session, requester_profile_id, target_profile_id)
        if not is_guardian:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 프로필에 알림을 등록할 권한이 없습니다. 더보기 > 가족관리에서 먼저 연결해주세요.",
            )
        schedule = await self.repo.create_schedule(
            session,
            profile_id=target_profile_id,
            medication_name=data.medication_name,
            frequency_type=data.frequency_type,
            target_day_of_week=data.target_day_of_week,
            alarm_time=data.alarm_time,
        )
        await session.commit()
        return schedule

    async def _get_guarded_schedule(
        self, session: AsyncSession, requester_profile_id: int, schedule_id: int
    ) -> NotificationSchedule:
        schedule = await self.repo.get_schedule(session, schedule_id)
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 알림 일정을 찾을 수 없습니다.")
        is_guardian = await self._family_repo.is_guardian_of(session, requester_profile_id, schedule.profile_id)
        if not is_guardian:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="해당 알림 일정에 대한 권한이 없습니다.")
        return schedule

    async def update_schedule_for_family(
        self,
        session: AsyncSession,
        requester_profile_id: int,
        schedule_id: int,
        data: NotificationScheduleUpdateRequest,
    ) -> NotificationSchedule:
        """(가족관리) 보호자가 가족 구성원 몫 알림을 수정한다. is_active 필드도 여기 포함되므로
        이 메서드 하나로 "수정"과 "on/off 토글"을 둘 다 처리한다(기존 update_schedule과 동일한 설계)."""
        schedule = await self._get_guarded_schedule(session, requester_profile_id, schedule_id)
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

    async def delete_schedule_for_family(
        self, session: AsyncSession, requester_profile_id: int, schedule_id: int
    ) -> None:
        schedule = await self._get_guarded_schedule(session, requester_profile_id, schedule_id)
        await self.repo.delete_instance(session, schedule)
        await session.commit()
