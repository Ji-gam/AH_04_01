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


class SnoozeRequest(BaseModel):
    """알림의 "30분 후 다시" 액션 버튼 클릭 시 서비스워커가 보내는 요청. 서비스워커는
    앱이 완전히 꺼져있어도 실행되지만 로그인 세션(JWT는 페이지 메모리에만 있음)에 접근할
    수 없어, 이 엔드포인트는 인증 없이 profile_id를 직접 받는다 - 대신 source_id가 실제로
    그 profile_id 소유인지 서버가 검증한다(push_routers.py). minutes=60은 지금은 알림에
    버튼이 없어 프론트에서 보낼 일이 없지만(액션 버튼 2개 제한으로 "빈도 줄이기"에 자리를
    내줌, F-NTFY-3), API 자체는 호환성을 위해 그대로 받아둔다."""

    profile_id: int
    source_type: Literal["notification_schedule", "medication_schedule"]
    source_id: int
    minutes: Literal[30, 60]


class ReduceFrequencyRequest(BaseModel):
    """알림의 "빈도 줄이기" 액션 버튼 클릭 시 서비스워커가 보내는 요청(F-NTFY-3). SnoozeRequest와
    같은 이유로 인증 없이 profile_id를 직접 받고, source_id 소유권은 서버가 검증한다.

    medication_schedule은 스케줄 하나가 여러 시각(times)을 가질 수 있어, alarm_time("HH:MM" -
    이 알림이 실제로 울린 시각)이 있어야 그중 정확히 어떤 시각을 뺄지 알 수 있다. 스누즈 후
    재발송된 알림처럼 어떤 시각인지 서버가 모르는 경우엔 alarm_time을 생략할 수 있는데,
    그럴 땐 잘못 지우느니 조용히 아무 것도 하지 않는다. notification_schedule은 한 행이 이미
    시각 하나씩이라 alarm_time이 필요 없다(그냥 그 행을 끈다)."""

    profile_id: int
    source_type: Literal["notification_schedule", "medication_schedule"]
    source_id: int
    alarm_time: str | None = None
