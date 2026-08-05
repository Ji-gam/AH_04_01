from fastapi import APIRouter, Response, status

from ai_worker.core import observability
from ai_worker.schemas.observability_schema import ScoreRequest

observability_router = APIRouter()


@observability_router.post(
    "/observability/score",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Langfuse trace에 점수 기록 (T-LLM-2-langfuse-user-feedback)",
    description=(
        "app/의 사용자 피드백(👍/👎) API가 DB 저장에 성공한 뒤 fire-and-forget으로 호출한다. "
        "Langfuse 키 설정은 ai_worker가 단일 소유하므로 app은 이 엔드포인트를 경유해 점수를 "
        "보낸다(설계 결정 3). 미설정/전송 실패 시에도 항상 204를 반환한다 — 관측은 부수효과일 "
        "뿐 호출부의 응답을 절대 막지 않는다."
    ),
)
async def submit_score_endpoint(payload: ScoreRequest) -> Response:
    observability.create_score(payload.trace_id, payload.name, payload.value, payload.comment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
