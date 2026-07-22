"""새 MySQL 환경에서 음식-약물 상호작용 참조 데이터를 처음부터 채워야 할 때 쓰는 1회성 오프라인
부트스트랩 스크립트.

`app/scripts/seed_food_drug_interaction.py`는 (T-MED-15) "원본 데이터가 이미 운영 MySQL
(ai_health)에 있다"고 가정하고 MySQL -> MySQL(주로 테스트 DB)만 복사한다. 최초 적재 경로
(`food_drug_interaction_reference.json` -> MySQL)는 이전에 `food_drug_interaction.db`(SQLite)를
거쳐 이뤄졌는데, T-MED-15 때 SQLite 조회 경로를 걷어내면서 최초 적재 스크립트도 함께 없어졌다.
이 스크립트는 SQLite를 거치지 않고 JSON을 직접 읽어 MySQL에 넣어 그 빠진 경로를 대체한다.

카테고리별 음식 문장 추출/극성(overrides) 로직은 `build_food_drug_interaction_db.py`와 완전히
동일해야 하므로(다른 결과가 나오면 리뷰된 적 없는 새 규칙이 생기는 셈) 그 모듈의 함수/상수를
그대로 재사용한다.

실행: uv run python -m app.scripts.bootstrap_food_drug_from_json [reference.json 경로]
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import delete

from app.core.db.databases import AsyncSessionLocal
from app.models.food_drug_interaction import (
    FoodDrugCategory,
    FoodDrugFoodItem,
    FoodDrugIngredient,
    FoodDrugSource,
)
from app.scripts.build_food_drug_interaction_db import (
    _RECOMMEND_OVERRIDES,
    _TIMING_CAUTION_OVERRIDES,
    _merged_food_items,
)

DEFAULT_JSON_PATH = Path(__file__).parent.parent / "database" / "food_drug_interaction_reference.json"


async def bootstrap_food_drug_from_json(json_path: Path = DEFAULT_JSON_PATH) -> int:
    """운영 MySQL(`ai_health`)의 음식-약물 참조 테이블을 `json_path` 내용으로 전체 삭제 후
    재적재한다."""
    if not json_path.exists():
        raise FileNotFoundError(f"{json_path}가 없습니다 — 백업(database.zip)에서 복원하세요.")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    matched_recommend_overrides: set[tuple[str, str]] = set()
    matched_timing_overrides: set[tuple[str, str]] = set()

    async with AsyncSessionLocal() as session:
        await session.execute(delete(FoodDrugFoodItem))
        await session.execute(delete(FoodDrugIngredient))
        await session.execute(delete(FoodDrugCategory))
        await session.execute(delete(FoodDrugSource))

        source = data["source"]
        session.add(
            FoodDrugSource(
                title=source.get("title"),
                publisher=source.get("publisher"),
                published=source.get("published"),
                url=source.get("url"),
                note=source.get("note"),
                not_covered=source.get("not_covered"),
            )
        )

        category_count = 0
        ingredient_count = 0
        food_item_count = 0

        for category_row in data["categories"]:
            category = FoodDrugCategory(
                category=category_row["category"],
                drug_class=category_row["drug_class"],
                food_interaction=category_row.get("food_interaction"),
                alcohol_interaction=category_row.get("alcohol_interaction"),
                source_page=category_row.get("source_page"),
            )
            session.add(category)
            await session.flush()
            category_count += 1

            for ing in category_row["ingredients"]:
                session.add(
                    FoodDrugIngredient(category_id=category.id, name_ko=ing.get("name_ko"), name_en=ing.get("name_en"))
                )
                ingredient_count += 1

            for name, detail in _merged_food_items(
                category_row.get("food_interaction"), category_row.get("alcohol_interaction")
            ):
                override_key = (category_row["drug_class"], name)
                if override_key in _RECOMMEND_OVERRIDES:
                    matched_recommend_overrides.add(override_key)
                    polarity = "recommend"
                elif override_key in _TIMING_CAUTION_OVERRIDES:
                    matched_timing_overrides.add(override_key)
                    polarity = "timing_caution"
                else:
                    polarity = "avoid"
                session.add(FoodDrugFoodItem(category_id=category.id, food_name=name, detail=detail, polarity=polarity))
                food_item_count += 1

        unused_recommend = _RECOMMEND_OVERRIDES - matched_recommend_overrides
        if unused_recommend:
            raise ValueError(f"_RECOMMEND_OVERRIDES에 매칭되지 않은 항목이 있습니다(오타 의심): {unused_recommend}")
        unused_timing = _TIMING_CAUTION_OVERRIDES - matched_timing_overrides
        if unused_timing:
            raise ValueError(f"_TIMING_CAUTION_OVERRIDES에 매칭되지 않은 항목이 있습니다(오타 의심): {unused_timing}")

        await session.commit()
        print(f"카테고리 {category_count:,}건, 성분 {ingredient_count:,}건, 음식 항목 {food_item_count:,}건 시딩 완료")
        return category_count


async def _main() -> None:
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JSON_PATH
    await bootstrap_food_drug_from_json(json_path)


if __name__ == "__main__":
    asyncio.run(_main())
