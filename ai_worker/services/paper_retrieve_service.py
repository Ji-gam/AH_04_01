from typing import Any

from langchain_chroma import Chroma

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger
from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.services.disease_query_resolver import resolve_diseases
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


def search_papers(db: Chroma, query: str, limit: int, conditions: list[str] | None = None) -> list[DocumentChunk]:
    """질환 사전(`disease_query_resolver`)으로 대상 질환을 판별해 메타데이터 필터를 걸고
    pubmed_papers를 검색한다.

    T-LLM-7-3-2는 "임계값만으로 무관한 질문이 걸러진다"는 전제로 질환 필터를 뺐었다.
    그 전제는 인사말류에는 맞았지만(임계값 0.40 위로 안전하게 걸러짐) 질환 간 구분에는
    틀렸다 — "고혈압에 좋은 운동은?"의 1위가 당뇨 논문이었다(2026-07-17 실측). 임베딩이
    질환보다 주제("운동")에 지배당해 점수가 0.34~0.39 좁은 구간에 뭉치므로 임계값 조정으로
    분리할 수 없다. LLM 분류기를 다시 들이지 않고 사전으로 해결한 이유는
    `disease_query_resolver` 모듈 docstring 참고.

    대상 질환을 못 정하면(질의에도 없고 사용자 진단 이력에도 없음) 빈 목록을 반환한다 —
    성분명이 없으면 DUR 검색을 생략하는 `retrieve_service.search_documents()`와 같은 판단.
    """
    diseases = resolve_diseases(query, conditions)
    if not diseases:
        logger.info("질의/사용자 진단 이력에서 대상 질환을 정하지 못해 논문 검색을 생략합니다.")
        return []

    logger.info(f"Retrieving paper chunks for query: '{query}' (diseases: {diseases}, limit: {limit})")

    # 값이 str(단일)일 수도 dict($in, 복수)일 수도 있어 dict[str, Any]로 명시한다.
    filter_dict: dict[str, Any] = {"disease": diseases[0]} if len(diseases) == 1 else {"disease": {"$in": diseases}}
    docs_with_scores = db.similarity_search_with_score(query, k=limit, filter=filter_dict)

    for doc, score in docs_with_scores:
        logger.info(f"DEBUG_SCORE: PMID={doc.metadata.get('pmid')}, score={score}")

    threshold = settings.PAPER_SIMILARITY_THRESHOLD
    valid_docs_with_scores = [(doc, score) for doc, score in docs_with_scores if score < threshold]

    chunks = [
        DocumentChunk(content=doc.page_content, metadata=doc.metadata, score=score)
        for doc, score in valid_docs_with_scores
    ]
    logger.info(f"Found {len(chunks)} relevant paper chunks after threshold (candidates: {len(docs_with_scores)})")
    return chunks
