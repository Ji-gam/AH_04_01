from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HabitLog(Base):
    """오늘 하루의 습관 실천 진행량. habit_key별 목표치/라벨은 DB에 저장하지 않고
    services/habit_service.py의 카탈로그(질환 맞춤)에서 계산한다 - 여기는 순수 진행량만 기록.
    (profile_id, log_date, habit_key) 단위로 하루 지나면 자연히 새 로우가 생겨 초기화된다."""

    __tablename__ = "habit_logs"
    __table_args__ = (UniqueConstraint("profile_id", "log_date", "habit_key", name="uq_habit_logs_profile_date_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    habit_key: Mapped[str] = mapped_column(String(50), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
