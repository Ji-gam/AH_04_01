import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger
from ai_worker.ingest.embeddings import (
    EmbeddingMismatchError,
    EmbeddingUnavailableError,
    assert_embedding_compatible,
)
from ai_worker.schemas.retrieval_schema import ChatCompletionRequest
from ai_worker.services.paper_retrieve_service import ensure_paper_db
from ai_worker.services.retrieve_service import ensure_db
from ai_worker.tasks.chat_agent import stream_chat_answer

logger = setup_logger("ai_worker.chat_agent_router")

chat_agent_router = APIRouter()


@chat_agent_router.post(
    "/agent/chat",
    summary="통합 RAG 스트리밍 채팅 (T-LLM-7-3-2)",
    description=(
        "DUR(dur_rules)+논문(pubmed_papers) 두 컬렉션을 모두 검색해 청크를 합치고, "
        "한 번의 LLM 호출로 답변을 스트리밍한다. 각 줄은 "
        "{type: 'sources'|'token'|'error', ...} 형태의 JSON이다. 관련 자료가 없으면 "
        "RAG 없이 일반 답변으로 자연히 폴백한다(별도 분류 없음). 기존 /retrieve, "
        "/agent/paper-search를 대체한다."
    ),
)
async def chat_agent_endpoint(payload: ChatCompletionRequest) -> StreamingResponse:
    # 스트리밍이 시작되면(200 응답 헤더가 이미 나가면) 상태 코드를 더 이상 바꿀 수 없으므로,
    # 확인 가능한 실패(키 없음/임베딩 불일치)는 스트림 시작 전에 걸러 503으로 응답한다.
    if settings.OPENAI_API_KEY is None:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY가 설정되지 않았습니다.")
    try:
        dur_db = ensure_db()
        assert_embedding_compatible(dur_db)
        paper_db = ensure_paper_db()
        assert_embedding_compatible(paper_db)
    except EmbeddingUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except EmbeddingMismatchError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    async def event_stream():
        try:
            async for chunk in stream_chat_answer(
                payload.message, payload.context, payload.history, payload.injected_context
            ):
                yield json.dumps(chunk, ensure_ascii=False) + "\n"
        except Exception as e:
            # 스트림이 이미 시작된 뒤의 실패는 상태 코드로 알릴 수 없어, 인밴드 error
            # 청크로 알린다 — 호출자(app/)가 이걸 보고 "받은 만큼만 저장 + 에러 표시"한다.
            logger.error(f"채팅 스트림 생성 중 오류: {e}")
            yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="text/plain")
