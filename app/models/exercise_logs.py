from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExerciseLog(Base):
    """운동 기록 한 건. `diet_logs.py`와 같은 이유로 소모 칼로리를 기록 시점에 계산한
    스냅샷으로 저장한다 - MET 시드 값이 나중에 바뀌어도 과거 기록은 그대로 남는다.

    `duration_minutes`는 입력 방식(input_mode)과 무관하게 항상 채워진다 - count 모드(줄넘기)도
    분당 100회 가정으로 환산한 시간을 저장해서 "오늘 총 운동 시간" 합계에 그대로 더할 수 있게
    한다. `distance_km`/`count`는 표시용 부가 정보로, 해당 입력 방식일 때만 채워진다."""

    __tablename__ = "exercise_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    exercise_name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_minutes: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calorie_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
