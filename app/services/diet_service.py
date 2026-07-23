from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.diet_dto import (
    DietLogCreateRequest,
    DietLogItemResult,
    DietRecentDayResult,
    DietRecentResult,
    DietTodayResult,
    FoodSearchResult,
    FoodSearchResultItem,
)
from app.models.profiles import Profile
from app.repositories.diet_repository import DietRepository
from app.services import food_nutrition_open_api_client

# 목표 체중/칼로리 개인화 필드가 아직 없어서(F-GOAL 미구현), 개인화 없이 일반 성인 권장
# 섭취량으로 비교한다. 나중에 개인 목표 칼로리가 생기면 이 상수 대신 그 값을 쓰면 된다.
DIET_REFERENCE_KCAL = 2000


def _raw_item_to_dto(item: food_nutrition_open_api_client.RawFoodItem) -> FoodSearchResultItem:
    return FoodSearchResultItem(
        food_name=item.food_name,
        serving_size_g=item.serving_size_g,
        calorie_kcal_per_100g=item.calorie_kcal_per_100g,
        protein_g_per_100g=item.protein_g_per_100g,
        carb_g_per_100g=item.carb_g_per_100g,
        fat_g_per_100g=item.fat_g_per_100g,
    )


class DietService:
    def __init__(self, repository: DietRepository | None = None) -> None:
        self._repository = repository or DietRepository()

    async def search_food(self, session: AsyncSession, query: str) -> FoodSearchResult:
        normalized = query.strip()
        if len(normalized) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어를 입력해주세요.")

        cached = await self._repository.get_cached_food(session, normalized)
        if cached is not None:
            return FoodSearchResult(results=[FoodSearchResultItem(**row) for row in cached.results])

        raw_items = await food_nutrition_open_api_client.search_food(normalized)
        items = [_raw_item_to_dto(raw) for raw in raw_items]
        if items:
            await self._repository.save_cached_food(session, normalized, [item.model_dump() for item in items])
        return FoodSearchResult(results=items)

    async def log_food(self, session: AsyncSession, profile: Profile, request: DietLogCreateRequest) -> DietTodayResult:
        multiplier = Decimal(str(request.serving_multiplier))
        serving_grams = Decimal(str(request.serving_size_g)) * multiplier
        ratio = serving_grams / Decimal(100)

        await self._repository.create_log(
            session,
            profile_id=profile.id,
            log_date=date.today(),
            food_name=request.food_name,
            serving_multiplier=multiplier,
            serving_grams=serving_grams,
            calorie_kcal=Decimal(str(request.calorie_kcal_per_100g)) * ratio,
            protein_g=Decimal(str(request.protein_g_per_100g)) * ratio,
            carb_g=Decimal(str(request.carb_g_per_100g)) * ratio,
            fat_g=Decimal(str(request.fat_g_per_100g)) * ratio,
        )
        return await self.get_today(session, profile)

    async def get_today(self, session: AsyncSession, profile: Profile) -> DietTodayResult:
        logs = await self._repository.list_logs_for_date(session, profile.id, date.today())
        items = [
            DietLogItemResult(
                id=log.id,
                food_name=log.food_name,
                serving_grams=float(log.serving_grams),
                calorie_kcal=float(log.calorie_kcal),
                protein_g=float(log.protein_g),
                carb_g=float(log.carb_g),
                fat_g=float(log.fat_g),
                logged_at=log.created_at,
            )
            for log in logs
        ]
        return DietTodayResult(
            logs=items,
            total_kcal=sum(i.calorie_kcal for i in items),
            total_protein_g=sum(i.protein_g for i in items),
            total_carb_g=sum(i.carb_g for i in items),
            total_fat_g=sum(i.fat_g for i in items),
            reference_kcal=DIET_REFERENCE_KCAL,
        )

    async def delete_log(self, session: AsyncSession, profile: Profile, log_id: int) -> DietTodayResult:
        deleted = await self._repository.delete_log(session, profile.id, log_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 기록을 찾을 수 없습니다.")
        return await self.get_today(session, profile)

    async def get_recent(self, session: AsyncSession, profile: Profile) -> DietRecentResult:
        end = date.today()
        start = end - timedelta(days=6)
        totals = dict(await self._repository.list_daily_totals(session, profile.id, start, end))
        days = [
            DietRecentDayResult(log_date=day, total_kcal=float(totals.get(day, 0)))
            for day in (start + timedelta(days=offset) for offset in range(7))
        ]
        return DietRecentResult(days=days)
