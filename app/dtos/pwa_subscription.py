import datetime

from app.dtos.base import BaseSerializerModel


class SubscriptionCreate(BaseSerializerModel):
    endpoint_url: str
    p256dh_key: str
    auth_key: str


class SubscriptionResponse(BaseSerializerModel):
    id: int
    user_id: int
    endpoint_url: str
    updated_at: datetime.datetime


class SubscriptionDelete(BaseSerializerModel):
    endpoint_url: str
