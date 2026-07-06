# backend/domains/emergency_card/model.py
# API_Specification_v3.pdf [M4] EMERGENCY_CARDS
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import Base


class EmergencyCard(Base):
    __tablename__ = "emergency_cards"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    blood_type = Column(String(5), nullable=True)
    food_allergies = Column(Text, nullable=True)
    medication_allergies = Column(Text, nullable=True)
    past_history = Column(Text, nullable=True)
    present_history = Column(Text, nullable=True)
    family_history = Column(Text, nullable=True)
    emergency_contacts = Column(Text, nullable=True)

    user = relationship("User", back_populates="emergency_card")
