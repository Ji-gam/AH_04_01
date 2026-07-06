from fastapi import HTTPException, status

from app.dtos.pwa_subscription import SubscriptionCreate, SubscriptionDelete
from app.models.pwa_subscriptions import PwaSubscription
from app.models.users import User


class PwaSubscriptionService:
    async def register_subscription(self, user: User, data: SubscriptionCreate) -> PwaSubscription:
        existing = await PwaSubscription.get_or_none(endpoint_url=data.endpoint_url)
        if existing:
            existing.p256dh_key = data.p256dh_key
            existing.auth_key = data.auth_key
            existing.user = user
            await existing.save()
            return existing
        else:
            sub = await PwaSubscription.create(user=user, **data.model_dump())
            return sub

    async def delete_subscription(self, user: User, data: SubscriptionDelete) -> None:
        sub = await PwaSubscription.get_or_none(endpoint_url=data.endpoint_url, user=user)
        if not sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="구독 정보를 찾을 수 없습니다.")
        await sub.delete()
