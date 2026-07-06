from fastapi import HTTPException, status

from app.dtos.chat import MessageCreate, SessionCreate
from app.models.chat_sessions import ChatMessage, ChatSession
from app.models.users import User


class ChatService:
    async def create_chat_session(self, user: User, data: SessionCreate) -> ChatSession:
        return await ChatSession.create(user=user, **data.model_dump())

    async def list_chat_sessions(self, user: User) -> list[ChatSession]:
        return await ChatSession.filter(user=user).order_by("-created_at").all()

    async def send_chat_message(self, user: User, session_id: int, data: MessageCreate) -> ChatMessage:
        session = await ChatSession.get_or_none(id=session_id, user=user)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화 세션을 찾을 수 없습니다.")

        # 사용자 메시지 저장
        await ChatMessage.create(session=session, sender_type="USER", message_text=data.content)

        # 스텁 답변 메시지 저장 (추후 OpenAI GPT 연동 및 StreamingResponse 적용 예정)
        assistant_reply = "죄송해요, 아직 실제 AI 상담 기능이 연결되지 않았어요. (플레이스홀더 응답입니다)"
        assistant_msg = await ChatMessage.create(session=session, sender_type="ASSISTANT", message_text=assistant_reply)
        return assistant_msg
