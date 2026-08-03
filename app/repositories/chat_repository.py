from sqlalchemy import func, select, update
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
        # 마지막 대화(메시지)가 있었던 순서다 - 생성일 순이면 오래전에 만들어 두고 방금
        # 이어서 대화한 세션이 목록 아래로 밀려난다. save_message가 매 메시지마다
        # ChatSession.updated_at을 갱신해줘야 이 정렬이 의미를 갖는다(아래 참고).
        result = await session.execute(
            select(ChatSession).where(ChatSession.profile_id == profile_id).order_by(ChatSession.updated_at.desc())
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
        trace_id: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            disclaimer=disclaimer,
            trace_id=trace_id,
        )
        session.add(message)
        # ChatSession.updated_at은 onupdate=func.now()로 선언돼 있지만, 이 세션 행 자체를
        # 건드리는 곳이 없어 지금까지 한 번도 갱신된 적이 없었다(항상 created_at과 같음).
        # list_sessions의 "마지막 대화일" 정렬이 실제로 동작하려면 매 메시지 저장마다
        # 여기서 명시적으로 찍어줘야 한다.
        await session.execute(update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now()))
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
