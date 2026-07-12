"""서버 기동 없이 retrieve_service의 순수 로직(threshold 필터, 성분명 캐싱)을 검증한다."""

from langchain_core.documents import Document

from ai_worker.services import retrieve_service


class FakeChromaDb:
    def __init__(self, docs_with_scores: list[tuple[Document, float]]) -> None:
        self._docs_with_scores = docs_with_scores

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        if filter is None:
            return self._docs_with_scores[:k]
        return [
            (doc, score)
            for doc, score in self._docs_with_scores
            if doc.metadata.get("ingr_name") == filter.get("ingr_name")
        ][:k]


class _FakeCollection:
    def __init__(self, metadatas: list[dict]) -> None:
        self._metadatas = metadatas

    def get(self, include: list[str]):
        return {"metadatas": self._metadatas}


def test_cache_ingr_names_extracts_unique_names():
    db = FakeChromaDb([])
    db._collection = _FakeCollection(
        [
            {"ingr_name": "졸피뎀타르타르산염"},
            {"ingr_name": " 졸피뎀타르타르산염 "},
            {"ingr_name": "무관성분"},
            {},
        ]
    )

    retrieve_service.cache_ingr_names(db)

    assert retrieve_service.db_holder["ingr_names"] == {"졸피뎀타르타르산염", "무관성분"}


def test_search_documents_filters_by_similarity_threshold(monkeypatch):
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 1.0)
    relevant_doc = Document(page_content="관련 문서", metadata={"ingr_name": "졸피뎀타르타르산염"})
    irrelevant_doc = Document(page_content="무관 문서", metadata={"ingr_name": "무관성분"})
    db = FakeChromaDb([(relevant_doc, 0.5), (irrelevant_doc, 2.0)])
    retrieve_service.db_holder["ingr_names"] = {"졸피뎀타르타르산염", "무관성분"}

    chunks = retrieve_service.search_documents(db, "졸피뎀 관련 질문", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == relevant_doc.page_content


def test_search_documents_applies_dynamic_ingredient_filter(monkeypatch):
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    matching_doc = Document(page_content="졸피뎀 문서", metadata={"ingr_name": "졸피뎀타르타르산염"})
    other_doc = Document(page_content="다른 성분 문서", metadata={"ingr_name": "무관성분"})
    db = FakeChromaDb([(matching_doc, 0.1), (other_doc, 0.1)])
    retrieve_service.db_holder["ingr_names"] = {"졸피뎀타르타르산염", "무관성분"}

    chunks = retrieve_service.search_documents(db, "졸피뎀타르타르산염 최대 투여기간", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == matching_doc.page_content
