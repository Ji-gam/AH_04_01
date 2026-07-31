from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SnoozeReminder(Base):
    """F-NTFY-3(미루기) - 알림을 눌러 연 인앱 화면에서 "30분/1시간 후에"를 고르면 생기는
    1회성 재알림 예약. 반복 스케줄(NotificationSchedule)과 달리 한 번 발송되면 바로 삭제되어
    쌓이지 않는다(push_scheduler.py 참고)."""

    __tablename__ = "snooze_reminders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    medication_name: Mapped[str] = mapped_column(String(100), nullable=False)
    alarm_time: Mapped[str] = mapped_column(String(5), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
