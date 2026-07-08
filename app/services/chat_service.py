"""
T-LLM-2: 응급 감지 → (아니면) 컨텍스트 조회 → RAG 검색 → LLM 스트리밍 → 대화 저장.
`docs/dev/sample_code_chat/app/services/chat_service.py`의 검증된 흐름을 실제
SQLAlchemy(AsyncSession) 기반으로 옮긴 것 — 흐름 구조 자체는 동일하다.
"""

from collections.abc import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import MessageRole
from app.repositories.chat_repository import ChatRepository
from app.services import safety_service
from app.services.llm_stub import stream_llm_reply
from app.services.retriever_stub import Retriever
from app.services.user_health_context_service import UserHealthContextService

LlmStream = Callable[[str, dict, list[str]], AsyncIterator[str]]


class ChatService:
    def __init__(
        self,
        repository: ChatRepository | None = None,
        health_context_service: UserHealthContextService | None = None,
        retriever: Retriever | None = None,
        llm_stream: LlmStream | None = None,
    ) -> None:
        self._repository = repository or ChatRepository()
        self._health_context_service = health_context_service or UserHealthContextService()
        self._retriever = retriever or Retriever()
        self._llm_stream = llm_stream or stream_llm_reply

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
        chunks = await self._retriever.search(message, context)
        content_chunks = [chunk.get("content", "") for chunk in chunks]
        sources = sorted(
            {
                chunk["metadata"]["source"]
                for chunk in chunks
                if chunk.get("metadata") and chunk["metadata"].get("source")
            }
        )

        full_response = ""
        async for token in self._llm_stream(message, context, content_chunks):
            full_response += token
            yield {"type": "token", "content": token}

        # RAG 메타데이터 출처가 존재할 경우, 답변 끝에 출처를 합성하여 노출하고 데이터베이스에도 함께 기록합니다.
        if sources:
            source_text = f"\n\n[출처: {', '.join(sources)}]"
            full_response += source_text
            yield {"type": "token", "content": source_text}

        await self._repository.save_message(session, session_id, MessageRole.USER, message)
        await self._repository.save_message(session, session_id, MessageRole.ASSISTANT, full_response)

        # T-LLM-1: 면책조항은 RAG 매칭 여부와 무관하게 항상 노출한다(끄거나 숨길 수 없음).
        yield {"type": "done", "content": "", "disclaimer": safety_service.DISCLAIMER_TEXT}
