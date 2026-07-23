from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.push import (
    FcmTokenRegisterRequest,
    FcmTokenUnregisterRequest,
    MarkTakenRequest,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    ReduceFrequencyRequest,
    VapidPublicKeyResult,
)
from app.models.medication_model import MedicationSchedule
from app.models.notification_schedules import NotificationSchedule
from app.models.profiles import Profile
from app.models.push_subscription import PushPlatform
from app.services.medication_intake_service import MedicationIntakeService
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
    "/register-fcm-token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="FCM 등록 토큰 저장",
    description="Firebase JS SDK(`getToken()`)로 발급받은 FCM 등록 토큰을 저장한다(웹/네이티브 공통).",
)
async def register_fcm_token(
    body: FcmTokenRegisterRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = PushService()
    await service.subscribe_fcm(session, profile.id, PushPlatform(body.platform), body.device_token)


@push_router.post(
    "/unregister-fcm-token",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="FCM 등록 토큰 해제",
)
async def unregister_fcm_token(
    body: FcmTokenUnregisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = PushService()
    await service.unsubscribe_fcm(session, body.device_token)


@push_router.post(
    "/mark-taken",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="알림에서 바로 복용 완료 처리",
    description=(
        "알림의 '복용완료' 액션 버튼용(F-NTFY-1). 서비스워커는 로그인 세션에 접근할 수 없어 "
        "인증 없이 profile_id를 직접 받되, source_id가 그 profile_id 소유인지 서버가 검증한다. "
        "이미 체크돼있으면 조용히 아무 것도 하지 않는다(멱등)."
    ),
    responses={status.HTTP_404_NOT_FOUND: {"description": "해당 profile_id 소유가 아니거나 존재하지 않는 알림"}},
)
async def mark_taken_push(
    body: MarkTakenRequest,
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

    await MedicationIntakeService().toggle(
        session,
        body.profile_id,
        body.source_type,
        body.source_id,
        body.alarm_time,
        date.today().isoformat(),
        checked=True,
    )


@push_router.post(
    "/reduce-frequency",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="알림 빈도 줄이기",
    description=(
        "알림의 '빈도 줄이기' 액션 버튼용(F-NTFY-3). 서비스워커는 로그인 세션에 접근할 수 없어 "
        "인증 없이 profile_id를 직접 받되, source_id가 그 profile_id 소유인지 서버가 검증한다."
    ),
    responses={status.HTTP_404_NOT_FOUND: {"description": "해당 profile_id 소유가 아니거나 존재하지 않는 알림"}},
)
async def reduce_frequency_push(
    body: ReduceFrequencyRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if body.source_type == "notification_schedule":
        schedule = await session.get(NotificationSchedule, body.source_id)
        if schedule is None or schedule.profile_id != body.profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 알림을 찾을 수 없습니다.")
        # 이 행 자체가 이미 시각 하나짜리라, "빈도 줄이기" = 이 시각을 끄는 것과 같다.
        schedule.is_active = False
        await session.commit()
        return

    med_schedule = await session.get(MedicationSchedule, body.source_id)
    if med_schedule is None or med_schedule.profile_id != body.profile_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 알림을 찾을 수 없습니다.")
    # alarm_time을 모르면(예: 스누즈 재발송) 어떤 시각인지 확신 없이 지우느니 아무것도 안 한다.
    # 시각이 하나뿐이면 그것마저 지우면 알림이 통째로 사라지니(0개짜리 스케줄은 만들지 않음),
    # 그 경우도 조용히 무시한다 - 완전히 끄고 싶으면 앱에서 명시적으로 삭제해야 한다.
    if body.alarm_time and len(med_schedule.times) > 1:
        remaining = [t for t in med_schedule.times if t[:5] != body.alarm_time[:5]]
        if len(remaining) < len(med_schedule.times):
            med_schedule.times = remaining
            await session.commit()
