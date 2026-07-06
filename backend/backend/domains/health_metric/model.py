# backend/domains/health_metric/model.py
# API_Specification_v3.pdf [M9] HEALTH_METRICS
# TODO(조원 구현): 지금은 등록(POST)만 있습니다. 필요하면 기간별 조회/추이 그래프용 GET도 추가해보세요.
import datetime
from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class HealthMetric(Base):
    __tablename__ = "health_metrics"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    blood_pressure_systolic = Column(Integer, nullable=True)
    blood_pressure_diastolic = Column(Integer, nullable=True)
    blood_glucose = Column(Integer, nullable=True)
    source = Column(String(10), default="MANUAL")  # MANUAL (추후 외부 연동 시 값 확장 가능)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="health_metrics")
