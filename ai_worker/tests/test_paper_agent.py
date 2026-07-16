"""
T-LLM-7/7-1/7-2/7-3: 질환 논문 검색 파이프라인 회귀 테스트.

주의(중요) — 이 테스트들은 "판단력 시험"의 회귀 방지용일 뿐이다. LLM 호출과 PubMed
호출을 모킹하므로 우리가 짠 시나리오만 검증하며, 실제 LLM이 무관한 질문에 도구를
정말 호출하지 않는지, PubMed가 실제로 유의미한 결과를 주는지는 이 테스트로 보장되지
않는다. 진짜 동작은 `OPENAI_API_KEY`를 채운 상태로 최소 1회 수동 실행해서 눈으로
확인해야 한다.
"""

from collections.abc import Iterator

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from ai_worker.main import app
from ai_worker.tasks import paper_agent as paper_agent_module
from ai_worker.tasks.paper_agent import QueryClassification
from ai_worker.tools.paper_search import PaperSearchUnavailableError, search_disease_paper


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    original_api_key = paper_agent_module.settings.OPENAI_API_KEY
    yield
    paper_agent_module.settings.OPENAI_API_KEY = original_api_key


def _mock_transport(handler):
    """httpx.AsyncClient(timeout=...)처럼 kwargs가 붙는 생성 호출도 그대로 통과시키면서
    transport만 가짜로 바꿔치기한다."""
    real_async_client = httpx.AsyncClient

    def _patched_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    return _patched_client


_EFETCH_XML_ONE_ARTICLE = """<?xml version="1.0"?>
<PubmedArticleSet>
<PubmedArticle>
<MedlineCitation>
<PMID>11111111</PMID>
<Article>
<ArticleTitle>Continuous Glucose Monitoring and HbA1c Reduction</ArticleTitle>
<Abstract><AbstractText>HbA1c was significantly reduced in the intervention group.</AbstractText></Abstract>
</Article>
</MedlineCitation>
</PubmedArticle>
</PubmedArticleSet>
"""

_EFETCH_XML_NO_ABSTRACT_THEN_ONE = """<?xml version="1.0"?>
<PubmedArticleSet>
<PubmedArticle>
<MedlineCitation>
<PMID>22222222</PMID>
<Article><ArticleTitle>No Abstract Article</ArticleTitle></Article>
</MedlineCitation>
</PubmedArticle>
<PubmedArticle>
<MedlineCitation>
<PMID>33333333</PMID>
<Article>
<ArticleTitle>Second Article With Abstract</ArticleTitle>
<Abstract><AbstractText>This one has an abstract.</AbstractText></Abstract>
</Article>
</MedlineCitation>
</PubmedArticle>
</PubmedArticleSet>
"""


def _pubmed_handler(esearch_ids: list[str], efetch_xml: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if "esearch.fcgi" in str(request.url):
            return httpx.Response(200, json={"esearchresult": {"idlist": esearch_ids}})
        if "efetch.fcgi" in str(request.url):
            return httpx.Response(200, text=efetch_xml)
        raise AssertionError(f"예상치 못한 요청: {request.url}")

    return handler


async def test_search_disease_paper_returns_parsed_result_for_supported_disease(monkeypatch):
    handler = _pubmed_handler(["11111111"], _EFETCH_XML_ONE_ARTICLE)
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    result = await search_disease_paper.ainvoke({"disease": "당뇨"})

    assert "Continuous Glucose Monitoring" in result
    assert "HbA1c was significantly reduced" in result
    assert "PMID: 11111111" in result
    assert "https://pubmed.ncbi.nlm.nih.gov/11111111/" in result


async def test_search_disease_paper_skips_articles_without_abstract(monkeypatch):
    handler = _pubmed_handler(["22222222", "33333333"], _EFETCH_XML_NO_ABSTRACT_THEN_ONE)
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    result = await search_disease_paper.ainvoke({"disease": "암"})

    assert "Second Article With Abstract" in result
    assert "PMID: 33333333" in result
    assert "No Abstract Article" not in result


async def test_search_disease_paper_returns_not_found_when_no_results(monkeypatch):
    handler = _pubmed_handler([], "")
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    result = await search_disease_paper.ainvoke({"disease": "간질환"})

    assert "찾지 못했습니다" in result


async def test_search_disease_paper_raises_on_esearch_non_200_status(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    with pytest.raises(PaperSearchUnavailableError):
        await search_disease_paper.ainvoke({"disease": "당뇨"})


async def test_search_disease_paper_raises_on_network_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    with pytest.raises(PaperSearchUnavailableError):
        await search_disease_paper.ainvoke({"disease": "당뇨"})


async def test_search_disease_paper_raises_on_malformed_efetch_xml(monkeypatch):
    handler = _pubmed_handler(["11111111"], "not valid xml <<<")
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    with pytest.raises(PaperSearchUnavailableError):
        await search_disease_paper.ainvoke({"disease": "당뇨"})


async def test_search_disease_paper_reports_unsupported_disease():
    result = await search_disease_paper.ainvoke({"disease": "감기"})

    assert "찾지 못했습니다" in result


@pytest.mark.parametrize("malicious", ["../../etc/passwd", "당뇨/../../secret", "..", "/etc/hosts", "해킹"])
async def test_search_disease_paper_rejects_unsupported_disease_without_http_call(malicious, monkeypatch):
    """화이트리스트 밖 disease는 PubMed에 질의하지 않고 즉시 거부한다."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("화이트리스트 밖 disease인데 HTTP 호출이 발생했다")

    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    result = await search_disease_paper.ainvoke({"disease": malicious})

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


class _FakeSearchTool:
    """search_disease_paper 도구 자체를 대신하는 가짜 — PubMed 연동은 별도로
    검증하므로, ask_paper_agent의 분류/답변 로직 테스트에서는 네트워크를 타지
    않도록 이 페이크로 치환한다."""

    def __init__(self, result: str | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def ainvoke(self, args: dict) -> str:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


async def test_paper_agent_searches_when_disease_and_information_request(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("당뇨", True))
    monkeypatch.setattr(paper_agent_module, "search_disease_paper", _FakeSearchTool(result="제목: X\n초록: Y"))
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


async def test_paper_agent_returns_503_when_pubmed_unavailable(monkeypatch):
    monkeypatch.setattr(paper_agent_module.settings, "OPENAI_API_KEY", "fake-key")
    monkeypatch.setattr(paper_agent_module, "classify_query", _fake_classify("당뇨", True))
    monkeypatch.setattr(
        paper_agent_module,
        "search_disease_paper",
        _FakeSearchTool(error=PaperSearchUnavailableError("PubMed 요청 중 네트워크 오류가 발생했습니다.")),
    )

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
