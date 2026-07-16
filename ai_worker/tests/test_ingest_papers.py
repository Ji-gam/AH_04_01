"""
T-LLM-7-3(개정): PubMed 논문 인제스천(수집+청킹+임베딩+색인) 회귀 테스트.

PubMed 호출을 흉내내는 부분(예전 test_paper_agent.py의 mock transport 패턴)은
이제 "질문 시점 1건 조회"가 아니라 "배치 대량 수집"을 검증한다.
"""

import json

import httpx

from ai_worker.tasks import ingest_papers as ingest_papers_module
from ai_worker.tasks.ingest_papers import build_documents, fetch_and_append_category_papers, load_raw_papers


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


def test_build_documents_keeps_short_abstract_as_single_document():
    papers = [{"pmid": "1", "title": "T", "abstract": "짧은 초록.", "category": "FOOD"}]

    docs = build_documents("당뇨", papers)

    assert len(docs) == 1
    assert docs[0].page_content == "T\n\n짧은 초록."
    assert docs[0].metadata == {
        "disease": "당뇨",
        "pmid": "1",
        "title": "T",
        "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
        "source": "PubMed",
        "category": "FOOD",
    }


def test_build_documents_splits_long_abstract_and_shares_metadata():
    long_abstract = "문장입니다. " * 300  # 1000자 훌쩍 넘김
    papers = [{"pmid": "2", "title": "Long", "abstract": long_abstract, "category": "LIFESTYLE"}]

    docs = build_documents("암", papers)

    assert len(docs) > 1
    assert all(d.metadata["pmid"] == "2" for d in docs)
    assert all(d.metadata["disease"] == "암" for d in docs)


def test_build_documents_skips_papers_missing_pmid_or_abstract():
    papers = [{"pmid": None, "title": "무효", "abstract": "내용"}, {"pmid": "3", "title": "유효"}]

    docs = build_documents("간질환", papers)

    assert docs == []


def test_load_raw_papers_skips_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨", "암"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(json.dumps([{"pmid": "1", "title": "t", "abstract": "a"}]), encoding="utf-8")

    result = load_raw_papers()

    assert list(result.keys()) == ["당뇨"]


def test_load_raw_papers_skips_empty_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text("[]", encoding="utf-8")

    assert load_raw_papers() == {}


class _FakePaperDb:
    """langchain-chroma의 공개 API(`get`/`add_documents`)만 흉내낸다."""

    def __init__(self, metadatas: list[dict]) -> None:
        self._metadatas = metadatas
        self.added_batches: list[list] = []
        self.deleted = False

    def get(self, include: list[str]):
        return {"metadatas": self._metadatas}

    def add_documents(self, docs):
        self.added_batches.append(docs)

    def delete_collection(self):
        self.deleted = True


def test_indexed_pmids_extracts_unique_pmids_from_metadata():
    fake_db = _FakePaperDb(metadatas=[{"pmid": "1"}, {"pmid": "1"}, {"pmid": "2"}, {}])

    assert ingest_papers_module._indexed_pmids(fake_db) == {"1", "2"}


def test_ingest_papers_skips_already_indexed_pmids_and_adds_only_new(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(
        json.dumps(
            [
                {"pmid": "1", "title": "이미 색인됨", "abstract": "내용1", "category": "FOOD"},
                {"pmid": "2", "title": "신규", "abstract": "내용2", "category": "FOOD"},
            ]
        ),
        encoding="utf-8",
    )
    fake_db = _FakePaperDb(metadatas=[{"pmid": "1"}])
    monkeypatch.setattr(ingest_papers_module, "build_paper_vector_store", lambda: fake_db)

    result = ingest_papers_module.ingest_papers()

    assert result is fake_db
    assert len(fake_db.added_batches) == 1
    added_pmids = {d.metadata["pmid"] for d in fake_db.added_batches[0]}
    assert added_pmids == {"2"}


def test_ingest_papers_adds_nothing_when_all_already_indexed(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_papers_module, "SUPPORTED_DISEASES", ["당뇨"])
    monkeypatch.setattr(ingest_papers_module, "RAW_DATA_DIR", tmp_path)
    (tmp_path / "당뇨.json").write_text(
        json.dumps([{"pmid": "1", "title": "이미 색인됨", "abstract": "내용1", "category": "FOOD"}]),
        encoding="utf-8",
    )
    fake_db = _FakePaperDb(metadatas=[{"pmid": "1"}])
    monkeypatch.setattr(ingest_papers_module, "build_paper_vector_store", lambda: fake_db)

    result = ingest_papers_module.ingest_papers()

    assert result is fake_db
    assert fake_db.added_batches == []


def test_reset_paper_collection_calls_delete_collection(monkeypatch):
    fake_db = _FakePaperDb(metadatas=[])
    monkeypatch.setattr(ingest_papers_module, "build_paper_vector_store", lambda: fake_db)

    ingest_papers_module.reset_paper_collection()

    assert fake_db.deleted is True


async def test_run_daily_pipeline_calls_fetch_then_ingest_in_order(monkeypatch):
    calls: list[str] = []

    async def _fake_fetch(retmax_per_category, categories):
        calls.append("fetch")

    def _fake_ingest():
        calls.append("ingest")
        return "db-sentinel"

    monkeypatch.setattr(ingest_papers_module, "fetch_and_append_category_papers", _fake_fetch)
    monkeypatch.setattr(ingest_papers_module, "ingest_papers", _fake_ingest)

    result = await ingest_papers_module.run_daily_pipeline()

    assert calls == ["fetch", "ingest"]
    assert result == "db-sentinel"
