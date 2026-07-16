"""서버 기동 없이 retrieve_service의 순수 로직(threshold 필터, 성분명 캐싱)을 검증한다."""

from langchain_core.documents import Document

from ai_worker.services import retrieve_service


class FakeChromaDb:
    """langchain-chroma의 공개 API(`get`/`similarity_search_with_score`)만 흉내낸다.
    `_collection` 같은 사설 속성은 일부러 두지 않는다 — 프로덕션 코드가 사설 접근을
    시도하면 이 fake에서 AttributeError로 곧장 드러나야 한다."""

    def __init__(
        self,
        docs_with_scores: list[tuple[Document, float]],
        metadatas: list[dict] | None = None,
    ) -> None:
        self._docs_with_scores = docs_with_scores
        self._metadatas = metadatas or []

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        if filter is None:
            return self._docs_with_scores[:k]
        return [
            (doc, score)
            for doc, score in self._docs_with_scores
            if doc.metadata.get("ingr_name") == filter.get("ingr_name")
        ][:k]

    def get(self, include: list[str]):
        return {"metadatas": self._metadatas}


def test_cache_ingr_names_extracts_unique_names():
    db = FakeChromaDb(
        [],
        metadatas=[
            {"ingr_name": "졸피뎀타르타르산염"},
            {"ingr_name": " 졸피뎀타르타르산염 "},
            {"ingr_name": "무관성분"},
            {},
        ],
    )

    retrieve_service.cache_ingr_names(db)

    assert retrieve_service.db_holder["ingr_names"] == {"졸피뎀타르타르산염", "무관성분"}


def test_search_documents_filters_by_similarity_threshold(monkeypatch):
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 1.0)
    relevant_doc = Document(page_content="관련 문서", metadata={"ingr_name": "졸피뎀타르타르산염"})
    irrelevant_doc = Document(page_content="무관 문서", metadata={"ingr_name": "무관성분"})
    db = FakeChromaDb([(relevant_doc, 0.5), (irrelevant_doc, 2.0)])
    retrieve_service.db_holder["ingr_names"] = {"졸피뎀타르타르산염", "무관성분"}

    # 쿼리에 성분명 전체가 그대로 들어있어야 동적 필터가 걸린다(아래 없으면 검색 자체가
    # 생략된다 — test_search_documents_skips_search_when_no_ingredient_identified 참고).
    chunks = retrieve_service.search_documents(db, "졸피뎀타르타르산염 관련 질문", limit=3)

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


class _RaisingChromaDb:
    """호출되면 즉시 실패하는 가짜 — search_documents가 성분명 미식별 시 Chroma를
    아예 안 건드리는지(검색 생략) 엄격하게 검증한다."""

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        raise AssertionError("성분명이 식별 안 됐는데 Chroma 검색이 호출됐다")


def test_search_documents_skips_search_when_no_ingredient_identified(monkeypatch):
    """T-LLM-7-3-2: DUR 문서는 전부 짧은 템플릿 문장이라, 성분명이 식별 안 된 일반
    건강 질문으로 필터 없이 전체 검색하면 무관한 성분이 임계값을 통과해버린다(실측:
    "당뇨병 진단받았는데 어떡하죠"가 항암제 임부금기 경고와 매칭됨). 성분명이 아예
    식별 안 되면 검색 자체를 생략한다."""
    retrieve_service.db_holder["ingr_names"] = {"졸피뎀타르타르산염", "무관성분"}

    chunks = retrieve_service.search_documents(_RaisingChromaDb(), "당뇨병 진단받았는데 어떡하죠", limit=3)

    assert chunks == []
