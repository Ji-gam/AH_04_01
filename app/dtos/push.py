from typing import Literal

from pydantic import BaseModel


class PushSubscribeKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscribeRequest(BaseModel):
    """브라우저 `PushSubscription.toJSON()`을 그대로 받는 형태 (endpoint + keys.p256dh/auth)."""

    endpoint: str
    keys: PushSubscribeKeys


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class VapidPublicKeyResult(BaseModel):
    public_key: str


class FcmTokenRegisterRequest(BaseModel):
    """Firebase JS SDK(`getToken()`)로 발급받은 FCM 등록 토큰을 저장한다. platform=WEB이면
    브라우저(PWA), IOS/ANDROID면 나중에 네이티브 앱이 쓸 수 있다 - device_token 하나만
    있으면 플랫폼과 무관하게 똑같은 방식으로 발송되므로 이 요청 하나로 셋 다 받는다."""

    platform: Literal["WEB", "IOS", "ANDROID"]
    device_token: str


class FcmTokenUnregisterRequest(BaseModel):
    device_token: str


class ReduceFrequencyRequest(BaseModel):
    """알림의 "빈도 줄이기" 액션 버튼 클릭 시 서비스워커가 보내는 요청(F-NTFY-3). 서비스워커는
    앱이 완전히 꺼져있어도 실행되지만 로그인 세션(JWT는 페이지 메모리에만 있음)에 접근할
    수 없어, 이 엔드포인트는 인증 없이 profile_id를 직접 받는다 - 대신 source_id가 실제로
    그 profile_id 소유인지 서버가 검증한다(push_routers.py).

    medication_schedule은 스케줄 하나가 여러 시각(times)을 가질 수 있어, alarm_time("HH:MM" -
    이 알림이 실제로 울린 시각)이 있어야 그중 정확히 어떤 시각을 뺄지 알 수 있다. 시각을 모르면
    잘못 지우느니 조용히 아무 것도 하지 않는다. notification_schedule은 한 행이 이미 시각
    하나씩이라 alarm_time이 필요 없다(그냥 그 행을 끈다)."""

    profile_id: int
    source_type: Literal["notification_schedule", "medication_schedule"]
    source_id: int
    alarm_time: str | None = None


class MarkTakenRequest(BaseModel):
    """알림의 "복용완료" 액션 버튼 클릭 시 서비스워커가 보내는 요청(F-NTFY-1). ReduceFrequencyRequest와
    같은 이유로 인증 없이 profile_id를 직접 받고, source_id 소유권은 서버가 검증한다. alarm_time이
    그대로 MedicationIntakeLog.scheduled_time이 되어 F-ADH-1 복용 기록에 반영된다 - 여러 약이
    한 알림에 묶여있으면(F-NTFY-2) 서비스워커가 묶인 항목 각각에 대해 이 요청을 반복해서 보낸다."""

    profile_id: int
    source_type: Literal["notification_schedule", "medication_schedule"]
    source_id: int
    alarm_time: str
