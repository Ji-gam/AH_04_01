import datetime

from app.dtos.schedule import ScheduleCreate
from app.models.schedules import MedicationSchedule
from app.models.users import User


class ScheduleService:
    def _parse_time(self, value: str) -> datetime.time:
        fmt = "%H:%M:%S" if value.count(":") == 2 else "%H:%M"
        return datetime.datetime.strptime(value, fmt).time()

    async def create_schedule(self, user: User, data: ScheduleCreate) -> MedicationSchedule:
        new_schedule = await MedicationSchedule.create(
            user=user,
            medication_id=data.medication_id,
            record_id=data.record_id,
            card_alias=data.card_alias,
            frequency_type=data.frequency_type,
            target_day_of_week=data.target_day_of_week,
            alarm_time=self._parse_time(data.alarm_time),
        )
        return new_schedule

    async def get_user_schedules(self, user: User) -> list[MedicationSchedule]:
        return await MedicationSchedule.filter(user=user).all()
