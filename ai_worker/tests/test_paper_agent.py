"""
T-LLM-7/7-1/7-2: 질환 논문 검색 파이프라인 회귀 테스트.

주의(중요) — 이 테스트들은 "판단력 시험"의 회귀 방지용일 뿐이다. LLM 호출을
모킹하므로 우리가 짠 시나리오만 검증하며, 실제 LLM이 무관한 질문에 도구를 정말
호출하지 않는지는 이 테스트로 보장되지 않는다. 진짜 판단력은 `OPENAI_API_KEY`를
채운 상태로 최소 1회 수동 실행(`ask_paper_agent`)해서 눈으로 확인해야 한다.
"""

from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from ai_worker.main import app
from ai_worker.tasks import paper_agent as paper_agent_module
from ai_worker.tasks.paper_agent import QueryClassification
from ai_worker.tools.paper_search import search_disease_paper


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    original_api_key = paper_agent_module.settings.OPENAI_API_KEY
    yield
    paper_agent_module.settings.OPENAI_API_KEY = original_api_key


def test_search_disease_paper_returns_stub_for_supported_disease():
    result = search_disease_paper.invoke({"disease": "당뇨"})

    assert "Continuous Glucose Monitoring" in result
    assert "HbA1c" in result


def test_search_disease_paper_reports_unsupported_disease():
    result = search_disease_paper.invoke({"disease": "감기"})

    assert "찾지 못했습니다" in result


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


def _fake_classify(disease: str | None, is_information_request: bool):
    async def _classify(question: str) -> QueryClassification:
        return QueryClassification(disease=disease, is_information_request=is_information_request)

    return _classify


class FakeAnswerLLM:
    """_build_llm()이 만드는 실제 ChatOpenAI 대신, 고정된 답변을 돌려준다."""

    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages: list[dict]) -> _FakeMessage:
        return _FakeMessage(self._content)


async def test_paper_agent_searches_when_disease_and_information_request(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("당뇨", True))
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeAnswerLLM("HbA1c가 감소했습니다."))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨병 논문 알려줘"})

    assert response.status_code == 200
    assert "HbA1c" in response.json()["answer"]


async def test_paper_agent_refuses_when_disease_mentioned_but_not_information_request(monkeypatch):
    """관용구 케이스: 질환 단어는 감지돼도(예: "심장") 정보 요청이 아니면 도구를 안 부른다."""
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("심장질환", False))
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeAnswerLLM("도움이 필요하시면 말씀해 주세요."))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "나 심장이 너무 쫄려..."})

    assert response.status_code == 200
    assert response.json()["answer"] == "도움이 필요하시면 말씀해 주세요."


async def test_paper_agent_refuses_when_no_disease_mentioned(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify(None, False))
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeAnswerLLM("논문 검색 범위 밖의 질문입니다."))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "오늘 날씨 어때"})

    assert response.status_code == 200
    assert response.json()["answer"] == "논문 검색 범위 밖의 질문입니다."


async def test_paper_agent_returns_503_without_api_key(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨 논문 알려줘"})

    assert response.status_code == 503


def test_build_llm_uses_temperature_zero(monkeypatch):
    """분류/답변 생성은 결정적이어야 하므로 temperature=0으로 생성해야 한다(기본 0.7 방지)."""
    captured: dict = {}

    class CapturingChatOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "ChatOpenAI", CapturingChatOpenAI)

    paper_agent_module._build_llm()

    assert captured["temperature"] == 0


def test_is_valid_disease_rejects_literal_null_string():
    """with_structured_output이 이따금 실제 None 대신 문자열 "null"을 반환하는 경우 방어."""
    assert paper_agent_module._is_valid_disease("null") is False
    assert paper_agent_module._is_valid_disease("NONE") is False
    assert paper_agent_module._is_valid_disease(None) is False
    assert paper_agent_module._is_valid_disease("당뇨") is True
