from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FeedbackValue(StrEnum):
    UP = "UP"
    DOWN = "DOWN"


class ReasonFeedbackFeature(StrEnum):
    HABIT_REASON = "HABIT_REASON"
    DIET_KCAL_REASON = "DIET_KCAL_REASON"


class ReasonFeedback(Base):
    """습관 추천 이유(habit_service._generate_detailed_reason)와 식단 기준 칼로리 이유
    (DietKcalReason.reason)에 대한 사용자 평가(👍/👎). chat_message_feedbacks와 같은 이유로
    별도 테이블로 둔다 - 다만 습관 이유는 대상 자체가 DB row로 저장되지 않으므로(요청마다
    계산), message_id 같은 단일 FK 대신 (feature, target_key)로 느슨하게 대상을 식별한다.
    (profile_id, feature, target_key) 유니크 - 다시 누르면 값을 갱신한다."""

    __tablename__ = "reason_feedbacks"
    __table_args__ = (
        UniqueConstraint("profile_id", "feature", "target_key", name="uq_reason_feedbacks_profile_feature_target"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[ReasonFeedbackFeature] = mapped_column(
        SAEnum(ReasonFeedbackFeature, native_enum=False, length=20), nullable=False
    )
    # HABIT_REASON이면 habit_key, DIET_KCAL_REASON이면 log_date(ISO 문자열)를 담는다.
    target_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[FeedbackValue] = mapped_column(SAEnum(FeedbackValue, native_enum=False, length=10), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
