import logging

from fastapi import FastAPI, HTTPException

from ai_worker.schemas.generation_schema import GenerateStructuredRequest, GenerateStructuredResponse
from ai_worker.schemas.retrieval_schema import (
    PaperAgentRequest,
    PaperAgentResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from ai_worker.services.retrieve_service import db_holder, ensure_db, initialize_rag, search_documents
from ai_worker.tasks.generate_structured import GenerationUnavailableError, generate_structured
from ai_worker.tasks.ingest import EmbeddingMismatchError, EmbeddingUnavailableError, assert_embedding_compatible
from ai_worker.tasks.paper_agent import ask_paper_agent

# 로거 설정
logger = logging.getLogger("ai_worker.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ReMedi AI Worker Service",
    description="RAG 파이프라인 및 Vector DB 검색 서비스를 제공하는 백그라운드 워커 API",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    initialize_rag()


@app.post("/retrieve", response_model=RetrieveResponse)
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


@app.post(
    "/generate-structured",
    response_model=GenerateStructuredResponse,
    summary="범용 구조화 생성",
    description=(
        "T-LLM-2-async-gateway: system_prompt + user_input + json_schema를 받아 그 스키마를 "
        "만족하는 JSON을 생성한다. 도메인 프롬프트/스키마는 호출하는 쪽(AIWorkerGateway.call_structured)이 "
        "소유하며, 이 엔드포인트는 도메인 지식을 갖지 않는다."
    ),
)
async def generate_structured_endpoint(payload: GenerateStructuredRequest) -> GenerateStructuredResponse:
    try:
        data = await generate_structured(payload.system_prompt, payload.user_input, payload.json_schema)
    except GenerationUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return GenerateStructuredResponse(data=data)


@app.post(
    "/agent/paper-search",
    response_model=PaperAgentResponse,
    summary="질환 논문 검색 에이전트 (T-LLM-7, 스텁)",
    description=(
        "T-LLM-7: 도구 1개(질환 논문 검색 스텁)를 쥔 LangChain 에이전트. "
        "기존 /retrieve(DUR 검색)와는 완전히 별개 파이프라인이다."
    ),
)
async def paper_agent_endpoint(payload: PaperAgentRequest) -> PaperAgentResponse:
    try:
        answer = await ask_paper_agent(payload.question)
    except GenerationUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PaperAgentResponse(answer=answer)


@app.get("/health")
async def health_check():
    """
    컨테이너 헬스체크용 엔드포인트
    """
    return {"status": "healthy", "db_loaded": db_holder["db"] is not None}
