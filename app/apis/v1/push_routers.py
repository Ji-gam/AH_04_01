from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.push import PushSubscribeRequest, PushUnsubscribeRequest, SnoozeRequest, VapidPublicKeyResult
from app.models.medication_model import MedicationSchedule
from app.models.notification_schedules import NotificationSchedule
from app.models.profiles import Profile
from app.services.push_scheduler import schedule_snooze
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
    "/snooze",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="복약 알림 미루기(스누즈)",
    description=(
        "알림의 '30분/1시간 후 다시' 액션 버튼용. 서비스워커는 로그인 세션에 접근할 수 없어 "
        "인증 없이 profile_id를 직접 받되, source_id가 그 profile_id 소유인지 서버가 검증한다."
    ),
    responses={status.HTTP_404_NOT_FOUND: {"description": "해당 profile_id 소유가 아니거나 존재하지 않는 알림"}},
)
async def snooze_push(
    body: SnoozeRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if body.source_type == "notification_schedule":
        schedule = await session.get(NotificationSchedule, body.source_id)
        owner_id = schedule.profile_id if schedule else None
    else:
        med_schedule = await session.get(MedicationSchedule, body.source_id)
        owner_id = med_schedule.profile_id if med_schedule else None

    if owner_id is None or owner_id != body.profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 알림을 찾을 수 없습니다.")

    schedule_snooze(request.app.state.push_scheduler, body.profile_id, body.source_type, body.source_id, body.minutes)
