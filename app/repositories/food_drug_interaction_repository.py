"""(T-DOC-3 후속) 식약처 「약과 음식 상호작용을 피하는 복약안내서」 참조 테이블 조회.

`app/database/food_drug_interaction.db`는 `app/scripts/build_food_drug_interaction_db.py`가
`food_drug_interaction_reference.json`(원문 그대로 보존하는 리뷰용 소스)으로부터 생성하는
파생 산출물이다 — `drug_light.db`가 `drugs_full.db`에서 파생되는 것과 같은 패턴. 원문 텍스트를
고치고 싶으면 JSON을 고친 뒤 빌드 스크립트를 다시 돌려야 한다(DB 파일을 직접 편집하지 않는다).

카테고리 수(35)와 성분 수(156)가 작아 매 요청마다 조회하지 않고 최초 1회 전체를 읽어
프로세스 메모리에 캐싱한다 — 이전 JSON 로딩과 동일한 캐싱 전략이며, 성분명 포함 매칭
(`medication_service._match_food_drug_reference`)은 여전히 파이썬에서 수행한다(품목명이
성분명을 포함하는지 판별해야 해서 SQL 인덱스로 가속할 수 있는 형태가 아니다).

(T-DOC-4 후속, 2026-07-15) `food_drug_food_items` 테이블은 빌드 스크립트가
`food_item_extraction.group_sentences_by_food_name()`으로 음식/알코올 상호작용 원문을 음식별
문장으로 미리 쪼개 저장해둔 결과다 — `medication_service._build_food_interaction_guide_card`가
매 요청마다 다시 계산하지 않고 이 테이블을 그대로 읽어 `GuideCard.food_items`를 채운다.

`polarity` 컬럼("avoid" 기본값 / "recommend" / "timing_caution")은 원문이 그 음식을 그냥
피하라는 게 아닌 소수의 예외를 표시한다 — "recommend"는 이 약과 함께 먹으라고 권장하는
경우(예: NSAIDs+우유), "timing_caution"은 동시 섭취는 피해야 하지만 복용 시간과 1~2시간
간격만 두면 섭취해도 되는 경우(예: 자몽주스+칼슘채널차단제)다. 자동 판별이 아니라
`build_food_drug_interaction_db.py`의 `_RECOMMEND_OVERRIDES`/`_TIMING_CAUTION_OVERRIDES`에
사람이 원문을 읽고 확인해 수동으로 등록한 목록이다."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "food_drug_interaction.db")


class FoodDrugInteractionRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._cache: list[dict] | None = None

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def load_categories(self) -> list[dict]:
        """카테고리별 성분/음식·알코올 상호작용 원문을 원본 JSON과 동일한 딕셔너리 형태로 반환한다."""
        if self._cache is not None:
            return self._cache

        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, category, drug_class, food_interaction, alcohol_interaction, source_page "
                "FROM food_drug_categories ORDER BY id"
            )
            category_rows = cursor.fetchall()

            cursor.execute("SELECT category_id, name_ko, name_en FROM food_drug_ingredients ORDER BY id")
            ingredients_by_category: dict[int, list[dict]] = {}
            for category_id, name_ko, name_en in cursor.fetchall():
                ingredients_by_category.setdefault(category_id, []).append({"name_ko": name_ko, "name_en": name_en})

            cursor.execute("SELECT category_id, food_name, detail, polarity FROM food_drug_food_items ORDER BY id")
            food_items_by_category: dict[int, list[dict]] = {}
            for category_id, food_name, detail, polarity in cursor.fetchall():
                food_items_by_category.setdefault(category_id, []).append(
                    {"name": food_name, "detail": detail, "polarity": polarity}
                )

            self._cache = [
                {
                    "category": category,
                    "drug_class": drug_class,
                    "ingredients": ingredients_by_category.get(category_id, []),
                    "food_interaction": food_interaction,
                    "alcohol_interaction": alcohol_interaction,
                    "source_page": source_page,
                    "food_items": food_items_by_category.get(category_id, []),
                }
                for category_id, category, drug_class, food_interaction, alcohol_interaction, source_page in category_rows
            ]
            return self._cache
        finally:
            conn.close()
