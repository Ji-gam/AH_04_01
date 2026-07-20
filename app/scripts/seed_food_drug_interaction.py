"""MySQL(`ai_health`)의 `food_drug_sources`/`food_drug_categories`/`food_drug_ingredients`/
`food_drug_food_items`(운영 데이터, 이미 시딩되어 있음)를 읽어 다른 MySQL 세션(주로 테스트 DB)에
같은 참조 데이터를 다시 심는다.

(T-MED-15) 원래 `app/database/food_drug_interaction.db`(SQLite, `build_food_drug_interaction_db.py`
산출물)를 읽었으나, SQLite를 더 이상 쓰지 않기로 하면서(원본 데이터는 이미 MySQL에 있음) 소스를
MySQL로 바꿨다. `source_session_factory`(기본: 운영 MySQL `AsyncSessionLocal`, 즉 `ai_health`)와
`session_factory`(대상, 테스트 DB 등)가 같은 DB를 가리키면 삭제 후 재삽입 과정에서 원본 데이터가
사라지므로 이를 막는다.

실행: uv run python -m app.scripts.seed_food_drug_interaction <target-db-name>
"""

import asyncio
import sys
from collections.abc import Callable

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db.databases import AsyncSessionLocal
from app.models.food_drug_interaction import (
    FoodDrugCategory,
    FoodDrugFoodItem,
    FoodDrugIngredient,
    FoodDrugSource,
)


class SameDatabaseError(RuntimeError):
    """소스와 대상이 같은 DB를 가리키면(운영 데이터를 지우고 빈 데이터로 재생성하는 사고를
    막기 위해) 시딩을 거부한다."""


async def _read_mysql(source_session: AsyncSession) -> dict:
    source_row = (await source_session.execute(select(FoodDrugSource))).scalars().first()
    source = (
        {
            "title": source_row.title,
            "publisher": source_row.publisher,
            "published": source_row.published,
            "url": source_row.url,
            "note": source_row.note,
            "not_covered": source_row.not_covered,
        }
        if source_row
        else {}
    )
    categories = (await source_session.execute(select(FoodDrugCategory).order_by(FoodDrugCategory.id))).scalars().all()
    ingredients = (
        (await source_session.execute(select(FoodDrugIngredient).order_by(FoodDrugIngredient.id))).scalars().all()
    )
    food_items = (await source_session.execute(select(FoodDrugFoodItem).order_by(FoodDrugFoodItem.id))).scalars().all()
    return {
        "source": source,
        "categories": [
            {
                "id": c.id,
                "category": c.category,
                "drug_class": c.drug_class,
                "food_interaction": c.food_interaction,
                "alcohol_interaction": c.alcohol_interaction,
                "source_page": c.source_page,
            }
            for c in categories
        ],
        "ingredients": [
            {"category_id": i.category_id, "name_ko": i.name_ko, "name_en": i.name_en} for i in ingredients
        ],
        "food_items": [
            {
                "category_id": f.category_id,
                "food_name": f.food_name,
                "detail": f.detail,
                "polarity": f.polarity,
            }
            for f in food_items
        ],
    }


async def _assert_different_database(source_session: AsyncSession, target_session: AsyncSession) -> None:
    source_db = (await source_session.execute(text("SELECT DATABASE()"))).scalar_one()
    target_db = (await target_session.execute(text("SELECT DATABASE()"))).scalar_one()
    if source_db == target_db:
        raise SameDatabaseError(
            f"소스와 대상이 같은 DB({source_db})입니다 — 운영 데이터를 지우고 재생성하는 사고를 "
            "막기 위해 시딩을 중단합니다. 다른 DB(테스트 DB 등)를 대상으로만 실행하세요."
        )


async def seed_food_drug_interaction(
    session_factory: Callable[[], AsyncSession] | async_sessionmaker[AsyncSession],
    source_session_factory: Callable[[], AsyncSession] | async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> int:
    """`session_factory`(대상, 필수 — 테스트 DB 등)에 `source_session_factory`(기본: 운영
    MySQL `ai_health`)의 참조 데이터를 복사한다."""
    async with source_session_factory() as source_session, session_factory() as session:
        await _assert_different_database(source_session, session)
        data = await _read_mysql(source_session)

        await session.execute(delete(FoodDrugFoodItem))
        await session.execute(delete(FoodDrugIngredient))
        await session.execute(delete(FoodDrugCategory))
        await session.execute(delete(FoodDrugSource))

        if data["source"]:
            session.add(FoodDrugSource(**data["source"]))

        old_id_to_category = {}
        for row in data["categories"]:
            category = FoodDrugCategory(
                category=row["category"],
                drug_class=row["drug_class"],
                food_interaction=row["food_interaction"],
                alcohol_interaction=row["alcohol_interaction"],
                source_page=row["source_page"],
            )
            session.add(category)
            old_id_to_category[row["id"]] = category

        # FK를 채우려면 새 category.id가 필요하므로 flush로 먼저 발급받는다.
        await session.flush()

        for row in data["ingredients"]:
            session.add(
                FoodDrugIngredient(
                    category_id=old_id_to_category[row["category_id"]].id,
                    name_ko=row["name_ko"],
                    name_en=row["name_en"],
                )
            )

        for row in data["food_items"]:
            session.add(
                FoodDrugFoodItem(
                    category_id=old_id_to_category[row["category_id"]].id,
                    food_name=row["food_name"],
                    detail=row["detail"],
                    polarity=row["polarity"],
                )
            )

        await session.commit()
        return len(data["categories"])


async def _main() -> None:
    print(
        "이 스크립트는 더 이상 단독 실행 대상이 없습니다 — 원본 데이터가 이미 운영 MySQL(ai_health)에 "
        "있습니다. 테스트 DB 시딩은 app/tests/conftest.py가 session_factory=TestSessionLocal로 "
        "자동 호출합니다.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    asyncio.run(_main())
