import datetime

from app.dtos.food_intake import FoodIntakeCreate
from app.models.food_intakes import FoodIntakeLog
from app.models.users import User


class FoodIntakeService:
    async def create_food_log(self, user: User, data: FoodIntakeCreate) -> FoodIntakeLog:
        recorded_at = data.recorded_at or datetime.datetime.now()

        new_log = await FoodIntakeLog.create(
            user=user,
            meal_time_type=data.meal_time_type,
            food_name=data.food_name,
            image_url=data.image_url,
            calories=data.calories,
            sugar_content=data.sugar_content,
            recorded_at=recorded_at,
            key_nutrients=None,  # 스텁
        )
        return new_log
