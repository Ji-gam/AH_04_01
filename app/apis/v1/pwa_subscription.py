from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.pwa_subscription import SubscriptionCreate, SubscriptionDelete, SubscriptionResponse
from app.models.users import User
from app.services.pwa_subscription_service import PwaSubscriptionService

pwa_subscription_router = APIRouter(prefix="/pwa-subscriptions", tags=["pwa-subscriptions"])


@pwa_subscription_router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def register_subscription(
    data: SubscriptionCreate,
    user: Annotated[User, Depends(get_request_user)],
    pwa_sub_service: Annotated[PwaSubscriptionService, Depends(PwaSubscriptionService)],
) -> Response:
    sub = await pwa_sub_service.register_subscription(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": sub.id,
            "user_id": sub.user_id,
            "endpoint_url": sub.endpoint_url,
            "updated_at": sub.updated_at.isoformat(),
        },
        "message": "푸시 알림 구독을 성공적으로 갱신했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)


@pwa_subscription_router.delete("", status_code=status.HTTP_200_OK)
async def delete_subscription(
    data: SubscriptionDelete,
    user: Annotated[User, Depends(get_request_user)],
    pwa_sub_service: Annotated[PwaSubscriptionService, Depends(PwaSubscriptionService)],
) -> Response:
    await pwa_sub_service.delete_subscription(user, data)
    response_data = {"success": True, "data": None, "message": "푸시 구독이 해지되었습니다."}
    return Response(response_data, status_code=status.HTTP_200_OK)
