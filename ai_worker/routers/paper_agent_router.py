from fastapi import APIRouter, HTTPException

from ai_worker.schemas.retrieval_schema import PaperAgentRequest, PaperAgentResponse
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tasks.paper_agent import ask_paper_agent

paper_agent_router = APIRouter()


@paper_agent_router.post(
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
