from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, MessageRole


class ChatRepository:
    async def create_session(self, session: AsyncSession, profile_id: int) -> ChatSession:
        chat_session = ChatSession(profile_id=profile_id)
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)
        return chat_session

    async def get_session(self, session: AsyncSession, session_id: int) -> ChatSession | None:
        return await session.get(ChatSession, session_id)

    async def list_sessions(self, session: AsyncSession, profile_id: int) -> list[ChatSession]:
        result = await session.execute(
            select(ChatSession).where(ChatSession.profile_id == profile_id).order_by(ChatSession.created_at.desc())
        )
        return list(result.scalars().all())

    async def save_message(
        self, session: AsyncSession, session_id: int, role: MessageRole, content: str
    ) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content)
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    async def list_messages(self, session: AsyncSession, session_id: int, limit: int = 20) -> list[ChatMessage]:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(limit)
        )
        return list(reversed(result.scalars().all()))
