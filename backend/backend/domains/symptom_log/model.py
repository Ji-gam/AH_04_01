# backend/domains/symptom_log/model.py
# API_Specification_v3.pdf [M9] SYMPTOM_LOGS
import datetime
from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class SymptomLog(Base):
    __tablename__ = "symptom_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symptom_notes = Column(Text, nullable=False)
    severity_level = Column(Integer, default=1)  # 1~5 단계
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="symptom_logs")
