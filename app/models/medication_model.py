from datetime import datetime
from sqlalchemy import BigInteger, ForeignKey, String, Text, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Medication(Base):
    """의약품 마스터 데이터 테이블 (DUR / 식약처 의약품 사전 등 기준)."""

    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    standard_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    medication_name: Mapped[str] = mapped_column(String(150), nullable=False)
    form_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # TABLET / INJECTION 등
    dosage_guideline: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    precautions: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_method: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 외형 정보 (알약 인식용)
    shape: Mapped[str | None] = mapped_column(String(30), nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    letters: Mapped[str | None] = mapped_column(String(50), nullable=True)


class MedicationSchedule(Base):
    """사용자가 등록한 복약 스케줄 테이블. profile_id 단위로 권한/조회를 제어한다."""

    __tablename__ = "medication_schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    medication_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    times: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # 복용 시간 목록 (e.g. ["08:30", "19:00"])
    source_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # 인식을 통해 등록된 경우 job_id 연계
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # N:1 관계 설정
    medication: Mapped["Medication"] = relationship("Medication", lazy="joined")


class MedicationRecognitionJob(Base):
    """비동기 알약/처방전 OCR 분석 작업 기록 테이블."""

    __tablename__ = "medication_recognition_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID v4
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, processing, done, failed
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pill_photo, prescription, medical_record, medication_guide
    candidates: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)  # 후보군 리스트 [{'drug_name': ..., 'match_rate': ..., 'drug_code': ...}]
    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 추출된 텍스트 필드 정보들
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
