from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.schedule import ScheduleCreate, ScheduleResponse
from app.models.users import User
from app.services.schedule_service import ScheduleService

schedule_router = APIRouter(prefix="/schedules", tags=["schedules"])


@schedule_router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    data: ScheduleCreate,
    user: Annotated[User, Depends(get_request_user)],
    schedule_service: Annotated[ScheduleService, Depends(ScheduleService)],
) -> Response:
    s = await schedule_service.create_schedule(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": s.id,
            "medication_id": s.medication_id,
            "record_id": s.record_id,
            "card_alias": s.card_alias,
            "frequency_type": s.frequency_type,
            "target_day_of_week": s.target_day_of_week,
            "alarm_time": s.alarm_time.strftime("%H:%M:%S"),
            "is_active": s.is_active,
        },
        "message": "복약 알림 일정을 등록했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)


@schedule_router.get("", response_model=list[ScheduleResponse], status_code=status.HTTP_200_OK)
async def get_schedules(
    user: Annotated[User, Depends(get_request_user)],
    schedule_service: Annotated[ScheduleService, Depends(ScheduleService)],
) -> Response:
    schedules = await schedule_service.get_user_schedules(user)
    data_list = []
    for s in schedules:
        data_list.append(
            {
                "id": s.id,
                "medication_id": s.medication_id,
                "record_id": s.record_id,
                "card_alias": s.card_alias,
                "frequency_type": s.frequency_type,
                "target_day_of_week": s.target_day_of_week,
                "alarm_time": s.alarm_time.strftime("%H:%M:%S"),
                "is_active": s.is_active,
            }
        )

    response_data = {"success": True, "data": data_list, "message": "복약 알림 일정 리스트를 조회했습니다."}
    return Response(response_data, status_code=status.HTTP_200_OK)
