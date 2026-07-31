"""
Service 레이어 규칙 (nickname_service.py와 동일): 판단은 여기서만 한다.
실제 위치: app/services/chat_service.py (T-LLM-2, CODING_RULES.md 2번)

이 파일이 `chat_flow_sequence.mermaid`에 그려진 실시간 RAG 챗봇 흐름의 실제 코드다:
SafetyService(응급 감지) → UserHealthContextService(컨텍스트 조회) → Retriever(RAG stub)
→ LLM(스트리밍 stub) → ChatRepository(대화 저장). 각 단계는 이미 계층 분리돼 있으므로
Retriever/LLM stub이 실제 ai_worker/LangChain 연동으로 바뀌어도 이 흐름 구조는 그대로다
(CODING_RULES.md 6번 Tier 2 stub 패턴과 같은 원칙).
"""

from collections.abc import Iterator

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

    def stream_reply(self, profile_id: int, session_id: int, message: str) -> Iterator[str]:
        """
        T-LLM-2: 응급 감지 → (아니면) 컨텍스트 조회 → RAG 검색 → LLM 스트리밍 → 대화 저장.

        응급 키워드가 감지되면 LLM을 호출하지 않고 고정 fallback만 리턴한다(T-LLM-1 원칙).
        이 경우 대화 기록도 저장하지 않는다 — `chat_flow_sequence.mermaid`의 분기와 동일.
        """
        if safety_service.check_emergency(message):
            yield safety_service.EMERGENCY_FALLBACK_MESSAGE
            return

        context = self._health_context_service.get_context(profile_id)
        chunks = self._retriever.search(message, context)

        full_response = ""
        for token in stream_llm_reply(message, context, chunks):
            full_response += token
            yield token

        self._repository.save_message(session_id, message, full_response)
