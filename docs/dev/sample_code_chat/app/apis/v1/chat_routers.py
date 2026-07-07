"""
Router 레이어 규칙: HTTP 처리만, 판단 없음.
실제 위치: app/apis/v1/chat_routers.py

실제 api_spec_core_v1.yaml의 POST /chat/sessions/{session_id}/messages를 단순화한 데모.
실제로는 JWT(bearerAuth)에서 profile_id를 꺼내지만, 데모에서는 쿼리 파라미터로 받는다.
(실제 앱에서는 `Depends(get_current_profile)`로 `Profile`을 받아 `profile.id`를 쓴다 —
app/dependencies/security.py 참고. User가 아니라 Profile 기준으로 스코핑하는 이유는
CODING_RULES.md 2-1번 참고.)
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.dtos.chat import ChatMessageRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: int, profile_id: int, body: ChatMessageRequest) -> StreamingResponse:
    service = ChatService()
    return StreamingResponse(
        service.stream_reply(profile_id, session_id, body.message),
        media_type="text/plain",
    )
