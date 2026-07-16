from typing import Any

from langchain_chroma import Chroma

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.tasks.ingest_papers import build_paper_vector_store

logger = setup_logger("ai_worker.paper_retrieve_service")

# retrieve_service.py의 db_holder와 완전히 별개인 싱글톤. db_holder는 ai_worker/main.py에서
# 이름으로 재노출되고 테스트가 직접 조작하므로 구조를 공유하면 DUR 쪽이 깨진다.
paper_db_holder: dict[str, Any] = {"db": None}


def ensure_paper_db() -> Chroma:
    """벡터스토어가 아직 초기화되지 않았으면 lazy하게 연다. PubMed를 호출하지 않고
    로컬 pubmed_papers 컬렉션만 연다 — 색인 전이면 빈 컬렉션이 열릴 뿐 에러가 아니다."""
    db = paper_db_holder["db"]
    if db is None:
        db = build_paper_vector_store()
        paper_db_holder["db"] = db
    return db


def search_papers(db: Chroma, query: str, disease: str, limit: int) -> list[DocumentChunk]:
    """disease로 정확히 필터링한 뒤(classify_query()가 이미 질환을 정확히 뽑아주므로
    DUR처럼 substring 매칭을 흉내낼 필요 없음) 쿼리와 유사한 논문 청크를 검색한다."""
    logger.info(f"Retrieving paper chunks for query: '{query}' (disease: {disease}, limit: {limit})")

    filter_dict = {"disease": disease}
    docs_with_scores = db.similarity_search_with_score(query, k=limit, filter=filter_dict)

    for doc, score in docs_with_scores:
        logger.info(f"DEBUG_SCORE: PMID={doc.metadata.get('pmid')}, score={score}, disease={disease}")

    threshold = settings.PAPER_SIMILARITY_THRESHOLD
    valid_docs = [doc for doc, score in docs_with_scores if score < threshold]

    chunks = [DocumentChunk(content=doc.page_content, metadata=doc.metadata) for doc in valid_docs]
    logger.info(f"Found {len(chunks)} relevant paper chunks after threshold (candidates: {len(docs_with_scores)})")
    return chunks
