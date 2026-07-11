from collections import Counter

from app.scripts.generate_health_content import build_fixture_entries
from app.services.content_service import CATEGORIES, CATEGORY_TOPICS, POPULAR_DISEASES


async def fake_generate(disease_code: str, category: str, topic: str) -> dict:
    return {"title": f"{disease_code}-{category}-{topic}", "summary": "s", "body": "b", "image_prompt": None}


async def test_build_fixture_entries_covers_all_diseases_categories_and_topics():
    """장르(카테고리)당 최소 3장이 보이도록, 질환x카테고리마다 소주제 3개를 각각 생성한다."""
    entries = await build_fixture_entries(fake_generate)

    topics_per_category = len(next(iter(CATEGORY_TOPICS.values())))
    assert len(entries) == len(POPULAR_DISEASES) * len(CATEGORIES) * topics_per_category
    assert all("title" in e and "body" in e for e in entries)

    counts = Counter((e["disease_code"], e["category"]) for e in entries)
    assert set(counts.values()) == {topics_per_category}
    assert set(counts.keys()) == {(d, c) for d in POPULAR_DISEASES for c in CATEGORIES}


async def test_build_fixture_entries_backdates_content_date_per_topic_to_avoid_collision():
    """같은 (질환, 카테고리) 안의 소주제 카드들은 DB 유니크 제약(질환+카테고리+날짜)을
    피하도록 서로 다른 날짜가 배정돼야 한다."""
    entries = await build_fixture_entries(fake_generate)

    diabetes_lifestyle_dates = {e["content_date"] for e in entries if e["disease_code"] == "당뇨" and e["category"] == "LIFESTYLE"}

    assert len(diabetes_lifestyle_dates) == len(CATEGORY_TOPICS["LIFESTYLE"])
