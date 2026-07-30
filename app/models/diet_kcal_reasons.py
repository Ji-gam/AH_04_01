from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DietKcalReason(Base):
    """오늘의 기준 섭취 칼로리(키/몸무게 기반 개인화 값)에 대한 AI 생성 한 줄 이유 캐시.
    (profile_id, log_date) 유니크 - 같은 날 재조회마다 AI Worker를 다시 부르지 않는다
    (goal_service.py의 guide_content가 목표 row에 캐시되는 것과 같은 발상). reference_kcal도
    같이 저장해서, 그 날 안에 키/몸무게가 바뀌어 기준치가 달라지면 캐시를 갱신한다."""

    __tablename__ = "diet_kcal_reasons"
    __table_args__ = (UniqueConstraint("profile_id", "log_date", name="uq_diet_kcal_reasons_profile_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
