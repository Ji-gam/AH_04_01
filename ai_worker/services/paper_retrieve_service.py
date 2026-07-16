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


def search_papers(db: Chroma, query: str, limit: int) -> list[DocumentChunk]:
    """T-LLM-7-3-2: 질문 그대로 pubmed_papers 컬렉션 전체를 벡터 검색한다(질환 사전
    분류 없음). 통합 RAG 설계상 "이 질문이 논문 검색 대상인지"를 별도 LLM 분류로
    판단하지 않고, 임계값을 통과하는 청크가 있는지로만 판단한다 — 관용구 등 무관한
    질문은 임베딩 거리 자체가 멀어 자연히 걸러진다는 전제."""
    logger.info(f"Retrieving paper chunks for query: '{query}' (limit: {limit})")

    docs_with_scores = db.similarity_search_with_score(query, k=limit)

    for doc, score in docs_with_scores:
        logger.info(f"DEBUG_SCORE: PMID={doc.metadata.get('pmid')}, score={score}")

    threshold = settings.PAPER_SIMILARITY_THRESHOLD
    valid_docs = [doc for doc, score in docs_with_scores if score < threshold]

    chunks = [DocumentChunk(content=doc.page_content, metadata=doc.metadata) for doc in valid_docs]
    logger.info(f"Found {len(chunks)} relevant paper chunks after threshold (candidates: {len(docs_with_scores)})")
    return chunks
