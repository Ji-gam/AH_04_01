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


class DeviceTokenRegisterRequest(BaseModel):
    """Capacitor 등으로 패키징된 iOS/Android 앱이 `@capacitor/push-notifications`로 받은
    FCM 디바이스 토큰을 등록할 때 쓴다. WEB은 여기 쓰지 않는다(PushSubscribeRequest 사용) -
    그래서 platform 타입 자체를 IOS/ANDROID로만 제한한다."""

    platform: Literal["IOS", "ANDROID"]
    device_token: str


class DeviceTokenUnregisterRequest(BaseModel):
    device_token: str
