"""
ai_worker는 app/와 별도 FastAPI 앱이라 별도 dependency group("ai")이 필요하다.
`uv sync --group ai` 후 `uv run pytest ai_worker/tests`로 실행한다(기본 `pytest`
테스트 대상인 app/tests에는 포함하지 않는다 — pyproject.toml의 testpaths 참고).
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.documents import Document

from ai_worker.main import app, db_holder


class FakeChromaDb:
    def __init__(self, docs_with_scores: list[tuple[Document, float]]) -> None:
        self._docs_with_scores = docs_with_scores

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        return self._docs_with_scores[:k]


@pytest.fixture(autouse=True)
async def reset_db_holder() -> AsyncIterator[None]:
    original_db = db_holder["db"]
    original_ingr_names = db_holder["ingr_names"]
    yield
    db_holder["db"] = original_db
    db_holder["ingr_names"] = original_ingr_names


async def test_health_check_reports_db_loaded_state():
    db_holder["db"] = FakeChromaDb([])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "db_loaded": True}


async def test_retrieve_returns_chunks_within_similarity_threshold():
    relevant_doc = Document(
        page_content="의약품 성분 [졸피뎀타르타르산염]은 최대 투여기간이 4주입니다.",
        metadata={"source": "dur_mdctn_pd_atent.csv", "ingr_name": "졸피뎀타르타르산염"},
    )
    irrelevant_doc = Document(
        page_content="관련 없는 문서",
        metadata={"source": "dur_efcy_dplct.csv", "ingr_name": "무관성분"},
    )
    db_holder["db"] = FakeChromaDb([(relevant_doc, 0.5), (irrelevant_doc, 2.0)])
    db_holder["ingr_names"] = {"졸피뎀타르타르산염", "무관성분"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/retrieve", json={"query": "졸피뎀 최대 투여기간", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert len(body["chunks"]) == 1
    assert body["chunks"][0]["content"] == relevant_doc.page_content
    assert body["chunks"][0]["metadata"]["source"] == "dur_mdctn_pd_atent.csv"


async def test_retrieve_returns_empty_chunks_when_no_document_matches():
    db_holder["db"] = FakeChromaDb([])
    db_holder["ingr_names"] = set()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/retrieve", json={"query": "무관한 질문", "limit": 3})

    assert response.status_code == 200
    assert response.json() == {"chunks": []}
