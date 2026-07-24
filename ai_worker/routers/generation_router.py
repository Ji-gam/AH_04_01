from fastapi import APIRouter, HTTPException

from ai_worker.schemas.generation_schema import GenerateStructuredRequest, GenerateStructuredResponse
from ai_worker.tasks.generate_structured import GenerationUnavailableError, generate_structured

generation_router = APIRouter()


@generation_router.post(
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
