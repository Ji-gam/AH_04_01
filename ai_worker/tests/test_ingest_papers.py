"""PubMed 수집 + 한국어 요약 회귀 테스트.

청킹/임베딩/색인은 이 모듈 소관이 아니다 — `source/_manifest.yaml`에 선언된 논문 JSON을
매니페스트 파이프라인이 처리한다(`ai_worker/ingest/`). 여기 남은 건 LangChain 밖 영역인
PubMed API 수집과 LLM 요약 생성뿐이다. 예전엔 이 파일에 전용 색인 코드가 따로 있었고,
그게 매니페스트 경로와 양쪽에서 같은 컬렉션에 써서 논문이 두 번 들어갔다(740편 -> 1,480건).
"""

import json

import httpx

from ai_worker.tasks import ingest_papers as ingest_papers_module
from ai_worker.tasks.ingest_papers import fetch_and_append_category_papers


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


async def test_fetch_and_append_category_papers_writes_new_papers(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    handler = _pubmed_handler(["11111111"], _EFETCH_XML_ONE_ARTICLE)
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    report = await fetch_and_append_category_papers(retmax_per_category=5, categories=["LIFESTYLE"])

    saved = json.loads((tmp_path / "당뇨.json").read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["pmid"] == "11111111"
    assert saved[0]["category"] == "LIFESTYLE"
    assert report["당뇨"]["LIFESTYLE"] == 1


async def test_fetch_and_append_category_papers_skips_articles_without_abstract(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["암"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    handler = _pubmed_handler(["22222222", "33333333"], _EFETCH_XML_NO_ABSTRACT_THEN_ONE)
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    await fetch_and_append_category_papers(retmax_per_category=5, categories=["FOOD"])

    saved = json.loads((tmp_path / "암.json").read_text(encoding="utf-8"))
    assert len(saved) == 1
    assert saved[0]["pmid"] == "33333333"


async def test_fetch_and_append_category_papers_dedupes_existing_pmids(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(
        json.dumps([{"pmid": "11111111", "title": "old", "abstract": "old", "category": "LIFESTYLE"}]),
        encoding="utf-8",
    )
    handler = _pubmed_handler(["11111111"], _EFETCH_XML_ONE_ARTICLE)
    monkeypatch.setattr(httpx, "AsyncClient", _mock_transport(handler))

    report = await fetch_and_append_category_papers(retmax_per_category=5, categories=["LIFESTYLE"])

    saved = json.loads((tmp_path / "당뇨.json").read_text(encoding="utf-8"))
    assert len(saved) == 1  # 중복 PMID라 추가되지 않음
    assert report["당뇨"]["LIFESTYLE"] == 0


async def test_ensure_paper_summaries_skips_papers_that_already_have_one(tmp_path, monkeypatch):
    """이미 요약된 논문은 다시 LLM에 태우지 않는다 — 리셋 후 전체 재색인을 해도 재과금 없음.

    곁다리 캐시 파일이 아니라 원본 JSON의 `summary_ko` 필드가 그 판단 근거다. 요약을 원본에
    합쳐두면 색인이 그 파일을 읽어 붙이는 "요리"를 할 필요가 없다."""
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(
        json.dumps(
            [
                {"pmid": "1", "title": "a", "abstract": "b", "summary_ko": "이미 있는 요약"},
                {"pmid": "2", "title": "c", "abstract": "d"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ingest_papers_module.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ingest_papers_module, "ChatOpenAI", lambda **kwargs: object())
    summarized: list[str] = []

    async def _fake_summarize(llm, paper):
        summarized.append(paper["pmid"])
        paper["summary_ko"] = f"{paper['pmid']} 요약"
        return True

    monkeypatch.setattr(ingest_papers_module, "_summarize_one", _fake_summarize)

    created = await ingest_papers_module.ensure_paper_summaries()

    assert summarized == ["2"]  # 요약이 있는 "1"은 건너뜀
    assert created == 1
    saved = json.loads((tmp_path / "당뇨.json").read_text(encoding="utf-8"))
    assert [p["summary_ko"] for p in saved] == ["이미 있는 요약", "2 요약"]  # 원본에 기록됨


async def test_ensure_paper_summaries_does_nothing_without_api_key(tmp_path, monkeypatch):
    """키가 없으면 요약 없이 진행한다(요약은 한국어 매칭 향상이지 색인의 필수 조건이 아님)."""
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(json.dumps([{"pmid": "1", "title": "a", "abstract": "b"}]), encoding="utf-8")
    monkeypatch.setattr(ingest_papers_module.settings, "OPENAI_API_KEY", None)

    assert await ingest_papers_module.ensure_paper_summaries() == 0
