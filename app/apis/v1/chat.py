from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.chat import MessageCreate, MessageResponse, SessionCreate, SessionResponse
from app.models.users import User
from app.services.chat_service import ChatService

chat_router = APIRouter(prefix="/chat", tags=["chat"])


@chat_router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    user: Annotated[User, Depends(get_request_user)],
    chat_service: Annotated[ChatService, Depends(ChatService)],
) -> Response:
    s = await chat_service.create_chat_session(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": s.id,
            "user_id": s.user_id,
            "session_title": s.session_title,
            "session_intent_mode": s.session_intent_mode,
            "has_injected_context": s.has_injected_context,
            "created_at": s.created_at.isoformat(),
        },
        "message": "챗봇 대화 세션을 개설했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)


@chat_router.get("/sessions", response_model=list[SessionResponse], status_code=status.HTTP_200_OK)
async def list_sessions(
    user: Annotated[User, Depends(get_request_user)],
    chat_service: Annotated[ChatService, Depends(ChatService)],
) -> Response:
    sessions = await chat_service.list_chat_sessions(user)
    data_list = []
    for s in sessions:
        data_list.append(
            {
                "id": s.id,
                "user_id": s.user_id,
                "session_title": s.session_title,
                "session_intent_mode": s.session_intent_mode,
                "has_injected_context": s.has_injected_context,
                "created_at": s.created_at.isoformat(),
            }
        )

    response_data = {"success": True, "data": data_list, "message": "챗봇 대화방 목록을 조회했습니다."}
    return Response(response_data, status_code=status.HTTP_200_OK)


@chat_router.post("/sessions/{session_id}/messages", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def send_message(
    session_id: int,
    data: MessageCreate,
    user: Annotated[User, Depends(get_request_user)],
    chat_service: Annotated[ChatService, Depends(ChatService)],
) -> Response:
    msg = await chat_service.send_chat_message(user, session_id, data)
    response_data = {
        "success": True,
        "data": {
            "id": msg.id,
            "sender_type": msg.sender_type,
            "message_text": msg.message_text,
        },
        "message": "챗봇 답변이 도착했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)
