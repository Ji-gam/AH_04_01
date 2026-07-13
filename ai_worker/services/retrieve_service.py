from typing import Any

from langchain_chroma import Chroma

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.tasks.ingest import build_vector_store, ingest_csv_data

logger = setup_logger("ai_worker.retrieve_service")

# 싱글톤 데이터베이스 인스턴스 및 성분명 캐시 홀더.
# 값 타입을 Any로 둔 이유: 테스트에서 이 딕셔너리에 실제 Chroma 대신 duck-typed
# fake 객체를 직접 대입해 모킹하므로(ai_worker/tests/test_main.py 참고), Chroma로
# 좁히면 오히려 모킹이 막힌다.
db_holder: dict[str, Any] = {
    "db": None,
    "ingr_names": set(),
}


def cache_ingr_names(db: Chroma) -> None:
    """ChromaDB 적재 문서로부터 모든 성분명을 추출하여 캐싱합니다."""
    try:
        logger.info("Extracting and caching unique drug ingredients from ChromaDB...")
        # metadatas만 조회 (langchain-chroma의 공개 API — 사설 `_collection` 미사용)
        data = db.get(include=["metadatas"])
        metadatas = (data.get("metadatas") or []) if data else []
        names = set()
        for meta in metadatas:
            if not meta:
                continue
            ingr_name = meta.get("ingr_name")
            if isinstance(ingr_name, str) and ingr_name:
                names.add(ingr_name.strip())
        db_holder["ingr_names"] = names
        logger.info(f"Cached {len(names)} unique ingredients (e.g., {list(names)[:5]})")
    except Exception as e:
        logger.error(f"Failed to cache ingredient names: {e}")


def initialize_rag() -> None:
    """서비스 기동 시 데이터 인덱싱(Ingestion)을 자동 수행하고,
    크로마 DB 연결 객체와 성분명 인덱스를 캐싱합니다."""
    logger.info("Initializing RAG Ingestion on startup...")
    try:
        db = ingest_csv_data()
        db_holder["db"] = db
        cache_ingr_names(db)
        logger.info("RAG Initialization completed.")
    except Exception as e:
        logger.error(f"Failed to initialize RAG on startup: {e}")


def ensure_db() -> Chroma:
    """벡터스토어가 아직 초기화되지 않았으면 lazy하게 만든다.
    실패 시(`EmbeddingUnavailableError` 등) 도메인 예외를 그대로 전파한다 — HTTP 매핑은 라우터 몫."""
    db = db_holder["db"]
    if db is None:
        db = build_vector_store()
        db_holder["db"] = db
        cache_ingr_names(db)
    return db


def search_documents(db: Chroma, query: str, limit: int) -> list[DocumentChunk]:
    """입력된 쿼리에 대해 ChromaDB에서 가장 유사한 의약 안전 정보 문서(chunk)들을 검색합니다.
    쿼리 내에 성분명이 식별될 경우 메타데이터 필터링을 우선 적용합니다.
    임베딩 호환성 검증(`assert_embedding_compatible`)은 호출자(라우터) 책임이다."""
    logger.info(f"Retrieving documents for query: '{query}' (limit: {limit})")

    # 쿼리 내 성분명 매칭 기반 동적 메타데이터 필터링
    filter_dict = None
    query_text = query.replace(" ", "")
    ingr_names = db_holder["ingr_names"]

    # 가장 긴 성분명부터 매칭을 시도하여 정확도를 높입니다.
    sorted_ingrs = sorted(list(ingr_names), key=len, reverse=True)
    for ingr in sorted_ingrs:
        # 양방향 부분 매칭 검사:
        # 1. 쿼리 텍스트가 성분명의 일부인 경우 (예: "졸피뎀" -> "졸피뎀타르타르산염")
        # 2. 성분명이 쿼리 텍스트의 일부인 경우 (예: "졸피뎀타르타르산염에 대해" -> "졸피뎀타르타르산염")
        if (ingr in query_text) or (len(query_text) >= 2 and query_text in ingr):
            filter_dict = {"ingr_name": ingr}
            logger.info(f"Dynamic metadata filter applied: ingr_name='{ingr}'")
            break

    # 유사도 점수(Score)를 포함한 검색 수행
    docs_with_scores = db.similarity_search_with_score(query, k=limit, filter=filter_dict)

    # 디버깅 로그 출력 (유사도 거리 분석용)
    for doc, score in docs_with_scores:
        logger.info(
            f"DEBUG_SCORE: INGR={doc.metadata.get('ingr_name')}, score={score}, source={doc.metadata.get('source')}"
        )

    # 임계값(score < threshold)을 만족하는 유효한 문서만 반환합니다. 값은 config에서
    # 가져와 임베딩 백엔드별로 튜닝할 수 있게 한다(거리 스케일이 백엔드마다 다름).
    threshold = settings.RAG_SIMILARITY_THRESHOLD
    valid_docs = [doc for doc, score in docs_with_scores if score < threshold]

    # 문서의 내용과 메타데이터를 함께 추출
    chunks = [DocumentChunk(content=doc.page_content, metadata=doc.metadata) for doc in valid_docs]
    logger.info(f"Found {len(chunks)} relevant chunks after filter and threshold (candidates: {len(docs_with_scores)})")
    return chunks
