from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HabitDiagnosisEntrySuggestion(Base):
    """세부 진단명(subtype)이 없는 진단 항목(자유텍스트 detail/경과/조절상태/약물치료 기반)마다
    AIWorkerGateway로 한 번에 생성한 습관 5개(slot 0~4)를 캐싱해두는 테이블.

    habit_subtype_suggestions와 달리 diagnosis_entry_id로 개인 진단 항목 하나에 묶인다 - 이 경로는
    사용자가 직접 쓴 detail 등 개인화된 정보를 프롬프트에 포함하므로(habit_service.py의
    _format_diagnosis_info 참고), 세부 진단명처럼 사용자 간에 공유할 수 있는 값이 아니다. 그래서
    진단 항목이 삭제되면 캐시도 같이 지워지도록 CASCADE를 건다."""

    __tablename__ = "habit_diagnosis_entry_suggestions"
    __table_args__ = (
        UniqueConstraint("diagnosis_entry_id", "slot", name="uq_habit_diagnosis_entry_suggestions_entry_slot"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    diagnosis_entry_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("diagnosis_entries.id", ondelete="CASCADE"), nullable=False
    )
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
