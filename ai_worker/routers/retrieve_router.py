from fastapi import APIRouter, HTTPException

from ai_worker.core.logger import setup_logger
from ai_worker.schemas.retrieval_schema import RetrieveRequest, RetrieveResponse
from ai_worker.services.retrieve_service import db_holder, ensure_db, search_documents
from ai_worker.tasks.ingest import EmbeddingMismatchError, EmbeddingUnavailableError, assert_embedding_compatible

logger = setup_logger("ai_worker.retrieve_router")

retrieve_router = APIRouter()


@retrieve_router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_documents(payload: RetrieveRequest) -> RetrieveResponse:
    """
    입력된 쿼리에 대해 ChromaDB에서 가장 유사한 의약 안전 정보 문서(chunk)들을 검색합니다.
    쿼리 내에 성분명이 식별될 경우 메타데이터 필터링을 우선 적용합니다.
    """
    try:
        db = ensure_db()
    except EmbeddingUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector DB is not initialized. Error: {e}") from e

    # 저장된 벡터의 임베딩 모델과 현재 백엔드가 다르면 무음 오필터 대신 503으로 거부한다.
    try:
        assert_embedding_compatible(db)
    except EmbeddingMismatchError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    try:
        chunks = search_documents(db, payload.query, payload.limit)
        return RetrieveResponse(chunks=chunks)
    except Exception as e:
        logger.error(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=f"Error occurred during vector retrieval: {e}") from e


@retrieve_router.get("/health")
async def health_check():
    """
    컨테이너 헬스체크용 엔드포인트
    """
    return {"status": "healthy", "db_loaded": db_holder["db"] is not None}
