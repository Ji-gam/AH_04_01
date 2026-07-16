"""
ai_worker는 app/와 별도 FastAPI 앱이라 별도 dependency group("ai")이 필요하다.
`uv sync --group ai` 후 `uv run pytest ai_worker/tests`로 실행한다(기본 `pytest`
테스트 대상인 app/tests에는 포함하지 않는다 — pyproject.toml의 testpaths 참고).

T-LLM-7-3-2: 기존 /retrieve 엔드포인트(DUR 전용 청크 반환)는 통합 스트리밍
엔드포인트(/agent/chat, test_chat_agent.py 참고)로 대체되어 삭제됐다. 여기서는
db_holder 재노출과 /health만 검증한다.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from ai_worker.main import app, db_holder


class FakeChromaDb:
    def __init__(self, docs_with_scores: list[tuple]) -> None:
        self._docs_with_scores = docs_with_scores


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


async def test_health_check_reports_db_not_loaded_state():
    db_holder["db"] = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "db_loaded": False}
