"""(T-DOC-3 후속, 2026-07-16 MySQL 이전) 식약처 「약과 음식 상호작용을 피하는 복약안내서」
참조 테이블 조회.

기존에는 `app/database/food_drug_interaction.db`(SQLite, 파생 산출물)를 각자 로컬에서 직접
읽었으나, 팀 전체가 공유하는 하나의 DB에서 조회하도록 MySQL로 이전했다(멘토 피드백). 원문
소스(`food_drug_interaction_reference.json`)와 SQLite 빌드 스크립트는 그대로 두고,
`app/scripts/seed_food_drug_interaction.py`가 그 SQLite 파일을 읽어 MySQL 테이블에 시딩한다.

카테고리 수(35)와 성분 수(156)가 작아 매 요청마다 조회하지 않고 앱 기동 시(`app.main.lifespan`)
1회 전체를 읽어 프로세스 메모리에 캐싱한다 — 이전 SQLite 캐싱 전략과 동일. 성분명 포함 매칭
(`medication_service._match_food_drug_reference`)은 여전히 동기 파이썬 코드라, DB 조회 자체는
비동기(`refresh`)로 하되 이후 조회(`load_categories`)는 캐시에서 동기로 반환한다.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.food_drug_interaction import FoodDrugCategory


class FoodDrugInteractionRepository:
    def __init__(self) -> None:
        self._cache: list[dict] | None = None

    async def refresh(self, session: AsyncSession) -> list[dict]:
        """MySQL에서 전체 카테고리/성분/음식 항목을 읽어 캐시를 채운다. 앱 기동 시 1회 호출."""
        result = await session.execute(
            select(FoodDrugCategory)
            .options(selectinload(FoodDrugCategory.ingredients), selectinload(FoodDrugCategory.food_items))
            .order_by(FoodDrugCategory.id)
        )
        categories = result.scalars().all()

        self._cache = [
            {
                "category": category.category,
                "drug_class": category.drug_class,
                "ingredients": [
                    {"name_ko": ingredient.name_ko, "name_en": ingredient.name_en}
                    for ingredient in category.ingredients
                ],
                "food_interaction": category.food_interaction,
                "alcohol_interaction": category.alcohol_interaction,
                "source_page": category.source_page,
                "food_items": [
                    {"name": item.food_name, "detail": item.detail, "polarity": item.polarity}
                    for item in category.food_items
                ],
            }
            for category in categories
        ]
        return self._cache

    def load_categories(self) -> list[dict]:
        """카테고리별 성분/음식·알코올 상호작용 원문을 원본 JSON과 동일한 딕셔너리 형태로 반환한다.

        `refresh()`가 앱 기동 시 캐시를 채워둔다는 전제. 아직 채워지지 않았다면 빈 리스트를
        반환한다(요청을 실패시키기보다 매칭 결과 없음으로 안전하게 처리)."""
        return self._cache if self._cache is not None else []
