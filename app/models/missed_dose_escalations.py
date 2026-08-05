from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MissedDoseEscalation(Base):
    """F-NTFY-4(미확인시 가족알림) - 알람이 울린 시각으로부터 일정 시간(기본 30분,
    push_scheduler.py의 _ESCALATION_DELAY_MINUTES) 뒤에도 MedicationIntakeLog에 그
    항목(profile_id, source_type, source_id, scheduled_time, intake_date)이 체크되어
    있지 않으면, 본인+보호자에게 "아직 안 드셨어요" 알림을 한 번 더 보낸다.

    SnoozeReminder(F-NTFY-3, 1회성 재알림)와 거의 같은 모양이지만, 이건 사용자가 직접
    예약하는 게 아니라 알람이 울릴 때마다 시스템이 자동으로 걸어두는 "미확인 체크"라는
    점이 다르다 - intake_date가 있어야 MedicationIntakeLog 조회 키(profile_id,
    source_type, source_id, scheduled_time, intake_date)를 그대로 재구성할 수 있다.

    한 행 = "이 알람 하나에 대한 미확인 체크 예약" - 체크 시각(check_at)이 지나면 복용
    여부와 무관하게(보냈든 안 보냈든) 바로 삭제한다(반복 스케줄이 아니라 1회성).
    """

    __tablename__ = "missed_dose_escalations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    medication_name: Mapped[str] = mapped_column(String(100), nullable=False)
    alarm_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM" - MedicationIntakeLog 조회 키
    intake_date: Mapped[date] = mapped_column(Date, nullable=False)  # MedicationIntakeLog 조회 키
    check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
