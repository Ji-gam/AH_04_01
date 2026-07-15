"""개발자가 로컬에서 1회 실행하는 오프라인 빌드 스크립트. `food_drug_interaction_reference.json`
(식약처 PDF 가이드북을 파싱한 원문 보존용 소스, 리뷰 시 diff로 원문 변경 여부를 확인하기 위해
JSON으로 유지)를 읽어 `app/database/food_drug_interaction.db`(SQLite)를 생성한다.
`drug_light.db`(scripts/drug_info_sync/run_db.py)와 같은 패턴: 소스는 git에서 리뷰하고,
파생 DB 파일을 커밋해 팀 전체가 재빌드 없이 바로 쓴다.

JSON 원문 텍스트를 고치고 싶으면 이 스크립트가 아니라 JSON 파일을 고친 뒤 다시 실행해야 한다.

(T-DOC-4 후속, 2026-07-15) `food_drug_food_items` 테이블은 각 카테고리의 `food_interaction`/
`alcohol_interaction` 원문 문단에서 `food_item_extraction.group_sentences_by_food_name()`(V1
규칙 기반 추출, `medication_service.py`의 e약은요 폴백 경로와 동일한 사전/로직 공유)으로 음식별
문장을 미리 뽑아 저장한다 — 요청마다 다시 계산하지 않기 위해서다. 같은 음식명이 음식/알코올 두
문단 모두에 나오면 문장을 합쳐 한 행으로 저장한다.

(2026-07-15) `polarity` 컬럼: 이 규칙 기반 추출은 문장에 음식명이 등장하는지만 보고 그 문장이
"피하라"는 건지 "함께 먹으면 좋다"는 건지 맥락을 판단하지 못한다 — 예를 들어 NSAIDs 항목은
"위장장애가 있으면 우유와 함께 복용하세요"(권장)인데도 다른 항목과 똑같이 주의 칩으로 뜨는 문제가
있었다(실사용 리포트). 자동으로 "긍정 어투 감지" 같은 걸 시도하면 실제로 피해야 할 음식(예:
자몽주스+칼슘채널차단제의 "복용 후 2시간 뒤에 마시는 것이 좋다"는 여전히 회피 지시인데 "좋다"라는
말 때문에 오탐)을 "권장"으로 잘못 분류할 위험이 더 크므로, 자동 분류 대신 전체 187개 음식 항목을
사람이 직접 읽고 확인한 소수의 예외만 `_RECOMMEND_OVERRIDES`/`_TIMING_CAUTION_OVERRIDES`에 수동
등록한다. 그 외는 전부 기본값 "avoid".

`timing_caution`은 "동시 섭취는 피해야 하지만 복용 시간과 1~2시간 정도만 띄우면 섭취해도 된다"는
구체적인 시차 요령이 원문에 있는 경우다(예: 자몽주스는 칼슘채널차단제 복용 2시간 후엔 마셔도
됨). "~하는 것이 좋다"는 표현이 있어도 그 음식 자체를 권장하는 게 아니라 회피 방법(시차)에 대한
표현이면 `avoid`가 아니라 `timing_caution`으로 구분한다 — 세인트존스워트처럼 "1시간 전/후"가
그 약의 식사 시점 안내일 뿐 해당 음식과 무관한 경우는 제외했다(원문을 직접 읽고 확인).

실행: uv run python -m app.scripts.build_food_drug_interaction_db
"""

import json
import os
import sqlite3

from app.services.food_item_extraction import group_sentences_by_food_name

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "database")
JSON_PATH = os.path.join(DB_DIR, "food_drug_interaction_reference.json")
DB_PATH = os.path.join(DB_DIR, "food_drug_interaction.db")

# (drug_class, food_name) 쌍이 이 목록에 있으면 "avoid"가 아니라 "recommend"로 저장한다.
# 원문을 직접 읽고 확인한 결과 — 전체 187개 음식 항목 중 아래 둘만 "이 약과 함께/식후에 먹으면
# 좋다"는 권장 문맥이고, 나머지는 표현이 부드러워도("좋습니다" 등) 실제로는 회피/시간차 지시다.
_RECOMMEND_OVERRIDES = {
    ("2) 비스테로이드성 소염진통제(NSAIDs)", "우유"),  # 위장장애 완화 목적으로 음식/우유와 복용 권장
    ("6) 조울증 치료제(Bipolar Disorder Medicines)", "우유"),  # 리튬 — 식후 또는 우유와 복용 권장
}

# (drug_class, food_name) 쌍이 이 목록에 있으면 "avoid" 대신 "timing_caution"으로 저장한다.
# 원문을 직접 읽고 확인한 결과 — 동시 섭취는 피해야 하지만 복용 시간과 1~2시간 정도 간격을
# 두면 섭취해도 된다는 구체적인 시차 요령이 있는 경우만 여기 포함했다.
_TIMING_CAUTION_OVERRIDES = {
    # 칼슘채널차단제 복용 후 2시간 뒤엔 자몽주스를 마셔도 됨
    # ("자몽"은 같은 문장에서 "자몽주스"에 포함되는 짧은 이름이라 추출 시 중복 제외되어 항목
    # 자체가 없다 — group_sentences_by_food_name의 substring 억제 규칙)
    ("4) 칼슘채널 차단제(Calcium Channel Inhibitors)", "자몽주스"),
    ("4) 칼슘채널 차단제(Calcium Channel Inhibitors)", "포멜로"),
    # 디곡신 — 식이섬유가 많은 음식은 이 약 복용 전후 2시간을 피해서 섭취
    ("6) 강심배당체(Cardiac Glycosides)", "식이섬유"),
    # 테트라사이클린 복용 1시간 전 또는 2시간 안에만 유제품류를 피하면 됨
    ("1) 항균제 - 나) 테트라사이클린계 항균제(Tetracycline Antibacterials)", "우유"),
    ("1) 항균제 - 나) 테트라사이클린계 항균제(Tetracycline Antibacterials)", "유제품"),
    ("1) 항균제 - 나) 테트라사이클린계 항균제(Tetracycline Antibacterials)", "치즈"),
    ("1) 항균제 - 나) 테트라사이클린계 항균제(Tetracycline Antibacterials)", "아이스크림"),
    # 변비약 — 유제품/제산제 섭취 후 한 시간 뒤에 복용하면 됨
    ("변비약(완하제: Laxatives)", "유제품"),
}


def _merged_food_items(food_interaction: str | None, alcohol_interaction: str | None) -> list[tuple[str, str]]:
    """음식/알코올 문단을 각각 음식명별 문장으로 묶은 뒤, 같은 이름이 양쪽에 다 있으면 문장을
    합쳐 하나로 병합한다. 두 문단을 이어붙여 한 번에 추출하지 않는 이유는, 그렇게 하면 두 텍스트가
    합쳐진 하나의 큰 텍스트로 처리돼 어느 쪽 문단에서 왔는지 구분할 수 없어지기 때문 — 지금은
    구분해서 쓰진 않지만(둘 다 그냥 GuideCard.food_items로 합쳐짐), 원문 문단 경계를 지켜야
    문장 분리 결과가 각 문단만 봤을 때와 동일하게 유지된다."""
    food_groups = group_sentences_by_food_name(food_interaction or "")
    alcohol_groups = group_sentences_by_food_name(alcohol_interaction or "")

    names = list(dict.fromkeys([*food_groups.keys(), *alcohol_groups.keys()]))
    merged = []
    for name in names:
        sentences = list(dict.fromkeys([*food_groups.get(name, []), *alcohol_groups.get(name, [])]))
        merged.append((name, " ".join(sentences)))
    return merged


def build_db(json_path: str = JSON_PATH, db_path: str = DB_PATH) -> None:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE food_drug_source (
                title TEXT,
                publisher TEXT,
                published TEXT,
                url TEXT,
                note TEXT,
                not_covered TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE food_drug_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                drug_class TEXT NOT NULL,
                food_interaction TEXT,
                alcohol_interaction TEXT,
                source_page TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE food_drug_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES food_drug_categories(id),
                name_ko TEXT,
                name_en TEXT
            )
            """
        )
        cursor.execute("CREATE INDEX idx_food_drug_ingredients_category_id ON food_drug_ingredients(category_id)")
        cursor.execute("CREATE INDEX idx_food_drug_ingredients_name_ko ON food_drug_ingredients(name_ko)")
        cursor.execute("CREATE INDEX idx_food_drug_ingredients_name_en ON food_drug_ingredients(name_en)")

        cursor.execute(
            """
            CREATE TABLE food_drug_food_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES food_drug_categories(id),
                food_name TEXT NOT NULL,
                detail TEXT NOT NULL,
                polarity TEXT NOT NULL DEFAULT 'avoid'
                    CHECK (polarity IN ('avoid', 'recommend', 'timing_caution'))
            )
            """
        )
        cursor.execute("CREATE INDEX idx_food_drug_food_items_category_id ON food_drug_food_items(category_id)")

        source = data["source"]
        cursor.execute(
            "INSERT INTO food_drug_source (title, publisher, published, url, note, not_covered) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                source.get("title"),
                source.get("publisher"),
                source.get("published"),
                source.get("url"),
                source.get("note"),
                source.get("not_covered"),
            ),
        )

        matched_recommend_overrides = set()
        matched_timing_overrides = set()
        for category in data["categories"]:
            cursor.execute(
                "INSERT INTO food_drug_categories (category, drug_class, food_interaction, alcohol_interaction, "
                "source_page) VALUES (?, ?, ?, ?, ?)",
                (
                    category["category"],
                    category["drug_class"],
                    category.get("food_interaction"),
                    category.get("alcohol_interaction"),
                    category.get("source_page"),
                ),
            )
            category_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO food_drug_ingredients (category_id, name_ko, name_en) VALUES (?, ?, ?)",
                [(category_id, ing.get("name_ko"), ing.get("name_en")) for ing in category["ingredients"]],
            )

            food_item_rows = []
            for name, detail in _merged_food_items(
                category.get("food_interaction"), category.get("alcohol_interaction")
            ):
                override_key = (category["drug_class"], name)
                if override_key in _RECOMMEND_OVERRIDES:
                    matched_recommend_overrides.add(override_key)
                    polarity = "recommend"
                elif override_key in _TIMING_CAUTION_OVERRIDES:
                    matched_timing_overrides.add(override_key)
                    polarity = "timing_caution"
                else:
                    polarity = "avoid"
                food_item_rows.append((category_id, name, detail, polarity))
            cursor.executemany(
                "INSERT INTO food_drug_food_items (category_id, food_name, detail, polarity) VALUES (?, ?, ?, ?)",
                food_item_rows,
            )

        unused_recommend = _RECOMMEND_OVERRIDES - matched_recommend_overrides
        if unused_recommend:
            raise ValueError(f"_RECOMMEND_OVERRIDES에 매칭되지 않은 항목이 있습니다(오타 의심): {unused_recommend}")
        unused_timing = _TIMING_CAUTION_OVERRIDES - matched_timing_overrides
        if unused_timing:
            raise ValueError(
                f"_TIMING_CAUTION_OVERRIDES에 매칭되지 않은 항목이 있습니다(오타 의심): {unused_timing}"
            )

        conn.commit()
        ingredient_count = cursor.execute("SELECT COUNT(*) FROM food_drug_ingredients").fetchone()[0]
        category_count = cursor.execute("SELECT COUNT(*) FROM food_drug_categories").fetchone()[0]
        food_item_count = cursor.execute("SELECT COUNT(*) FROM food_drug_food_items").fetchone()[0]
        print(
            f"[OK] {db_path} 생성 완료 - 카테고리 {category_count}건, 성분 {ingredient_count}건, "
            f"음식 항목 {food_item_count}건"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    build_db()
