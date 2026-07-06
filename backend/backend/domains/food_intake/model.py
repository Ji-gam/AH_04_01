# backend/domains/food_intake/model.py
# API_Specification_v3.pdf [M7] FOOD_INTAKE_LOGS
import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class FoodIntakeLog(Base):
    __tablename__ = "food_intake_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    meal_time_type = Column(String(20), nullable=True)  # BREAKFAST/LUNCH/DINNER/SNACK
    food_name = Column(String(200), nullable=False)
    image_url = Column(String(500), nullable=True)
    key_nutrients = Column(String(200), nullable=True)
    calories = Column(Float, nullable=True)
    sugar_content = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="food_intake_logs")
