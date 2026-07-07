"""
T-LLM-2: 응급 감지 → (아니면) 컨텍스트 조회 → RAG 검색 → LLM 스트리밍 → 대화 저장.
`docs/dev/sample_code_chat/app/services/chat_service.py`의 검증된 흐름을 실제
SQLAlchemy(AsyncSession) 기반으로 옮긴 것 — 흐름 구조 자체는 동일하다.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import MessageRole
from app.repositories.chat_repository import ChatRepository
from app.services import safety_service
from app.services.llm_stub import stream_llm_reply
from app.services.retriever_stub import Retriever
from app.services.user_health_context_service import UserHealthContextService


class ChatService:
    def __init__(
        self,
        repository: ChatRepository | None = None,
        health_context_service: UserHealthContextService | None = None,
        retriever: Retriever | None = None,
    ) -> None:
        self._repository = repository or ChatRepository()
        self._health_context_service = health_context_service or UserHealthContextService()
        self._retriever = retriever or Retriever()

    async def create_session(self, session: AsyncSession, profile_id: int):
        return await self._repository.create_session(session, profile_id)

    async def stream_reply(
        self, session: AsyncSession, profile_id: int, session_id: int, message: str
    ) -> AsyncIterator[dict]:
        """
        응급 키워드가 감지되면 LLM을 호출하지 않고 고정 fallback만 반환한다(T-LLM-1 원칙).
        이 경우 대화 기록도 저장하지 않는다.
        """
        if safety_service.check_emergency(message):
            yield {
                "type": "emergency_fallback",
                "content": safety_service.EMERGENCY_FALLBACK_MESSAGE,
                "disclaimer": safety_service.DISCLAIMER_TEXT,
            }
            return

        history = await self._repository.list_messages(session, session_id)
        context = self._health_context_service.get_context(profile_id)
        context["history"] = [{"role": m.role, "content": m.content} for m in history]
        chunks = self._retriever.search(message, context)

        full_response = ""
        for token in stream_llm_reply(message, context, chunks):
            full_response += token
            yield {"type": "token", "content": token}

        await self._repository.save_message(session, session_id, MessageRole.USER, message)
        await self._repository.save_message(session, session_id, MessageRole.ASSISTANT, full_response)

        yield {"type": "done", "content": "", "disclaimer": safety_service.DISCLAIMER_TEXT}
