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


class FakeChatOpenAI:
    """실제 ChatOpenAI 대신, with_structured_output()에 어떤 스키마가 넘어오는지만 캡처한다."""

    def __init__(self, **kwargs) -> None:
        pass

    def with_structured_output(self, json_schema):
        FakeChatOpenAI.received_schema = json_schema
        return FakeChain({"greeting": "안녕"})


def test_build_chain_injects_title_when_missing(monkeypatch):
    """실서비스에서 발견된 회귀: with_structured_output()은 최상위 title 키가 없으면
    'Unsupported function' ValueError를 던진다(OpenAI 함수 이름으로 써야 하기 때문).
    Pydantic의 model_json_schema()는 title을 자동으로 채워주지만, 이 엔드포인트는 범용이라
    title 없는 스키마가 들어와도 죽지 않아야 한다."""
    monkeypatch.setattr(generate_structured_module, "ChatOpenAI", FakeChatOpenAI)

    generate_structured_module._build_chain({"type": "object", "properties": {}}, "fake-key")

    assert FakeChatOpenAI.received_schema["title"] == "GeneratedResponse"


def test_build_chain_keeps_existing_title(monkeypatch):
    monkeypatch.setattr(generate_structured_module, "ChatOpenAI", FakeChatOpenAI)

    generate_structured_module._build_chain({"title": "Custom", "type": "object"}, "fake-key")

    assert FakeChatOpenAI.received_schema["title"] == "Custom"
