# backend/domains/appointment/model.py
# API_Specification_v3.pdf [M9] HOSPITAL_APPOINTMENTS
import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class Appointment(Base):
    __tablename__ = "hospital_appointments"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hospital_name = Column(String(100), nullable=False)
    doctor_name = Column(String(50), nullable=True)
    doctor_contact = Column(String(30), nullable=True)
    appointment_at = Column(DateTime, nullable=False)
    memo = Column(Text, nullable=True)

    user = relationship("User", back_populates="appointments")
