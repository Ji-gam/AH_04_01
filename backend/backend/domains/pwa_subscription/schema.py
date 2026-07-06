# backend/domains/pwa_subscription/schema.py
import datetime
from pydantic import BaseModel


class SubscriptionCreate(BaseModel):
    endpoint_url: str
    p256dh_key: str
    auth_key: str


class SubscriptionResponse(BaseModel):
    subscription_id: int
    user_id: int
    endpoint_url: str
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class SubscriptionDelete(BaseModel):
    endpoint_url: str
