# backend/domains/schedule/model.py
# API_Specification_v3.pdf [M6] MEDICATION_SCHEDULES
import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Time, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    record_id = Column(Integer, ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True)

    card_alias = Column(String(100), nullable=True)  # 예: "다이어트 삭센다 주사"
    frequency_type = Column(String(10), nullable=False, default="DAILY")  # DAILY / WEEKLY
    target_day_of_week = Column(String(10), nullable=True)  # WEEKLY일 때만: 월/화/.../금 등
    alarm_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="medication_schedules")
    medication = relationship("Medication", back_populates="schedules")
    record = relationship("MedicalRecord", back_populates="schedules")
    intake_logs = relationship("IntakeLog", back_populates="schedule", cascade="all, delete-orphan")
