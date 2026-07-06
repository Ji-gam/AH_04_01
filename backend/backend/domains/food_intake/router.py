# backend/domains/food_intake/router.py
# API_Specification_v3.pdf [M7] 식사 일지 등록
import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import FoodIntakeLog
from .schema import FoodIntakeCreate, FoodIntakeResponse

router = APIRouter()


@router.post("", response_model=FoodIntakeResponse, status_code=201, summary="식사 일지 등록")
def create_food_log(data: FoodIntakeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    new_log = FoodIntakeLog(
        user_id=current_user.id,
        meal_time_type=data.meal_time_type,
        food_name=data.food_name,
        image_url=data.image_url,
        calories=data.calories,
        sugar_content=data.sugar_content,
        recorded_at=data.recorded_at or datetime.datetime.utcnow(),
        # key_nutrients는 실제로는 영양성분 분석 로직/외부 API가 필요합니다. 지금은 비워둡니다.
        key_nutrients=None,
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {
        "food_log_id": new_log.id,
        "meal_time_type": new_log.meal_time_type,
        "food_name": new_log.food_name,
        "key_nutrients": new_log.key_nutrients,
        "calories": new_log.calories,
        "sugar_content": new_log.sugar_content,
        "recorded_at": new_log.recorded_at,
    }
