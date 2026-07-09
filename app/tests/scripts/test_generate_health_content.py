from app.scripts.generate_health_content import build_fixture_entries
from app.services.content_service import CATEGORIES, POPULAR_DISEASES


class FakeRetriever:
    async def search(self, query: str, context: dict) -> list[dict]:
        return []


async def fake_generate(disease_code: str, category: str, chunks: list[dict]) -> dict:
    return {"title": f"{disease_code}-{category}", "summary": "s", "body": "b", "image_prompt": None}


async def test_build_fixture_entries_covers_all_diseases_and_categories():
    entries = await build_fixture_entries(FakeRetriever(), fake_generate)

    assert len(entries) == len(POPULAR_DISEASES) * len(CATEGORIES)
    assert {(e["disease_code"], e["category"]) for e in entries} == {
        (d, c) for d in POPULAR_DISEASES for c in CATEGORIES
    }
    assert all("title" in e and "body" in e for e in entries)
