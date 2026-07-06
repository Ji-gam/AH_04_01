# backend/domains/drug_food_interaction/model.py
# API_Specification_v3.pdf [M8] DRUG_FOOD_INTERACTIONS - v3 신규 모듈
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base


class DrugFoodInteraction(Base):
    __tablename__ = "drug_food_interactions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    substance_name = Column(String(100), nullable=False)
    risk_level = Column(String(20), nullable=False, default="INFO")  # INFO / WARNING / DANGER
    guidance_text = Column(Text, nullable=True)

    medication = relationship("Medication", back_populates="interactions")
