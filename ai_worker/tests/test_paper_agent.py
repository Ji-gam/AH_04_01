"""
T-LLM-7/7-1/7-2/7-3: 질환 논문 검색 파이프라인 회귀 테스트.

주의(중요) — 이 테스트들은 "판단력 시험"의 회귀 방지용일 뿐이다. LLM 호출과 벡터
검색(`search_papers`)을 모킹하므로 우리가 짠 시나리오만 검증하며, 실제 LLM이 무관한
질문에 검색을 정말 안 하는지, 실제 임베딩 검색이 유의미한 결과를 주는지는 이 테스트로
보장되지 않는다. 진짜 동작은 `OPENAI_API_KEY`를 채운 상태로 최소 1회 수동 실행해서
눈으로 확인해야 한다. PubMed 수집/색인 자체는 test_ingest_papers.py, 벡터 검색 순수
로직은 test_paper_retrieve_service.py 참고.
"""

from collections.abc import Iterator
from importlib import import_module

import pytest
from httpx import ASGITransport, AsyncClient

from ai_worker.main import app
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.tasks import paper_agent as paper_agent_module
from ai_worker.tasks.ingest import EmbeddingMismatchError, EmbeddingUnavailableError

# `ai_worker/routers/__init__.py`가 `paper_agent_router` 이름을 라우터 인스턴스로
# 재바인딩해두어서, `import ai_worker.routers.paper_agent_router as m`(속성 체이닝으로
# 해석됨)는 모듈이 아니라 그 인스턴스를 가져온다. import_module로 sys.modules에서
# 직접 모듈 객체를 가져와 이 함정을 피한다.
paper_agent_router_module = import_module("ai_worker.routers.paper_agent_router")


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    original_api_key = paper_agent_module.settings.OPENAI_API_KEY
    yield
    paper_agent_module.settings.OPENAI_API_KEY = original_api_key


class _FakePaperDb:
    """ensure_paper_db()가 반환할 자리표시자. search_papers는 아래에서 직접
    몽키패치하므로 실제 Chroma 메서드를 호출할 필요가 없다."""


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeAnswerLLM:
    """_build_llm()이 만드는 실제 ChatOpenAI 대신, 고정된 답변을 돌려준다."""

    def __init__(self, content: str) -> None:
        self._content = content

    async def ainvoke(self, messages: list[dict]) -> _FakeMessage:
        return _FakeMessage(self._content)


def _fake_classify(disease: str | None, is_information_request: bool):
    async def _classify(question: str) -> paper_agent_module.QueryClassification:
        return paper_agent_module.QueryClassification(disease=disease, is_information_request=is_information_request)

    return _classify


def _fake_search_papers(chunks: list[DocumentChunk]):
    def _search(db, query: str, disease: str, limit: int) -> list[DocumentChunk]:
        return chunks

    return _search


@pytest.fixture(autouse=True)
def stub_paper_db(monkeypatch):
    """라우터의 ensure_paper_db()가 실제 Chroma를 열지 않도록 자리표시자로 대체한다."""
    monkeypatch.setattr(paper_agent_router_module, "ensure_paper_db", lambda: _FakePaperDb())


async def test_paper_agent_searches_when_disease_and_information_request(monkeypatch):
    chunks = [
        DocumentChunk(
            content="HbA1c가 감소했습니다.",
            metadata={
                "pmid": "111",
                "title": "Paper A",
                "url": "https://pubmed.ncbi.nlm.nih.gov/111/",
            },
        ),
        DocumentChunk(
            content="공복혈당도 개선됐습니다.",
            metadata={
                "pmid": "222",
                "title": "Paper B",
                "url": "https://pubmed.ncbi.nlm.nih.gov/222/",
            },
        ),
    ]
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("당뇨", True))
    monkeypatch.setattr(paper_agent_module, "search_papers", _fake_search_papers(chunks))
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeAnswerLLM("HbA1c가 감소했습니다."))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨병 논문 알려줘"})

    assert response.status_code == 200
    body = response.json()
    assert "HbA1c" in body["answer"]
    assert body["sources"] == [
        {"name": "Paper A", "url": "https://pubmed.ncbi.nlm.nih.gov/111/"},
        {"name": "Paper B", "url": "https://pubmed.ncbi.nlm.nih.gov/222/"},
    ]


async def test_paper_agent_deduplicates_sources_by_pmid_when_chunks_split_same_paper(monkeypatch):
    chunks = [
        DocumentChunk(content="앞부분", metadata={"pmid": "111", "title": "Paper A", "url": "https://x/111/"}),
        DocumentChunk(content="뒷부분", metadata={"pmid": "111", "title": "Paper A", "url": "https://x/111/"}),
    ]
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("당뇨", True))
    monkeypatch.setattr(paper_agent_module, "search_papers", _fake_search_papers(chunks))
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeAnswerLLM("답변"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨병 논문 알려줘"})

    assert response.status_code == 200
    assert len(response.json()["sources"]) == 1


async def test_paper_agent_returns_not_found_message_when_no_chunks_found(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("당뇨", True))
    monkeypatch.setattr(paper_agent_module, "search_papers", _fake_search_papers([]))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨병 논문 알려줘"})

    assert response.status_code == 200
    body = response.json()
    assert "찾지 못했습니다" in body["answer"]
    assert body["sources"] == []


async def test_paper_agent_refuses_when_disease_mentioned_but_not_information_request(monkeypatch):
    """관용구 케이스: 질환 단어는 감지돼도(예: "심장") 정보 요청이 아니면 검색을 안 한다."""
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("심장질환", False))
    monkeypatch.setattr(paper_agent_module, "_build_llm", lambda: FakeAnswerLLM("도움이 필요하시면 말씀해 주세요."))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "나 심장이 너무 쫄려..."})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "도움이 필요하시면 말씀해 주세요."
    assert body["sources"] == []


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


async def test_paper_agent_returns_503_when_embedding_unavailable(monkeypatch):
    def _raise():
        raise EmbeddingUnavailableError("OPENAI_EMBEDDING_API_KEY가 설정되지 않았습니다.")

    monkeypatch.setattr(paper_agent_router_module, "ensure_paper_db", _raise)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/agent/paper-search", json={"question": "당뇨 논문 알려줘"})

    assert response.status_code == 503


async def test_paper_agent_returns_503_when_embedding_mismatch(monkeypatch):
    def _raise(db):
        raise EmbeddingMismatchError("임베딩 모델이 일치하지 않습니다.")

    monkeypatch.setattr(paper_agent_router_module, "assert_embedding_compatible", _raise)

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


def test_build_sources_deduplicates_by_pmid_preserving_first_occurrence_order():
    chunks = [
        DocumentChunk(content="a", metadata={"pmid": "2", "title": "B", "url": "u2"}),
        DocumentChunk(content="b", metadata={"pmid": "1", "title": "A", "url": "u1"}),
        DocumentChunk(content="c", metadata={"pmid": "2", "title": "B", "url": "u2"}),
    ]

    sources = paper_agent_module._build_sources(chunks)

    assert [s.name for s in sources] == ["B", "A"]


def test_format_search_context_numbers_chunks_with_pmid():
    chunks = [
        DocumentChunk(content="내용1", metadata={"pmid": "1", "title": "T1"}),
        DocumentChunk(content="내용2", metadata={"pmid": "2", "title": "T2"}),
    ]

    context = paper_agent_module._format_search_context(chunks)

    assert "[1] PMID 1: T1" in context
    assert "[2] PMID 2: T2" in context
