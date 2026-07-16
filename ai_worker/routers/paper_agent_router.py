from fastapi import APIRouter, HTTPException

from ai_worker.schemas.retrieval_schema import PaperAgentRequest, PaperAgentResponse
from ai_worker.services.paper_retrieve_service import ensure_paper_db
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tasks.ingest import EmbeddingMismatchError, EmbeddingUnavailableError, assert_embedding_compatible
from ai_worker.tasks.paper_agent import ask_paper_agent

paper_agent_router = APIRouter()


@paper_agent_router.post(
    "/agent/paper-search",
    response_model=PaperAgentResponse,
    summary="질환 논문 검색 에이전트 (T-LLM-7~7-3)",
    description=(
        "5대 질환(암/심장질환/뇌혈관질환/당뇨/간질환) 관련 질문에, 미리 색인된 PubMed 논문 "
        "벡터 검색 결과를 근거로 답한다. 기존 /retrieve(DUR 검색)와는 완전히 별개 파이프라인이다."
    ),
)
async def paper_agent_endpoint(payload: PaperAgentRequest) -> PaperAgentResponse:
    try:
        db = ensure_paper_db()
    except EmbeddingUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    # 저장된 벡터의 임베딩 모델과 현재 백엔드가 다르면 무음 오필터 대신 503으로 거부한다.
    try:
        assert_embedding_compatible(db)
    except EmbeddingMismatchError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    try:
        answer, sources = await ask_paper_agent(payload.question, db)
    except GenerationUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PaperAgentResponse(answer=answer, sources=sources)
