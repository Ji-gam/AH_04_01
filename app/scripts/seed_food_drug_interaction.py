"""`app/database/food_drug_interaction.db`(SQLite, `build_food_drug_interaction_db.py`가
`food_drug_interaction_reference.json`에서 생성한 파생 산출물)를 읽어 MySQL
(`food_drug_sources`/`food_drug_categories`/`food_drug_ingredients`/`food_drug_food_items`)에
시딩한다.

원문 소스와 SQLite 빌드 스크립트는 그대로 둔다 — 저장 형식만 SQLite에서 MySQL로 바꿨다
(팀 전체가 로컬 파일 대신 공유 DB에서 조회하도록, 2026-07-16 멘토 피드백). 이미 시딩된 MySQL에
다시 실행하면 기존 행을 전부 지우고 SQLite 파일 내용으로 재생성한다(참조 데이터라 증분 갱신할
이유가 없고, SQLite 원본이 갱신되면 그대로 다시 반영되어야 하기 때문).

실행: uv run python -m app.scripts.seed_food_drug_interaction
"""

import asyncio
import sqlite3
from pathlib import Path

from sqlalchemy import delete

from app.core.db.databases import AsyncSessionLocal
from app.models.food_drug_interaction import (
    FoodDrugCategory,
    FoodDrugFoodItem,
    FoodDrugIngredient,
    FoodDrugSource,
)

SQLITE_PATH = Path(__file__).parent.parent / "database" / "food_drug_interaction.db"


def _read_sqlite(sqlite_path: Path) -> dict:
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.row_factory = sqlite3.Row
        source = conn.execute("SELECT * FROM food_drug_source").fetchone()
        categories = conn.execute(
            "SELECT id, category, drug_class, food_interaction, alcohol_interaction, source_page "
            "FROM food_drug_categories ORDER BY id"
        ).fetchall()
        ingredients = conn.execute(
            "SELECT category_id, name_ko, name_en FROM food_drug_ingredients ORDER BY id"
        ).fetchall()
        food_items = conn.execute(
            "SELECT category_id, food_name, detail, polarity FROM food_drug_food_items ORDER BY id"
        ).fetchall()
        return {
            "source": dict(source) if source else {},
            "categories": [dict(row) for row in categories],
            "ingredients": [dict(row) for row in ingredients],
            "food_items": [dict(row) for row in food_items],
        }
    finally:
        conn.close()


async def seed_food_drug_interaction(sqlite_path: Path = SQLITE_PATH) -> int:
    data = _read_sqlite(sqlite_path)

    async with AsyncSessionLocal() as session:
        await session.execute(delete(FoodDrugFoodItem))
        await session.execute(delete(FoodDrugIngredient))
        await session.execute(delete(FoodDrugCategory))
        await session.execute(delete(FoodDrugSource))

        if data["source"]:
            session.add(FoodDrugSource(**{k: v for k, v in data["source"].items() if k != "id"}))

        old_id_to_category = {}
        for row in data["categories"]:
            old_id = row["id"]
            category = FoodDrugCategory(
                category=row["category"],
                drug_class=row["drug_class"],
                food_interaction=row["food_interaction"],
                alcohol_interaction=row["alcohol_interaction"],
                source_page=row["source_page"],
            )
            session.add(category)
            old_id_to_category[old_id] = category

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
    count = await seed_food_drug_interaction()
    print(f"{count}개 카테고리 MySQL 시딩 완료")


if __name__ == "__main__":
    asyncio.run(_main())
