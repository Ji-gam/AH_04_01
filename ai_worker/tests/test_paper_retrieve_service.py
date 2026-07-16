"""서버 기동 없이 paper_retrieve_service의 순수 로직(threshold)을 검증한다.
T-LLM-7-3-2: 질환 사전 분류/필터를 제거하고 전체 컬렉션을 검색하도록 바뀌었다."""

from langchain_core.documents import Document

from ai_worker.services import paper_retrieve_service


class FakePaperChromaDb:
    """langchain-chroma의 공개 API(`similarity_search_with_score`)만 흉내낸다."""

    def __init__(self, docs_with_scores: list[tuple[Document, float]]) -> None:
        self._docs_with_scores = docs_with_scores

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        return self._docs_with_scores[:k]


def test_search_papers_filters_by_similarity_threshold(monkeypatch):
    monkeypatch.setattr(paper_retrieve_service.settings, "PAPER_SIMILARITY_THRESHOLD", 1.0)
    relevant = Document(page_content="관련", metadata={"disease": "당뇨", "pmid": "1"})
    irrelevant = Document(page_content="무관", metadata={"disease": "당뇨", "pmid": "2"})
    db = FakePaperChromaDb([(relevant, 0.5), (irrelevant, 2.0)])

    chunks = paper_retrieve_service.search_papers(db, "질문", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == relevant.page_content


def test_search_papers_returns_empty_when_no_match():
    db = FakePaperChromaDb([])

    chunks = paper_retrieve_service.search_papers(db, "질문", limit=3)

    assert chunks == []


def test_ensure_paper_db_lazily_builds_and_caches(monkeypatch):
    sentinel = object()
    calls: list[str] = []

    def _fake_build():
        calls.append("build")
        return sentinel

    monkeypatch.setattr(paper_retrieve_service, "build_paper_vector_store", _fake_build)
    original_db = paper_retrieve_service.paper_db_holder["db"]
    paper_retrieve_service.paper_db_holder["db"] = None
    try:
        db1 = paper_retrieve_service.ensure_paper_db()
        db2 = paper_retrieve_service.ensure_paper_db()

        assert db1 is sentinel
        assert db2 is sentinel
        assert calls == ["build"]  # 두 번째 호출은 캐시된 값 재사용, build 재호출 없음
    finally:
        paper_retrieve_service.paper_db_holder["db"] = original_db
