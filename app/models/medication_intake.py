from datetime import date, datetime
from typing import Literal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

IntakeSourceType = Literal["medication_schedule", "notification_schedule"]


class MedicationIntakeLog(Base):
    """복약 체크(F-ADH-1) 서버 기록. 예전엔 프론트가 `localStorage`(`intake-YYYY-MM-DD` 키)에만
    저장해서 기기를 바꾸거나 캐시를 지우면 기록이 사라졌고, 서버가 복용 여부를 전혀 몰라서
    F-ADH-2(동기부여 피드백)/F-NTFY-1(복용완료 버튼)/F-NTFY-4(미확인시 가족알림)가 전부
    막혀 있었다 - 이 테이블로 "그 날짜에 그 복용 항목을 체크했다"만 서버에 남겨서 풀어준다.

    한 행 = "체크됨" 하나를 의미한다(불리언 컬럼 대신 존재 자체로 표현) - 체크 해제는 행 삭제.
    프론트의 기존 아이템 키(`med-{schedule_id}-{HH:MM}` / `alarm-{schedule_id}`)와 1:1
    대응되도록 (source_type, source_id, scheduled_time)을 그대로 저장한다
    (medication_schedule은 하루 여러 시각이 있어 scheduled_time이 필요하고,
    notification_schedule은 행 하나가 이미 시각 하나라 사실 안 써도 되지만, 조회 로직을
    통일하기 위해 똑같이 채운다 - 그 알림의 alarm_time을 그대로 넣으면 된다)."""

    __tablename__ = "medication_intake_logs"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "source_type", "source_id", "scheduled_time", "intake_date", name="uq_intake_item_per_day"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    intake_date: Mapped[date] = mapped_column(Date, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
