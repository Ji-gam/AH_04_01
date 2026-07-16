from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.profiles import Profile


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
        self,
        session: AsyncSession,
        session_id: int,
        role: MessageRole,
        content: str,
        sources: list[dict] | None = None,
        disclaimer: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content, sources=sources, disclaimer=disclaimer)
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message

    async def list_messages(self, session: AsyncSession, session_id: int, limit: int = 20) -> list[ChatMessage]:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def list_all_sessions(
        self, session: AsyncSession, limit: int = 50, offset: int = 0
    ) -> list[tuple[ChatSession, str]]:
        """관리자 전용: 전체 프로필의 세션을 최신순으로 조회한다(patient 라우터는 profile_id로 스코핑되지만
        이건 그 반대 - 모니터링 목적이라 의도적으로 스코프를 안 건다)."""
        result = await session.execute(
            select(ChatSession, Profile.name)
            .join(Profile, ChatSession.profile_id == Profile.id)
            .order_by(ChatSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(row.ChatSession, row.name) for row in result]
