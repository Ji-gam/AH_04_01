from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GoalProgressLog(Base):
    """목표(Goal)의 일일 수치 기록 - "오늘 기록하기"로 매일 체중/수면시간 등을 남긴다.
    (goal_id, log_date) 유니크 제약으로 같은 날 다시 기록하면 그날 값을 덮어쓴다(diary_entries의
    하루 1건 upsert와 같은 패턴). 가장 최근 값은 Goal.current_value에도 그대로 반영되어
    진행률 계산에 바로 쓰인다."""

    __tablename__ = "goal_progress_logs"
    __table_args__ = (UniqueConstraint("goal_id", "log_date", name="uq_goal_progress_logs_goal_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
