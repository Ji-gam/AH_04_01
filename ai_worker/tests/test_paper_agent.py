"""
T-LLM-7: 질환 논문 검색 도구/에이전트 회귀 테스트.

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


def _fake_rewrite(result: str | None):
    """rewrite_disease_query를 대체할 고정 결과 반환 함수를 만든다."""

    async def _rewrite(question: str) -> str | None:
        return result

    return _rewrite


class FakeAgentExecutor:
    """실제 LangChain 에이전트(create_agent) 대신, "이 질문엔 도구를 불렀을 것"을 시뮬레이션한다."""

    def __init__(self, should_call_tool: bool, disease: str | None = None) -> None:
        self._should_call_tool = should_call_tool
        self._disease = disease

    async def ainvoke(self, state: dict) -> dict:
        if self._should_call_tool:
            paper = search_disease_paper.invoke({"disease": self._disease})
            content = f"논문을 찾았습니다.\n{paper}"
        else:
            content = "논문 검색 범위 밖의 질문입니다."
        return {"messages": [*state["messages"], _FakeMessage(content)]}


async def test_paper_agent_calls_tool_for_relevant_question(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "rewrite_disease_query", _fake_rewrite("당뇨"))
    monkeypatch.setattr(
        paper_agent_module,
        "_build_agent_executor",
        lambda: FakeAgentExecutor(should_call_tool=True, disease="당뇨"),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨병 논문 알려줘"})

    assert response.status_code == 200
    assert "HbA1c" in response.json()["answer"]


async def test_paper_agent_skips_tool_for_irrelevant_question(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "rewrite_disease_query", _fake_rewrite(None))
    monkeypatch.setattr(
        paper_agent_module,
        "_build_agent_executor",
        lambda: FakeAgentExecutor(should_call_tool=False),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "오늘 날씨 어때"})

    assert response.status_code == 200
    assert response.json()["answer"] == "논문 검색 범위 밖의 질문입니다."


async def test_paper_agent_returns_503_without_api_key(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨 논문 알려줘"})

    assert response.status_code == 503


class FakeChatModel:
    """rewrite_disease_query가 쓰는 ChatOpenAI 대신, 고정된 정규화 결과를 돌려준다."""

    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages: list[dict]) -> _FakeMessage:
        return _FakeMessage(self._content)


async def test_rewrite_disease_query_normalizes_variant_expression(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeChatModel("뇌혈관질환"))

    result = await paper_agent_module.rewrite_disease_query("뇌졸중 치료는 빠를수록 좋다는 게 사실이야?")

    assert result == "뇌혈관질환"


async def test_rewrite_disease_query_returns_none_for_irrelevant_question(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeChatModel("NONE"))

    result = await paper_agent_module.rewrite_disease_query("오늘 날씨 어때")

    assert result is None


async def test_rewrite_disease_query_passes_through_unsupported_disease(monkeypatch):
    """지원 5개 밖의 질환(예: ADHD)도 그대로 통과시킨다 — 화이트리스트 필터링은 여기서 안 함."""
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeChatModel("ADHD"))

    result = await paper_agent_module.rewrite_disease_query("ADHD 관련 논문 있어?")

    assert result == "ADHD"
