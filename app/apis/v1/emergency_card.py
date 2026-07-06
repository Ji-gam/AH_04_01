from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.emergency_card import EmergencyCardResponse, EmergencyCardUpsert
from app.models.users import User
from app.services.emergency_card_service import EmergencyCardService

emergency_card_router = APIRouter(prefix="/emergency-cards", tags=["emergency-cards"])


@emergency_card_router.get("", response_model=EmergencyCardResponse, status_code=status.HTTP_200_OK)
async def get_emergency_card(
    user: Annotated[User, Depends(get_request_user)],
    emergency_card_service: Annotated[EmergencyCardService, Depends(EmergencyCardService)],
) -> Response:
    card = await emergency_card_service.get_card_by_user(user)
    response_data = {
        "success": True,
        "data": {
            "id": card.id,
            "user_id": card.user_id,
            "blood_type": card.blood_type,
            "food_allergies": card.food_allergies,
            "medication_allergies": card.medication_allergies,
            "past_history": card.past_history,
            "present_history": card.present_history,
            "family_history": card.family_history,
            "emergency_contacts": card.emergency_contacts,
        },
        "message": "응급 의료 카드를 조회했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)


@emergency_card_router.put("", response_model=EmergencyCardResponse, status_code=status.HTTP_200_OK)
async def upsert_emergency_card(
    data: EmergencyCardUpsert,
    user: Annotated[User, Depends(get_request_user)],
    emergency_card_service: Annotated[EmergencyCardService, Depends(EmergencyCardService)],
) -> Response:
    card = await emergency_card_service.upsert_card(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": card.id,
            "user_id": card.user_id,
            "blood_type": card.blood_type,
            "food_allergies": card.food_allergies,
            "medication_allergies": card.medication_allergies,
            "past_history": card.past_history,
            "present_history": card.present_history,
            "family_history": card.family_history,
            "emergency_contacts": card.emergency_contacts,
        },
        "message": "응급 의료 카드를 갱신했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)
