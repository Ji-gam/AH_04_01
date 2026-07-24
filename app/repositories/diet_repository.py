from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diet_logs import DietLog
from app.models.food_nutrition_cache import FoodNutritionCache


class DietRepository:
    async def get_cached_food(self, session: AsyncSession, query_name: str) -> FoodNutritionCache | None:
        result = await session.execute(select(FoodNutritionCache).where(FoodNutritionCache.query_name == query_name))
        return result.scalar_one_or_none()

    async def save_cached_food(self, session: AsyncSession, query_name: str, results: list[dict]) -> None:
        existing = await self.get_cached_food(session, query_name)
        if existing is not None:
            existing.results = results
        else:
            session.add(FoodNutritionCache(query_name=query_name, results=results))
        try:
            await session.commit()
        except IntegrityError:
            # 동시에 같은 검색어를 캐싱하려던 다른 요청이 먼저 커밋한 경우 - 캐시일 뿐이라
            # 이 요청은 그냥 조용히 넘어가도 된다(어차피 다음 조회부터 캐시 히트).
            await session.rollback()

    async def create_log(
        self,
        session: AsyncSession,
        profile_id: int,
        log_date: date,
        food_name: str,
        serving_multiplier: Decimal,
        serving_grams: Decimal,
        calorie_kcal: Decimal,
        protein_g: Decimal,
        carb_g: Decimal,
        fat_g: Decimal,
    ) -> DietLog:
        log = DietLog(
            profile_id=profile_id,
            log_date=log_date,
            food_name=food_name,
            serving_multiplier=serving_multiplier,
            serving_grams=serving_grams,
            calorie_kcal=calorie_kcal,
            protein_g=protein_g,
            carb_g=carb_g,
            fat_g=fat_g,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

    async def get_log(self, session: AsyncSession, profile_id: int, log_id: int) -> DietLog | None:
        result = await session.execute(select(DietLog).where(DietLog.id == log_id, DietLog.profile_id == profile_id))
        return result.scalar_one_or_none()

    async def delete_log(self, session: AsyncSession, profile_id: int, log_id: int) -> bool:
        log = await self.get_log(session, profile_id, log_id)
        if log is None:
            return False
        await session.execute(delete(DietLog).where(DietLog.id == log_id, DietLog.profile_id == profile_id))
        await session.commit()
        return True

    async def list_logs_for_date(self, session: AsyncSession, profile_id: int, log_date: date) -> list[DietLog]:
        result = await session.execute(
            select(DietLog)
            .where(DietLog.profile_id == profile_id, DietLog.log_date == log_date)
            .order_by(DietLog.created_at)
        )
        return list(result.scalars().all())

    async def list_daily_totals(
        self, session: AsyncSession, profile_id: int, start_date: date, end_date: date
    ) -> list[tuple[date, Decimal]]:
        result = await session.execute(
            select(DietLog.log_date, func.sum(DietLog.calorie_kcal))
            .where(
                DietLog.profile_id == profile_id,
                DietLog.log_date >= start_date,
                DietLog.log_date <= end_date,
            )
            .group_by(DietLog.log_date)
            .order_by(DietLog.log_date)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def list_profile_ids_with_logs_in_range(
        self, session: AsyncSession, start_date: date, end_date: date
    ) -> list[int]:
        """주간 AI 리포트 대상자 선정용 - `habit_repository.py`의
        `list_profile_ids_with_selections_in_range`와 같은 패턴."""
        result = await session.execute(
            select(DietLog.profile_id).where(DietLog.log_date >= start_date, DietLog.log_date <= end_date).distinct()
        )
        return list(result.scalars().all())
