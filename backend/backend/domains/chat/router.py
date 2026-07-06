# backend/domains/chat/router.py
# API_Specification_v3.pdf [M10] 챗봇 세션 개설/목록조회/메시지 전송
# TODO(조원 구현): 실제 LLM 연동과 SSE(Server-Sent Events) 스트리밍은 아직 없습니다.
# 지금은 메시지를 저장하고 고정 문구로 답하는 수준입니다. 나중에 send_message 내부를
# SSE StreamingResponse + 실제 LLM 호출로 교체하면 됩니다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import ChatSession, ChatMessage
from .schema import SessionCreate, SessionResponse, MessageCreate, MessageResponse

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201, summary="챗봇 대화 세션 개설")
def create_session(data: SessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_session = ChatSession(user_id=current_user.id, **data.model_dump())
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {
        "session_id": new_session.id,
        "user_id": new_session.user_id,
        "session_title": new_session.session_title,
        "session_intent_mode": new_session.session_intent_mode,
        "has_injected_context": new_session.has_injected_context,
        "created_at": new_session.created_at,
    }


@router.get("/sessions", response_model=list[SessionResponse], summary="챗봇 대화방 목록 조회")
def list_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [
        {
            "session_id": s.id,
            "user_id": s.user_id,
            "session_title": s.session_title,
            "session_intent_mode": s.session_intent_mode,
            "has_injected_context": s.has_injected_context,
            "created_at": s.created_at,
        }
        for s in sessions
    ]


@router.post("/sessions/{session_id}/messages", summary="실시간 챗봇 메시지 전송 [현재는 SSE 미적용, 일반 JSON 응답]")
def send_message(session_id: int, data: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="대화 세션을 찾을 수 없습니다.")

    user_msg = ChatMessage(session_id=session_id, sender_type="USER", message_text=data.content)
    db.add(user_msg)
    db.commit()

    # TODO: 여기서 실제 LLM을 호출하고, SSE(StreamingResponse)로 토큰 단위 스트리밍 응답하도록 교체
    assistant_reply = "죄송해요, 아직 실제 AI 상담 기능이 연결되지 않았어요. (플레이스홀더 응답입니다)"
    assistant_msg = ChatMessage(session_id=session_id, sender_type="ASSISTANT", message_text=assistant_reply)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return {
        "message_id": assistant_msg.id,
        "sender_type": assistant_msg.sender_type,
        "message_text": assistant_msg.message_text,
    }
