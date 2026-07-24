from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exercise_logs import ExerciseLog


class ExerciseRepository:
    async def create_log(
        self,
        session: AsyncSession,
        profile_id: int,
        log_date: date,
        exercise_name: str,
        duration_minutes: Decimal,
        calorie_kcal: Decimal,
        distance_km: Decimal | None = None,
        count: int | None = None,
    ) -> ExerciseLog:
        log = ExerciseLog(
            profile_id=profile_id,
            log_date=log_date,
            exercise_name=exercise_name,
            duration_minutes=duration_minutes,
            distance_km=distance_km,
            count=count,
            calorie_kcal=calorie_kcal,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

    async def get_log(self, session: AsyncSession, profile_id: int, log_id: int) -> ExerciseLog | None:
        result = await session.execute(
            select(ExerciseLog).where(ExerciseLog.id == log_id, ExerciseLog.profile_id == profile_id)
        )
        return result.scalar_one_or_none()

    async def delete_log(self, session: AsyncSession, profile_id: int, log_id: int) -> bool:
        log = await self.get_log(session, profile_id, log_id)
        if log is None:
            return False
        await session.execute(delete(ExerciseLog).where(ExerciseLog.id == log_id, ExerciseLog.profile_id == profile_id))
        await session.commit()
        return True

    async def list_logs_for_date(self, session: AsyncSession, profile_id: int, log_date: date) -> list[ExerciseLog]:
        result = await session.execute(
            select(ExerciseLog)
            .where(ExerciseLog.profile_id == profile_id, ExerciseLog.log_date == log_date)
            .order_by(ExerciseLog.created_at)
        )
        return list(result.scalars().all())

    async def list_daily_totals(
        self, session: AsyncSession, profile_id: int, start_date: date, end_date: date
    ) -> list[tuple[date, Decimal]]:
        result = await session.execute(
            select(ExerciseLog.log_date, func.sum(ExerciseLog.calorie_kcal))
            .where(
                ExerciseLog.profile_id == profile_id,
                ExerciseLog.log_date >= start_date,
                ExerciseLog.log_date <= end_date,
            )
            .group_by(ExerciseLog.log_date)
            .order_by(ExerciseLog.log_date)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def list_profile_ids_with_logs_in_range(
        self, session: AsyncSession, start_date: date, end_date: date
    ) -> list[int]:
        """주간 AI 리포트 대상자 선정용 - `habit_repository.py`의
        `list_profile_ids_with_selections_in_range`와 같은 패턴."""
        result = await session.execute(
            select(ExerciseLog.profile_id)
            .where(ExerciseLog.log_date >= start_date, ExerciseLog.log_date <= end_date)
            .distinct()
        )
        return list(result.scalars().all())
