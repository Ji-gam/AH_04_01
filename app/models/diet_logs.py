from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DietLog(Base):
    """F-DIET-1/2: 하루 식사 한 건의 기록. 영양성분(calorie_kcal 등)은 기록 시점에 계산한
    스냅샷이다 - food_nutrition_cache가 나중에 갱신돼도 과거 기록의 값은 바뀌지 않는다.
    habit_logs.py처럼 (profile_id, log_date) 인덱스를 둬서 오늘조회/최근 7일 집계 쿼리를 받친다."""

    __tablename__ = "diet_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    food_name: Mapped[str] = mapped_column(String(150), nullable=False)
    serving_multiplier: Mapped[Decimal] = mapped_column(Numeric(3, 1), nullable=False)
    serving_grams: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    calorie_kcal: Mapped[Decimal] = mapped_column(Numeric(7, 1), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    carb_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    fat_g: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
