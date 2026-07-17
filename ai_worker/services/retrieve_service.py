from typing import Any

from langchain_chroma import Chroma

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger
from ai_worker.ingest.pipeline import build_vector_store
from ai_worker.ingest.sources import STRUCTURED
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.services.drug_name_resolver import DrugNameIndex, build_index

logger = setup_logger("ai_worker.retrieve_service")

# DUR 규칙은 CSV라 structured 컬렉션에 있다. 이름 문자열을 여기 또 적지 않는다 —
# 예전엔 "dur_rules"가 매니페스트 + 파이썬 3곳에 흩어져 있었고, 그 파일들엔 하나같이
# "매니페스트의 collection: 값과 일치해야 한다"는 주석이 붙어 있었다. 손으로 맞춰야 하는
# 것을 주석으로 경고하는 대신, 맞출 필요가 없게 한 곳에서 가져온다.
#
# 이 컬렉션엔 DUR 규칙(성분 단위)과 e약은요(제품 단위)가 함께 있다. 둘은 필터 키가 달라
# 서로 섞이지 않는다 — DUR 문서엔 ingr_name만, e약은요 문서엔 item_name만 있다.
COLLECTION_NAME = STRUCTURED

# 싱글톤 데이터베이스 인스턴스 및 이름 캐시 홀더.
# 값 타입을 Any로 둔 이유: 테스트에서 이 딕셔너리에 실제 Chroma 대신 duck-typed
# fake 객체를 직접 대입해 모킹하므로(ai_worker/tests/test_main.py 참고), Chroma로
# 좁히면 오히려 모킹이 막힌다.
db_holder: dict[str, Any] = {
    "db": None,
    "ingr_names": set(),
    "drug_names": DrugNameIndex(),
}


def cache_searchable_names(db: Chroma) -> None:
    """적재된 문서에서 질의에 쓸 이름을 뽑아 캐싱한다 — 성분명과 약 이름 **둘 다**.

    약 이름을 같이 담는 이유: 사람은 "아세트아미노펜 부작용"이 아니라 "타이레놀 부작용"이라고
    묻는다. 성분명만 보던 시절엔 그런 질문이 전부 0건이었다(`drug_name_resolver` 참고)."""
    try:
        logger.info("Extracting searchable names (ingredients + drug names) from ChromaDB...")
        # metadatas만 조회 (langchain-chroma의 공개 API — 사설 `_collection` 미사용)
        data = db.get(include=["metadatas"])
        metadatas = (data.get("metadatas") or []) if data else []
        ingr_names: set[str] = set()
        item_names: set[str] = set()
        for meta in metadatas:
            if not meta:
                continue
            ingr_name = meta.get("ingr_name")
            if isinstance(ingr_name, str) and ingr_name.strip():
                ingr_names.add(ingr_name.strip())
            item_name = meta.get("item_name")
            if isinstance(item_name, str) and item_name.strip():
                item_names.add(item_name.strip())
        db_holder["ingr_names"] = ingr_names
        db_holder["drug_names"] = build_index(item_names)
        logger.info(f"Cached {len(ingr_names)} ingredients and {len(item_names)} drug names")
    except Exception as e:
        logger.error(f"Failed to cache searchable names: {e}")


def initialize_rag() -> None:
    """서비스 기동 시 벡터스토어 핸들과 성분명 인덱스를 캐싱한다. **색인은 하지 않는다.**

    예전엔 여기서 `ingest_all()`을 돌렸고, 그게 이 시스템 최악의 버그였다. cleanup="full"
    이라 `source/`에 파일이 하나 안 보이면(다른 컴퓨터, git에 없는 큰 파일, 볼륨 미마운트)
    그 문서들이 **부팅과 동시에 삭제**됐다. 아래 except가 그걸 로그로만 삼켜서 아무도 몰랐다.

    색인은 사건이지 감시 루프가 아니다. 사람이 `python -m ai_worker.ingest`를 치거나
    관리자 화면에서 누를 때만 돈다."""
    logger.info("Initializing RAG...")
    try:
        db = build_vector_store(COLLECTION_NAME)
        db_holder["db"] = db
        cache_searchable_names(db)
        logger.info("RAG Initialization completed.")
    except Exception as e:
        logger.error(f"Failed to initialize RAG on startup: {e}")


def ensure_db() -> Chroma:
    """벡터스토어가 아직 초기화되지 않았으면 lazy하게 만든다.
    실패 시(`EmbeddingUnavailableError` 등) 도메인 예외를 그대로 전파한다 — HTTP 매핑은 라우터 몫."""
    db = db_holder["db"]
    if db is None:
        db = build_vector_store(COLLECTION_NAME)
        db_holder["db"] = db
        cache_searchable_names(db)
    return db


def _build_filter(query: str) -> dict[str, Any] | None:
    """질의에서 성분명이나 약 이름을 찾아 메타데이터 필터를 만든다. 못 찾으면 None.

    성분명을 먼저 본다 — DUR 금기/주의 규칙이 성분 단위라 더 구체적인 답이기 때문이다.
    성분명이 없으면 약 이름으로 e약은요(효능/용법/부작용 산문)를 찾는다.

    둘은 서로 배타적이다: DUR 문서엔 ingr_name만, e약은요 문서엔 item_name만 있다.
    그래서 "타이레놀 같이 먹어도 돼?"는 아직 DUR 병용금기를 못 뽑는다 — 그 규칙은
    성분(아세트아미노펜)으로 키가 걸려 있고, 제품 -> 성분 변환은 별도 작업이다."""
    query_text = query.replace(" ", "")

    # 가장 긴 성분명부터 매칭을 시도하여 정확도를 높입니다.
    for ingr in sorted(db_holder["ingr_names"], key=len, reverse=True):
        # 양방향 부분 매칭 검사:
        # 1. 쿼리 텍스트가 성분명의 일부인 경우 (예: "졸피뎀" -> "졸피뎀타르타르산염")
        # 2. 성분명이 쿼리 텍스트의 일부인 경우 (예: "졸피뎀타르타르산염에 대해" -> "졸피뎀타르타르산염")
        if (ingr in query_text) or (len(query_text) >= 2 and query_text in ingr):
            logger.info(f"Dynamic metadata filter applied: ingr_name='{ingr}'")
            return {"ingr_name": ingr}

    matched = db_holder["drug_names"].resolve(query)
    if matched is not None:
        key, products = matched
        logger.info(f"Dynamic metadata filter applied: drug '{key}' -> {len(products)}개 제품")
        # 브랜드 하나에 제품이 여럿이다("타이레놀" -> 정/서방정/현탁액...). 하나만 고르면
        # 엉뚱한 제형이 잡히므로 전부 넘기고 유사도가 고르게 한다.
        return {"item_name": products[0] if len(products) == 1 else {"$in": products}}

    return None


def search_documents(db: Chroma, query: str, limit: int) -> list[DocumentChunk]:
    """질의에서 찾아낸 성분명 또는 약 이름으로 문서를 검색한다. 둘 다 없으면 검색 자체를
    생략하고 빈 목록을 반환한다.

    필터 없이 전체를 유사도 검색하지 않는 이유: DUR 문서는 짧은 템플릿 문장이라 무관한
    성분이 임계값을 통과해버린다(실측: "혈당 관리 운동"이 항고혈압제/항히스타민제와 매칭됨,
    2026-07-16). 이건 "이 약이 안전한가"를 위한 자료이지 일반 건강 지식 베이스가 아니므로,
    약이 식별 안 되면 애초에 관련 문서가 없다고 보는 게 맞다.

    임베딩 호환성 검증(`assert_embedding_compatible`)은 호출자(라우터) 책임이다."""
    logger.info(f"Retrieving documents for query: '{query}' (limit: {limit})")

    filter_dict = _build_filter(query)

    if filter_dict is None:
        logger.info("쿼리에서 성분명·약 이름을 식별하지 못해 검색을 생략합니다.")
        return []

    # 유사도 점수(Score)를 포함한 검색 수행
    docs_with_scores = db.similarity_search_with_score(query, k=limit, filter=filter_dict)

    # 디버깅 로그 출력 (유사도 거리 분석용)
    for doc, score in docs_with_scores:
        logger.info(
            f"DEBUG_SCORE: INGR={doc.metadata.get('ingr_name')}, score={score}, "
            f"source_id={doc.metadata.get('source_id')}"
        )

    # 임계값(score < threshold)을 만족하는 유효한 문서만 반환합니다. 값은 config에서
    # 가져와 임베딩 백엔드별로 튜닝할 수 있게 한다(거리 스케일이 백엔드마다 다름).
    threshold = settings.RAG_SIMILARITY_THRESHOLD
    valid_docs_with_scores = [(doc, score) for doc, score in docs_with_scores if score < threshold]

    # 문서의 내용과 메타데이터를 함께 추출
    chunks = [
        DocumentChunk(content=doc.page_content, metadata=doc.metadata, score=score)
        for doc, score in valid_docs_with_scores
    ]
    logger.info(f"Found {len(chunks)} relevant chunks after filter and threshold (candidates: {len(docs_with_scores)})")
    return chunks
