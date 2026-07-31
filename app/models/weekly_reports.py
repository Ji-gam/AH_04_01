from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WeeklyReport(Base):
    """일요일 오전 9시 스케줄러(push_scheduler.py)가 AI로 작성해 저장하는 주간 리포트.
    (profile_id, week_start_date) 유니크 제약으로 같은 주 중복 생성을 막는다 - 스케줄러가
    실수로 두 번 돌거나 재시도해도 안전하다."""

    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("profile_id", "week_start_date", name="uq_weekly_reports_profile_week"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
