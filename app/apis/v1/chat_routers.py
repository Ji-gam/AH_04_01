import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.chat import ChatMessageRequest, ChatSessionCreateResponse
from app.models.profiles import Profile
from app.repositories.chat_repository import ChatRepository
from app.services.chat_service import ChatService

chat_router = APIRouter(prefix="/chat", tags=["Chat"])


@chat_router.post(
    "/sessions",
    response_model=ChatSessionCreateResponse,
    summary="채팅 세션 생성",
    description="현재 로그인한 프로필의 새 채팅 세션을 생성한다.",
)
async def create_chat_session(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatSessionCreateResponse:
    chat_session = await ChatService().create_session(session, profile.id)
    return ChatSessionCreateResponse(session_id=str(chat_session.id))


@chat_router.post(
    "/sessions/{session_id}/messages",
    summary="채팅 메시지 전송(스트리밍)",
    description=(
        "메시지를 전송하고 답변을 text/plain 스트림으로 받는다. "
        "각 줄은 {type: 'token'|'emergency_fallback'|'done', content, disclaimer?} 형태의 JSON이다. "
        "응급 키워드가 감지되면 LLM 호출 없이 emergency_fallback 청크만 반환한다."
    ),
    responses={
        404: {"description": "세션이 존재하지 않거나 다른 프로필 소유의 세션이다."},
    },
)
async def send_chat_message(
    session_id: int,
    body: ChatMessageRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    chat_session = await ChatRepository().get_session(session, session_id)
    if chat_session is None or chat_session.profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="채팅 세션을 찾을 수 없습니다.")

    async def event_stream():
        async for chunk in ChatService().stream_reply(session, profile.id, session_id, body.message):
            yield json.dumps(chunk, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="text/plain")
