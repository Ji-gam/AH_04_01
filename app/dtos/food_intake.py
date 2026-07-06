import datetime

from app.dtos.base import BaseSerializerModel


class FoodIntakeCreate(BaseSerializerModel):
    meal_time_type: str
    food_name: str
    image_url: str | None = None
    calories: float | None = None
    sugar_content: float | None = None
    recorded_at: datetime.datetime | None = None


class FoodIntakeResponse(BaseSerializerModel):
    id: int
    meal_time_type: str
    food_name: str
    key_nutrients: str | None = None
    calories: float | None = None
    sugar_content: float | None = None
    recorded_at: datetime.datetime
