from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.appointment import AppointmentCreate, AppointmentResponse
from app.models.users import User
from app.services.appointment_service import AppointmentService

appointment_router = APIRouter(prefix="/appointments", tags=["appointments"])


@appointment_router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: AppointmentCreate,
    user: Annotated[User, Depends(get_request_user)],
    appointment_service: Annotated[AppointmentService, Depends(AppointmentService)],
) -> Response:
    appt = await appointment_service.create_appointment(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": appt.id,
            "hospital_name": appt.hospital_name,
            "doctor_name": appt.doctor_name,
            "doctor_contact": appt.doctor_contact,
            "appointment_at": appt.appointment_at.isoformat(),
            "memo": appt.memo,
        },
        "message": "병원 예약 일정을 등록했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)
