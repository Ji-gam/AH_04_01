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
