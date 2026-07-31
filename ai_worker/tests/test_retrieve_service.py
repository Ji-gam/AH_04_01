"""서버 기동 없이 retrieve_service의 순수 로직(threshold 필터, 이름 캐싱·매칭)을 검증한다."""

import pytest
from langchain_core.documents import Document

from ai_worker.services import retrieve_service
from ai_worker.services.drug_name_resolver import DrugNameIndex, build_index, build_ingredient_index


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
        self.received_queries: list[tuple[str, dict | None]] = []

    def _matches(self, doc: Document, filter: dict) -> bool:
        if "$or" in filter:
            return any(self._matches(doc, clause) for clause in filter["$or"])
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
        self.received_queries.append((query, filter))
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

    assert retrieve_service.db_holder["ingr_names"].resolve("졸피뎀타르타르산염 관련 질문") is not None
    assert retrieve_service.db_holder["drug_names"].resolve("타이레놀 부작용") is not None


def test_cache_searchable_names_merges_extra_item_names_from_bridge():
    """T-LLM-2-rag-brand-name-bridge: "인데놀"은 e약은요 문서가 없어 Chroma 메타데이터에
    안 잡히지만, 전체 허가목록 기준 브릿지(_item_ingredient_map.csv)의 제품명 사전엔 있다.
    그 사전을 extra_item_names로 넘기면, 문서가 하나도 없는 브랜드도 "아는 약 이름"으로
    인식돼야 한다 — 이게 안 되면 브릿지까지 도달하기 전에 _build_filters가 검색을 생략한다."""
    db = FakeChromaDb([], metadatas=[])  # 인데놀 e약은요 문서 없음(실제 상황과 동일)

    retrieve_service.cache_searchable_names(db, extra_item_names=["인데놀정10mg(프로프라놀롤염산염)"])

    assert retrieve_service.db_holder["drug_names"].resolve("인데놀 노인이 먹어도 돼?") is not None


def test_search_documents_filters_by_similarity_threshold(monkeypatch):
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 1.0)
    relevant_doc = Document(page_content="관련 문서", metadata={"ingr_name": "졸피뎀타르타르산염"})
    irrelevant_doc = Document(page_content="무관 문서", metadata={"ingr_name": "무관성분"})
    db = FakeChromaDb([(relevant_doc, 0.5), (irrelevant_doc, 2.0)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["졸피뎀타르타르산염", "무관성분"])

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
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["졸피뎀타르타르산염", "무관성분"])

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
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["졸피뎀타르타르산염", "무관성분"])
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
    retrieve_service.db_holder["ingr_names"] = DrugNameIndex()
    retrieve_service.db_holder["drug_names"] = build_index(["타이레놀정500밀리그람(아세트아미노펜)", "게보린정"])

    chunks = retrieve_service.search_documents(db, "타이레놀은 부작용이 뭐야?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == tylenol.page_content


def test_search_documents_prefers_ingredient_over_drug_name(monkeypatch):
    """성분명을 먼저 본다 — DUR 금기/주의 규칙이 성분 단위라 더 구체적인 답이기 때문."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    rule = Document(page_content="병용금기 규칙", metadata={"ingr_name": "와파린"})
    db = FakeChromaDb([(rule, 0.1)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["와파린"])
    retrieve_service.db_holder["drug_names"] = build_index(["와파린정1밀리그람"])

    chunks = retrieve_service.search_documents(db, "와파린 같이 먹어도 돼?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == rule.page_content


def test_search_documents_finds_ingredient_by_partial_name(monkeypatch):
    """저장된 성분명은 화학명 전체("졸피뎀타르타르산염")인데 사용자는 "졸피뎀"까지만 친다.

    예전엔 양방향 완전 포함 검사라 "졸피뎀 노인이 먹어도 돼?"가 0건이었다 — 질의 전체
    문자열이 성분명에 안 들어있고, 성분명 전체도 질의에 안 들어있기 때문. 접두사 인덱스로
    바뀐 뒤에는 "졸피뎀"이 3자 이상 접두사라 걸린다."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    rule = Document(page_content="졸피뎀 병용금기 규칙", metadata={"ingr_name": "졸피뎀타르타르산염"})
    other = Document(page_content="다른 성분 규칙", metadata={"ingr_name": "와파린"})
    db = FakeChromaDb([(rule, 0.1), (other, 0.1)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["졸피뎀타르타르산염", "와파린"])
    retrieve_service.db_holder["drug_names"] = DrugNameIndex()

    chunks = retrieve_service.search_documents(db, "졸피뎀 노인이 먹어도 돼?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == rule.page_content


def test_search_documents_finds_dur_rule_by_product_name(monkeypatch):
    """ "타이레놀 같이 먹어도 돼?"는 제품명 질의지만 DUR 병용금기는 성분(아세트아미노펜)
    단위로 키가 걸려 있다. product_ingredients 브릿지가 제품명 매칭에서 성분명을 찾아
    $or로 함께 걸어야, item_name만 있는 e약은요 문서뿐 아니라 ingr_name만 있는 DUR
    문서까지 같이 뽑힌다.

    ingr_names를 실제 DUR 문서(아세트아미노펜 규칙)로 채워두는 이유: 프로덕션에서는
    cache_searchable_names가 같은 문서 스캔에서 ingr_names와 drug_names를 함께 채우므로
    "그 성분의 DUR 문서가 Chroma에 있는데 ingr_names엔 없다"는 조합은 실제로 없다
    (_build_filters가 브릿지 성분명을 ingr_names로 정규화하기 때문)."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    dur_rule = Document(page_content="아세트아미노펜 병용금기 규칙", metadata={"ingr_name": "아세트아미노펜"})
    summary = Document(
        page_content="타이레놀 e약은요 요약", metadata={"item_name": "타이레놀정500밀리그람(아세트아미노펜)"}
    )
    other = Document(page_content="무관 성분 규칙", metadata={"ingr_name": "와파린"})
    db = FakeChromaDb([(dur_rule, 0.1), (summary, 0.1), (other, 0.1)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["아세트아미노펜", "와파린"])
    retrieve_service.db_holder["drug_names"] = build_index(["타이레놀정500밀리그람(아세트아미노펜)"])
    retrieve_service.db_holder["product_ingredients"] = {"타이레놀정500밀리그람(아세트아미노펜)": ("아세트아미노펜",)}

    chunks = retrieve_service.search_documents(db, "타이레놀 같이 먹어도 돼?", limit=3)

    contents = {chunk.content for chunk in chunks}
    assert contents == {dur_rule.page_content, summary.page_content}


def test_search_documents_normalizes_salt_form_bridge_ingredient(monkeypatch):
    """T-LLM-2-rag-brand-name-bridge 실측 버그: 전체 허가목록 기준으로 넓힌 브릿지는
    item_ingredient_map 원문을 그대로 준다 — "인데놀" -> "프로프라놀롤염산염"(염 형태).
    그런데 DUR 문서엔 염을 뗀 원형 "프로프라놀롤"로만 저장돼 있다. 브릿지 원문을 그대로
    필터에 쓰면 정확매치가 항상 0건이 된다 — ingr_names로 한 번 더 정규화해야 실제
    문서의 표기를 찾는다."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    dur_rule = Document(page_content="프로프라놀롤 노인주의 규칙", metadata={"ingr_name": "프로프라놀롤"})
    db = FakeChromaDb([(dur_rule, 0.1)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["프로프라놀롤"])
    retrieve_service.db_holder["drug_names"] = build_index(["인데놀정10mg(프로프라놀롤염산염)"])
    # MySQL item_ingredient_map 원문 그대로 — 염 형태, DUR 문서 표기와 다름.
    retrieve_service.db_holder["product_ingredients"] = {"인데놀정10mg(프로프라놀롤염산염)": ("프로프라놀롤염산염",)}

    chunks = retrieve_service.search_documents(db, "인데놀 노인이 먹어도 돼?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == dur_rule.page_content


def test_search_documents_augments_bridge_search_text_with_resolved_ingredient(monkeypatch):
    """DUR 문서는 브랜드명("인데놀")을 절대 안 쓰고 성분명("프로프라놀롤")만 쓴다. 성분
    브릿지 필터로 검색할 때 원본 질의 그대로 비교하면 임베딩 유사도가 나쁘게 나와 임계값에
    걸려 탈락한다(실측: 0.42, 임계값 0.35 미달) — 기존 브랜드 "타이레놀"도 e약은요 문서가
    함께 걸려 가려졌을 뿐 같은 문제였다. 성분 브릿지 필터에 한해서만 검색 문구에 정규화된
    성분명을 덧붙여야 한다(item_name 필터는 원본 질의 그대로 둬야 한다 — e약은요 문서는
    본문에 브랜드명을 그대로 쓴다)."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    dur_rule = Document(page_content="프로프라놀롤 노인주의 규칙", metadata={"ingr_name": "프로프라놀롤"})
    db = FakeChromaDb([(dur_rule, 0.1)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["프로프라놀롤"])
    retrieve_service.db_holder["drug_names"] = build_index(["인데놀정10mg(프로프라놀롤염산염)"])
    retrieve_service.db_holder["product_ingredients"] = {"인데놀정10mg(프로프라놀롤염산염)": ("프로프라놀롤염산염",)}

    retrieve_service.search_documents(db, "인데놀 노인이 먹어도 돼?", limit=3)

    queries_by_filter_key = {tuple(sorted((f or {}).keys())): q for q, f in db.received_queries}
    assert queries_by_filter_key[("item_name",)] == "인데놀 노인이 먹어도 돼?"
    ingr_name_query = queries_by_filter_key[("$or",)]
    assert "프로프라놀롤" in ingr_name_query
    assert "인데놀 노인이 먹어도 돼?" in ingr_name_query


def test_search_documents_skips_bridge_ingredient_without_dur_document(monkeypatch):
    """브릿지 성분명이 ingr_names에서 정규화되지 않으면(그 성분에 대한 DUR 문서가 애초에
    없음) 조용히 건너뛰고 item_name 필터만 남는다 — 존재하지 않는 표기로 필터를 걸어 헛김을
    보내지 않는다."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    summary = Document(page_content="게보린 e약은요 요약", metadata={"item_name": "게보린정"})
    db = FakeChromaDb([(summary, 0.1)])
    retrieve_service.db_holder["ingr_names"] = DrugNameIndex()  # 이 성분에 대한 DUR 문서 없음
    retrieve_service.db_holder["drug_names"] = build_index(["게보린정"])
    retrieve_service.db_holder["product_ingredients"] = {"게보린정": ("무관성분코드",)}

    chunks = retrieve_service.search_documents(db, "게보린 부작용", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == summary.page_content


def test_search_documents_falls_back_to_item_name_only_without_bridge_entry(monkeypatch):
    """브릿지 사전에 없는 제품(등록 안 됐거나 단일 성분 매핑이 비어있는 경우)은 예전처럼
    item_name 필터만 걸어야 한다 — $or 도입 전 동작을 그대로 보존."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    summary = Document(page_content="게보린 e약은요 요약", metadata={"item_name": "게보린정"})
    unrelated_dur_rule = Document(page_content="무관 DUR 규칙", metadata={"ingr_name": "아세트아미노펜"})
    db = FakeChromaDb([(summary, 0.1), (unrelated_dur_rule, 0.1)])
    retrieve_service.db_holder["ingr_names"] = DrugNameIndex()
    retrieve_service.db_holder["drug_names"] = build_index(["게보린정"])
    retrieve_service.db_holder["product_ingredients"] = {}

    chunks = retrieve_service.search_documents(db, "게보린 부작용", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == summary.page_content


def test_search_documents_finds_rule_by_mixture_side_ingredient(monkeypatch):
    """T-LLM-2-dur-interaction-mixture-index 실측 버그: 병용금기 원본은 성분을 주성분/
    상대성분 두 칸에 나눠 적는다(예: "메나테트레논+와파린"). 와파린은 이 데이터에서 항상
    상대성분 칸에만 나오는데, ingr_name(주성분 칸)만 보는 필터로는 절대 못 찾았다 —
    데이터는 있는데 반대쪽 칸에 있다는 이유만으로 0건("와파린 노인이 먹어도 돼?" 실측).
    mixture_ingr_name도 $or로 같이 봐야 한다."""
    monkeypatch.setattr(retrieve_service.settings, "RAG_SIMILARITY_THRESHOLD", 10.0)
    interaction_rule = Document(
        page_content="메나테트레논-와파린 병용금기 규칙",
        metadata={"ingr_name": "메나테트레논", "mixture_ingr_name": "와파린"},
    )
    unrelated = Document(page_content="무관 규칙", metadata={"ingr_name": "무관성분"})
    db = FakeChromaDb([(interaction_rule, 0.1), (unrelated, 0.1)])
    retrieve_service.db_holder["ingr_names"] = build_ingredient_index(["와파린", "무관성분"])

    chunks = retrieve_service.search_documents(db, "와파린 노인이 먹어도 돼?", limit=3)

    assert len(chunks) == 1
    assert chunks[0].content == interaction_rule.page_content


def test_drug_name_index_is_empty_by_default():
    """색인 전이거나 캐싱이 실패해도 검색이 터지지 않고 그냥 0건이어야 한다."""
    assert DrugNameIndex().resolve("타이레놀 부작용") is None
