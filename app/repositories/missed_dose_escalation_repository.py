from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.missed_dose_escalations import MissedDoseEscalation


class MissedDoseEscalationRepository:
    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        medication_name: str,
        alarm_time: str,
        intake_date: date,
        check_at: datetime,
    ) -> MissedDoseEscalation:
        escalation = MissedDoseEscalation(
            profile_id=profile_id,
            source_type=source_type,
            source_id=source_id,
            medication_name=medication_name,
            alarm_time=alarm_time,
            intake_date=intake_date,
            check_at=check_at,
        )
        session.add(escalation)
        await session.commit()
        await session.refresh(escalation)
        return escalation

    async def list_due(self, session: AsyncSession, now: datetime) -> list[MissedDoseEscalation]:
        result = await session.execute(select(MissedDoseEscalation).where(MissedDoseEscalation.check_at <= now))
        return list(result.scalars().all())

    async def delete(self, session: AsyncSession, escalation_id: int) -> None:
        escalation = await session.get(MissedDoseEscalation, escalation_id)
        if escalation is not None:
            await session.delete(escalation)
            await session.commit()
