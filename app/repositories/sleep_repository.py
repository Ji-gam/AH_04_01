from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sleep_logs import SleepLog


class SleepRepository:
    async def get_for_date(self, session: AsyncSession, profile_id: int, log_date: date) -> SleepLog | None:
        result = await session.execute(
            select(SleepLog).where(SleepLog.profile_id == profile_id, SleepLog.log_date == log_date)
        )
        return result.scalar_one_or_none()

    async def upsert_log(
        self,
        session: AsyncSession,
        profile_id: int,
        log_date: date,
        hours: float,
        bed_time: time | None,
        quality: int,
        reason: str | None,
    ) -> SleepLog:
        """하루 1건 - 오늘 기록이 이미 있으면 값만 덮어쓰고, 없으면 새로 만든다."""
        existing = await self.get_for_date(session, profile_id, log_date)
        if existing is not None:
            existing.hours = hours
            existing.bed_time = bed_time
            existing.quality = quality
            existing.reason = reason
            await session.commit()
            await session.refresh(existing)
            return existing

        log = SleepLog(
            profile_id=profile_id, log_date=log_date, hours=hours, bed_time=bed_time, quality=quality, reason=reason
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

    async def list_daily(
        self, session: AsyncSession, profile_id: int, start_date: date, end_date: date
    ) -> list[SleepLog]:
        result = await session.execute(
            select(SleepLog)
            .where(SleepLog.profile_id == profile_id, SleepLog.log_date >= start_date, SleepLog.log_date <= end_date)
            .order_by(SleepLog.log_date)
        )
        return list(result.scalars().all())

    async def list_profile_ids_with_logs_in_range(
        self, session: AsyncSession, start_date: date, end_date: date
    ) -> list[int]:
        """주간 AI 리포트 대상자 선정용 - diet_repository.py의
        list_profile_ids_with_logs_in_range와 같은 패턴."""
        result = await session.execute(
            select(SleepLog.profile_id).where(SleepLog.log_date >= start_date, SleepLog.log_date <= end_date).distinct()
        )
        return list(result.scalars().all())
