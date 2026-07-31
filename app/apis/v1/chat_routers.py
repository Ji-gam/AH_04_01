import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionCreateResponse,
    ChatSessionResponse,
)
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
        "각 줄은 {type: 'sources'|'token'|'emergency_fallback'|'done', content, disclaimer?, sources?} "
        "형태의 JSON이다. sources는 답변 생성에 쓰인 DUR/논문 출처 목록(토큰보다 먼저 도착). "
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
        async for chunk in ChatService().stream_reply(profile.id, session_id, body.message):
            yield json.dumps(chunk, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="text/plain")


@chat_router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="채팅 세션 목록 조회",
    description="현재 로그인한 프로필의 이전 채팅 세션(대화방) 리스트를 마지막 대화일 기준 최신순으로 조회한다.",
)
async def list_chat_sessions(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatSessionResponse]:
    sessions = await ChatRepository().list_sessions(session, profile.id)
    return [ChatSessionResponse(id=s.id, created_at=s.created_at, updated_at=s.updated_at) for s in sessions]


@chat_router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    summary="채팅 메시지 이력 조회",
    description="특정 채팅 세션의 이전 대화 메시지 목록을 시간순으로 조회한다.",
    responses={
        404: {"description": "세션이 존재하지 않거나 다른 프로필 소유의 세션이다."},
    },
)
async def list_chat_messages(
    session_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ChatMessageResponse]:
    chat_session = await ChatRepository().get_session(session, session_id)
    if chat_session is None or chat_session.profile_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="채팅 세션을 찾을 수 없습니다.")

    messages = await ChatRepository().list_messages(session, session_id)
    # MessageRole enum 값 자체가 "USER"/"ASSISTANT"(대문자)라, 프론트(useChatStream.ts)가
    # 기대하는 소문자 "user"/"assistant"로 API 경계에서 변환한다(DB/모델은 그대로 둠).
    return [
        ChatMessageResponse(
            role=m.role.value.lower(),
            content=m.content,
            sources=m.sources,
            disclaimer=m.disclaimer,
            created_at=m.created_at,
        )
        for m in messages
    ]
