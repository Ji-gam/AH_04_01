from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.push import (
    DeviceTokenRegisterRequest,
    DeviceTokenUnregisterRequest,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    VapidPublicKeyResult,
)
from app.models.profiles import Profile
from app.models.push_subscription import PushPlatform
from app.services.push_service import PushService

push_router = APIRouter(prefix="/push", tags=["push"])


@push_router.get(
    "/vapid-public-key",
    response_model=VapidPublicKeyResult,
    summary="웹푸시 구독용 VAPID 공개키 조회",
    description="프론트가 `pushManager.subscribe()`에 넘길 공개키. 로그인 없이도 조회 가능.",
)
async def get_vapid_public_key() -> VapidPublicKeyResult:
    service = PushService()
    return VapidPublicKeyResult(public_key=service.get_vapid_public_key())


@push_router.post(
    "/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="웹푸시 구독 등록",
    description="브라우저에서 발급받은 구독 정보(endpoint+keys)를 저장한다.",
)
async def subscribe_push(
    body: PushSubscribeRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = PushService()
    await service.subscribe(session, profile.id, body.endpoint, body.keys.p256dh, body.keys.auth)


@push_router.post(
    "/unsubscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="웹푸시 구독 해제",
)
async def unsubscribe_push(
    body: PushUnsubscribeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = PushService()
    await service.unsubscribe(session, body.endpoint)


@push_router.post(
    "/register-device",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="FCM 디바이스 토큰 등록 (iOS/Android 네이티브 앱 전용)",
    description="Capacitor 등으로 패키징된 앱이 `@capacitor/push-notifications`로 발급받은 FCM 토큰을 저장한다.",
)
async def register_device_token(
    body: DeviceTokenRegisterRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = PushService()
    await service.subscribe_native(session, profile.id, PushPlatform(body.platform), body.device_token)


@push_router.post(
    "/unregister-device",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="FCM 디바이스 토큰 해제",
)
async def unregister_device_token(
    body: DeviceTokenUnregisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = PushService()
    await service.unsubscribe_native(session, body.device_token)
