from fastapi import APIRouter, HTTPException

from ai_worker.schemas.retrieval_schema import PaperAgentRequest, PaperAgentResponse
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tasks.paper_agent import ask_paper_agent
from ai_worker.tools.paper_search import PaperSearchUnavailableError

paper_agent_router = APIRouter()


@paper_agent_router.post(
    "/agent/paper-search",
    response_model=PaperAgentResponse,
    summary="질환 논문 검색 에이전트 (T-LLM-7~7-3)",
    description=(
        "5대 질환(암/심장질환/뇌혈관질환/당뇨/간질환) 관련 질문에 PubMed 검색 결과를 "
        "근거로 답한다. 기존 /retrieve(DUR 검색)와는 완전히 별개 파이프라인이다."
    ),
)
async def paper_agent_endpoint(payload: PaperAgentRequest) -> PaperAgentResponse:
    try:
        answer = await ask_paper_agent(payload.question)
    except (GenerationUnavailableError, PaperSearchUnavailableError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PaperAgentResponse(answer=answer)
