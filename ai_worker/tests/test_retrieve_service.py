"""서버 기동 없이 retrieve_service의 순수 로직(threshold 필터, 이름 캐싱·매칭)을 검증한다."""

import pytest
from langchain_core.documents import Document

from ai_worker.services import retrieve_service
from ai_worker.services.drug_name_resolver import DrugNameIndex, build_index


@pytest.fixture(autouse=True)
def reset_name_caches():
    """db_holder는 모듈 전역 싱글톤이라 테스트가 서로 샌다. 매번 되돌린다."""
    original = dict(retrieve_service.db_holder)
    yield
    retrieve_service.db_holder.update(original)


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

    def _matches(self, doc: Document, filter: dict) -> bool:
        for key, want in filter.items():
            got = doc.metadata.get(key)
            # 약 이름은 브랜드 하나에 제품이 여럿이라 $in으로 넘어온다("타이레놀" -> 4제품).
            if isinstance(want, dict) and "$in" in want:
                if got not in want["$in"]:
                    return False
            elif got != want:
                return False
        return True

    def similarity_search_with_score(self, query: str, k: int, filter: dict | None = None):
        if filter is None:
            return self._docs_with_scores[:k]
        return [(doc, score) for doc, score in self._docs_with_scores if self._matches(doc, filter)][:k]

    def get(self, include: list[str]):
        return {"metadatas": self._metadatas}


def test_cache_searchable_names_collects_ingredients_and_drug_names():
    """성분명만 모으던 시절엔 "타이레놀 부작용" 같은 질문이 전부 0건이었다."""
    db = FakeChromaDb(
        [],
        metadatas=[
            {"ingr_name": "졸피뎀타르타르산염"},
            {"ingr_name": " 졸피뎀타르타르산염 "},
            {"ingr_name": "무관성분"},
            {"item_name": "타이레놀정500밀리그람(아세트아미노펜)"},
            {},
        ],
    )

    retrieve_service.cache_searchable_names(db)

    assert retrieve_service.db_holder["ingr_names"] == {"졸피뎀타르타르산염", "무관성분"}
    assert retrieve_service.db_holder["drug_names"].resolve("타이레놀 부작용") is not None


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


def test_search_documents_skips_search_when_no_drug_identified(monkeypatch):
    """T-LLM-7-3-2: DUR 문서는 전부 짧은 템플릿 문장이라, 약이 식별 안 된 일반 건강
    질문으로 필터 없이 전체 검색하면 무관한 성분이 임계값을 통과해버린다(실측:
    "당뇨병 진단받았는데 어떡하죠"가 항암제 임부금기 경고와 매칭됨). 성분명도 약 이름도
    식별 안 되면 검색 자체를 생략한다."""
    retrieve_service.db_holder["ingr_names"] = {"졸피뎀타르타르산염", "무관성분"}
    retrieve_service.db_holder["drug_names"] = build_index(["타이레놀정500밀리그람(아세트아미노펜)"])

    chunks = retrieve_service.search_documents(_RaisingChromaDb(), "당뇨병 진단받았는데 어떡하죠", limit=3)

    assert chunks == []


def test_search_documents_finds_drug_by_brand_name(monkeypatch):
    """**사람은 성분명으로 묻지 않는다.** "타이레놀 부작용"이라고 친다.

    성분명만 보던 시절엔 이런 질문이 전부 0건이었고, e약은요 4,758건이 색인만 되고 한 번도
    뽑히지 않았다. 조사("타이레놀은")가 붙어도 걸려야 한다 — 한국어 조사는 명사 뒤에 붙으므로
    부분 문자열 검사로 통과한다."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    tylenol = Document(
        page_content="타이레놀 부작용 설명", metadata={"item_name": "타이레놀정500밀리그람(아세트아미노펜)"}
    )
    other = Document(page_content="다른 약", metadata={"item_name": "게보린정"})
    db = FakeChromaDb([(tylenol, 0.1), (other, 0.1)])
    retrieve_service.db_holder["ingr_names"] = set()
    retrieve_service.db_holder["drug_names"] = build_index(["타이레놀정500밀리그람(아세트아미노펜)", "게보린정"])

    chunks = retrieve_service.search_documents(db, "타이레놀은 부작용이 뭐야?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == tylenol.page_content


def test_search_documents_prefers_ingredient_over_drug_name(monkeypatch):
    """성분명을 먼저 본다 — DUR 금기/주의 규칙이 성분 단위라 더 구체적인 답이기 때문."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    rule = Document(page_content="병용금기 규칙", metadata={"ingr_name": "와파린"})
    db = FakeChromaDb([(rule, 0.1)])
    retrieve_service.db_holder["ingr_names"] = {"와파린"}
    retrieve_service.db_holder["drug_names"] = build_index(["와파린정1밀리그람"])

    chunks = retrieve_service.search_documents(db, "와파린 같이 먹어도 돼?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == rule.page_content


def test_drug_name_index_is_empty_by_default():
    """색인 전이거나 캐싱이 실패해도 검색이 터지지 않고 그냥 0건이어야 한다."""
    assert DrugNameIndex().resolve("타이레놀 부작용") is None
