from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HabitSelection(Base):
    """오늘의 추천 습관 목록(최대 10개, habit_service.pick_recommendations) 중 사용자가
    실제로 하겠다고 고른 항목(최대 5개, 0개도 가능). 선택된 것만 홈 화면 라이프스타일
    카드/habits/today에 노출된다. habit_logs(진행량)와 별개로 "오늘 뭘 하기로 했는지"만
    기록한다 - 하루 지나면 새 select_date로 다시 골라야 한다."""

    __tablename__ = "habit_selections"
    __table_args__ = (
        UniqueConstraint("profile_id", "select_date", "habit_key", name="uq_habit_selections_profile_date_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    select_date: Mapped[date] = mapped_column(Date, nullable=False)
    habit_key: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
