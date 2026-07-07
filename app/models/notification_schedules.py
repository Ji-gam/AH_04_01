from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Time, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FrequencyType(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class DayOfWeek(StrEnum):
    SUN = "일"
    MON = "월"
    TUE = "화"
    WED = "수"
    THU = "목"
    FRI = "금"
    SAT = "토"


class NotificationSchedule(Base):
    """복약 알림 일정. profiles.id(profile_id)를 참조 키로 쓴다 (CODING_RULES 2-1)."""

    __tablename__ = "notification_schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    medication_name: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency_type: Mapped[FrequencyType] = mapped_column(
        SAEnum(FrequencyType, native_enum=False, length=10), default=FrequencyType.DAILY, nullable=False
    )
    target_day_of_week: Mapped[DayOfWeek | None] = mapped_column(
        SAEnum(DayOfWeek, native_enum=False, length=10), nullable=True
    )
    alarm_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
