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
    """알림의 "30분/1시간 후 다시" 액션 버튼 클릭 시 서비스워커가 보내는 요청. 서비스워커는
    앱이 완전히 꺼져있어도 실행되지만 로그인 세션(JWT는 페이지 메모리에만 있음)에 접근할
    수 없어, 이 엔드포인트는 인증 없이 profile_id를 직접 받는다 - 대신 source_id가 실제로
    그 profile_id 소유인지 서버가 검증한다(push_routers.py)."""

    profile_id: int
    source_type: Literal["notification_schedule", "medication_schedule"]
    source_id: int
    minutes: Literal[30, 60]
