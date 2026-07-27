from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weekly_reports import WeeklyReport


class WeeklyReportRepository:
    async def get_by_profile_and_week(
        self, session: AsyncSession, profile_id: int, week_start_date: date
    ) -> WeeklyReport | None:
        result = await session.execute(
            select(WeeklyReport).where(
                WeeklyReport.profile_id == profile_id, WeeklyReport.week_start_date == week_start_date
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        week_start_date: date,
        week_end_date: date,
        content: str,
    ) -> WeeklyReport:
        report = WeeklyReport(
            profile_id=profile_id,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            content=content,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report

    async def list_for_profile(self, session: AsyncSession, profile_id: int) -> list[WeeklyReport]:
        result = await session.execute(
            select(WeeklyReport)
            .where(WeeklyReport.profile_id == profile_id)
            .order_by(WeeklyReport.week_start_date.desc())
        )
        return list(result.scalars().all())
