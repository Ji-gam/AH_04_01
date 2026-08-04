"""T-LLM-2-langfuse-user-feedback: 챗봇 답변 사용자 피드백(👍/👎) 저장 + Langfuse 점수 전달.

설계 결정 4(docs/tasks/T-LLM-2-langfuse-user-feedback.md): DB 저장이 성공하면 이 요청은
항상 성공한다. Langfuse 점수 전송(AIWorkerGateway.submit_score)은 그 뒤에 fire-and-forget으로
붙이며, 실패해도 이미 확정된 저장 결과에 영향을 주지 않는다.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessageFeedback, FeedbackValue, MessageRole
from app.repositories.chat_repository import ChatRepository
from app.services.ai_worker_gateway import AIWorkerGateway

logger = logging.getLogger("app.chat_feedback_service")

_SCORE_NAME = "user_feedback"
_SCORE_VALUE_BY_FEEDBACK = {FeedbackValue.UP: 1.0, FeedbackValue.DOWN: 0.0}


class FeedbackTargetNotFoundError(Exception):
    """메시지가 없거나 다른 프로필 소유다. 존재 여부를 노출하지 않기 위해 항상 404로 통일한다
    (chat_routers.py의 세션 조회 404 패턴과 동일)."""


class FeedbackTargetInvalidError(Exception):
    """어시스턴트 메시지가 아니다 - 사용자 자신의 질문에 별점을 매기는 건 의미가 없다."""


class ChatFeedbackService:
    def __init__(
        self,
        repository: ChatRepository | None = None,
        gateway: AIWorkerGateway | None = None,
    ) -> None:
        self._repository = repository or ChatRepository()
        self._gateway = gateway or AIWorkerGateway()

    async def submit_feedback(
        self,
        session: AsyncSession,
        profile_id: int,
        message_id: int,
        value: FeedbackValue,
        comment: str | None,
    ) -> ChatMessageFeedback:
        found = await self._repository.get_message_with_session(session, message_id)
        if found is None:
            raise FeedbackTargetNotFoundError(f"message_id={message_id} not found")
        message, chat_session = found
        if chat_session.profile_id != profile_id:
            raise FeedbackTargetNotFoundError(f"message_id={message_id} belongs to another profile")
        if message.role != MessageRole.ASSISTANT:
            raise FeedbackTargetInvalidError(f"message_id={message_id} is not an assistant message")

        feedback = await self._repository.upsert_feedback(session, message_id, value, comment)

        if message.trace_id:
            await self._gateway.submit_score(
                trace_id=message.trace_id,
                name=_SCORE_NAME,
                value=_SCORE_VALUE_BY_FEEDBACK[value],
                comment=comment,
            )
        return feedback
