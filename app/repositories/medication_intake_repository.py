from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medication_intake import MedicationIntakeLog


class MedicationIntakeRepository:
    async def get_one(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        scheduled_time: str,
        intake_date: date,
    ) -> MedicationIntakeLog | None:
        result = await session.execute(
            select(MedicationIntakeLog).where(
                MedicationIntakeLog.profile_id == profile_id,
                MedicationIntakeLog.source_type == source_type,
                MedicationIntakeLog.source_id == source_id,
                MedicationIntakeLog.scheduled_time == scheduled_time,
                MedicationIntakeLog.intake_date == intake_date,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        scheduled_time: str,
        intake_date: date,
    ) -> MedicationIntakeLog:
        log = MedicationIntakeLog(
            profile_id=profile_id,
            source_type=source_type,
            source_id=source_id,
            scheduled_time=scheduled_time,
            intake_date=intake_date,
        )
        session.add(log)
        await session.commit()
        return log

    async def delete(self, session: AsyncSession, log: MedicationIntakeLog) -> None:
        await session.delete(log)
        await session.commit()

    async def list_for_date(
        self, session: AsyncSession, profile_id: int, intake_date: date
    ) -> list[MedicationIntakeLog]:
        result = await session.execute(
            select(MedicationIntakeLog).where(
                MedicationIntakeLog.profile_id == profile_id,
                MedicationIntakeLog.intake_date == intake_date,
            )
        )
        return list(result.scalars().all())

    async def count_by_date_for_range(
        self, session: AsyncSession, profile_id: int, start_date: date, end_date: date
    ) -> dict[date, int]:
        """히트맵용 - 날짜별 체크 개수만 집계한다. "그 날 몇 개가 예정돼 있었는지"(분모)는
        요일별 반복 규칙이 프론트(dateUtils.isScheduleDueOnDate)에만 있어서 여기선 모른다 -
        분자(체크 개수)만 주고, 분모는 프론트가 buildGroups로 직접 계산해 합친다."""
        result = await session.execute(
            select(MedicationIntakeLog.intake_date, func.count(MedicationIntakeLog.id))
            .where(
                MedicationIntakeLog.profile_id == profile_id,
                MedicationIntakeLog.intake_date >= start_date,
                MedicationIntakeLog.intake_date <= end_date,
            )
            .group_by(MedicationIntakeLog.intake_date)
        )
        return {row[0]: row[1] for row in result.all()}
