"""서버 기동 없이 paper_retrieve_service의 순수 로직(질환 필터 + 확장 + threshold)을 검증한다."""

from langchain_core.documents import Document

from ai_worker.services import paper_retrieve_service


class FakePaperChromaDb:
    """langchain-chroma의 공개 API(`similarity_search_with_score`)만 흉내낸다.
    필터/질의를 실제로 적용하진 않고, 호출 시 받은 인자를 기록해 검증에 쓴다."""

    def __init__(self, docs_with_scores: list[tuple[Document, float]]) -> None:
        self._docs_with_scores = docs_with_scores
        self.calls: list[dict] = []

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        self.calls.append({"query": query, "k": k, "filter": filter})
        return self._docs_with_scores[:k]


def test_search_papers_filters_by_similarity_threshold(monkeypatch):
    monkeypatch.setattr(paper_retrieve_service.settings, "PAPER_SIMILARITY_THRESHOLD", 1.0)
    relevant = Document(page_content="관련", metadata={"disease": "당뇨", "pmid": "1"})
    irrelevant = Document(page_content="무관", metadata={"disease": "당뇨", "pmid": "2"})
    db = FakePaperChromaDb([(relevant, 0.5), (irrelevant, 2.0)])

    chunks = paper_retrieve_service.search_papers(db, "당뇨에 좋은 음식은?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == relevant.page_content


def test_search_papers_returns_empty_when_no_match():
    db = FakePaperChromaDb([])

    chunks = paper_retrieve_service.search_papers(db, "당뇨 관리법", limit=3)

    assert chunks == []


def test_search_papers_applies_single_disease_filter_with_unmodified_query():
    db = FakePaperChromaDb([])

    paper_retrieve_service.search_papers(db, "혈당 관리 어떻게 해요?", limit=3)

    assert db.calls[0]["filter"] == {"disease": "당뇨"}
    assert db.calls[0]["query"] == "혈당 관리 어떻게 해요?"


def test_search_papers_maps_hypertension_to_cardio_and_cerebro():
    """고혈압은 5대 질환에 없지만 심혈관/뇌혈관 논문이 답이 된다. 필터가 없으면
    벡터 검색이 당뇨 논문을 1위로 올린다(2026-07-17 실측)."""
    db = FakePaperChromaDb([])

    paper_retrieve_service.search_papers(db, "고혈압에 좋은 운동은?", limit=3)

    assert db.calls[0]["filter"] == {"disease": {"$in": ["심장질환", "뇌혈관질환"]}}


def test_search_papers_falls_back_to_user_conditions_when_query_has_no_disease():
    db = FakePaperChromaDb([])

    paper_retrieve_service.search_papers(db, "운동 뭐가 좋아?", limit=3, conditions=["당뇨"])

    assert db.calls[0]["filter"] == {"disease": "당뇨"}


def test_search_papers_skips_search_when_no_disease_resolved():
    """질의에도 진단 이력에도 질환이 없으면 검색 자체를 생략한다 —
    5대 질환 논문만 있는 컬렉션에서 억지로 답을 꺼내면 무관한 논문이 인용된다."""
    db = FakePaperChromaDb([(Document(page_content="아무거나", metadata={"pmid": "1"}), 0.1)])

    chunks = paper_retrieve_service.search_papers(db, "좋은 아침이야", limit=3)

    assert chunks == []
    assert db.calls == []  # 검색 호출 자체가 없어야 한다


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
