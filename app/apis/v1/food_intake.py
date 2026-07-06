from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.food_intake import FoodIntakeCreate, FoodIntakeResponse
from app.models.users import User
from app.services.food_intake_service import FoodIntakeService

food_intake_router = APIRouter(prefix="/food-intakes", tags=["food-intakes"])


@food_intake_router.post("", response_model=FoodIntakeResponse, status_code=status.HTTP_201_CREATED)
async def create_food_log(
    data: FoodIntakeCreate,
    user: Annotated[User, Depends(get_request_user)],
    food_intake_service: Annotated[FoodIntakeService, Depends(FoodIntakeService)],
) -> Response:
    f = await food_intake_service.create_food_log(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": f.id,
            "meal_time_type": f.meal_time_type,
            "food_name": f.food_name,
            "key_nutrients": f.key_nutrients,
            "calories": f.calories,
            "sugar_content": f.sugar_content,
            "recorded_at": f.recorded_at.isoformat(),
        },
        "message": "식사 일지를 등록했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)
