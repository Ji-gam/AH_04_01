"""습관 추천 이유(habit_service._generate_detailed_reason)와 식단 기준 칼로리 이유
(DietKcalReason.reason)에 대한 사용자 평가(👍/👎)를 저장한다.

두 이유 모두 대상 자체가 고유 PK를 가진 하나의 지속적 row가 아니라서(습관 이유는 매 요청마다
새로 계산되고, 식단 이유는 (profile_id, log_date)로만 식별됨) chat_message_feedbacks처럼
message_id FK를 참조하는 대신 (feature, target_key) 조합으로 대상을 느슨하게 식별한다.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reason_feedback import FeedbackValue, ReasonFeedback, ReasonFeedbackFeature
from app.repositories.reason_feedback_repository import ReasonFeedbackRepository


class ReasonFeedbackService:
    def __init__(self, repository: ReasonFeedbackRepository | None = None) -> None:
        self._repository = repository or ReasonFeedbackRepository()

    async def submit_habit_reason_feedback(
        self, session: AsyncSession, profile_id: int, habit_key: str, value: FeedbackValue, comment: str | None
    ) -> ReasonFeedback:
        return await self._repository.upsert(
            session, profile_id, ReasonFeedbackFeature.HABIT_REASON, habit_key, value, comment
        )

    async def submit_diet_kcal_reason_feedback(
        self, session: AsyncSession, profile_id: int, log_date_iso: str, value: FeedbackValue, comment: str | None
    ) -> ReasonFeedback:
        return await self._repository.upsert(
            session, profile_id, ReasonFeedbackFeature.DIET_KCAL_REASON, log_date_iso, value, comment
        )
