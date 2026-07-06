# backend/domains/food_intake/schema.py
import datetime
from typing import Optional
from pydantic import BaseModel


class FoodIntakeCreate(BaseModel):
    meal_time_type: str
    food_name: str
    image_url: Optional[str] = None
    calories: Optional[float] = None
    sugar_content: Optional[float] = None
    recorded_at: Optional[datetime.datetime] = None


class FoodIntakeResponse(BaseModel):
    food_log_id: int
    meal_time_type: str
    food_name: str
    key_nutrients: Optional[str] = None
    calories: Optional[float] = None
    sugar_content: Optional[float] = None
    recorded_at: datetime.datetime
