# backend/domains/intake_log/model.py
# API_Specification_v3.pdf [M6] INTAKE_LOGS
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from backend.core.database import Base


class IntakeLog(Base):
    __tablename__ = "intake_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("medication_schedules.id", ondelete="CASCADE"), nullable=False)
    planned_date = Column(Date, nullable=False)
    actual_take_time = Column(DateTime, nullable=True)
    status = Column(String(20), default="MISSED", nullable=False)  # COMPLETED / MISSED
    verification_media_url = Column(String(500), nullable=True)

    schedule = relationship("MedicationSchedule", back_populates="intake_logs")
