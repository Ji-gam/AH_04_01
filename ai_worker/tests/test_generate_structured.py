from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from ai_worker.main import app
from ai_worker.tasks import generate_structured as generate_structured_module


class FakeChain:
    def __init__(self, result: dict) -> None:
        self._result = result

    async def ainvoke(self, messages: list[dict]) -> dict:
        return self._result


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    original_api_key = generate_structured_module.settings.OPENAI_API_KEY
    yield
    generate_structured_module.settings.OPENAI_API_KEY = original_api_key


async def test_generate_structured_returns_data_matching_schema(monkeypatch):
    fake_result = {"title": "당뇨 라이프스타일 팁", "body": "본문"}
    monkeypatch.setattr(generate_structured_module, "_build_chain", lambda json_schema, api_key: FakeChain(fake_result))
    monkeypatch.setattr(generate_structured_module.settings, "OPENAI_API_KEY", "fake-key")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/generate-structured",
            json={
                "system_prompt": "너는 건강 콘텐츠 작가야",
                "user_input": "질환: 당뇨, 카테고리: LIFESTYLE",
                "json_schema": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                },
            },
        )

    assert response.status_code == 200
    assert response.json()["data"] == fake_result


async def test_generate_structured_returns_503_without_api_key(monkeypatch):
    monkeypatch.setattr(generate_structured_module.settings, "OPENAI_API_KEY", None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/generate-structured",
            json={"system_prompt": "sp", "user_input": "ui", "json_schema": {"type": "object"}},
        )

    assert response.status_code == 503


async def test_generate_structured_requires_all_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/generate-structured", json={})

    assert response.status_code == 422
