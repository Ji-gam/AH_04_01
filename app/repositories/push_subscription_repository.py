from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_subscription import PushPlatform, PushSubscription

NATIVE_PLATFORMS = (PushPlatform.IOS, PushPlatform.ANDROID)


class PushSubscriptionRepository:
    async def get_by_endpoint(self, session: AsyncSession, endpoint: str) -> PushSubscription | None:
        result = await session.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
        return result.scalar_one_or_none()

    async def create(
        self, session: AsyncSession, profile_id: int, endpoint: str, p256dh_key: str, auth_key: str
    ) -> PushSubscription:
        sub = PushSubscription(
            profile_id=profile_id,
            platform=PushPlatform.WEB,
            endpoint=endpoint,
            p256dh_key=p256dh_key,
            auth_key=auth_key,
        )
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return sub

    async def delete_by_endpoint(self, session: AsyncSession, endpoint: str) -> None:
        await session.execute(delete(PushSubscription).where(PushSubscription.endpoint == endpoint))
        await session.commit()

    async def update_profile_id(self, session: AsyncSession, subscription_id: int, new_profile_id: int) -> None:
        """같은 브라우저에서 다른 계정으로 로그인해 재구독한 경우, 그 endpoint의 소유자를
        바꾼다."""
        result = await session.execute(select(PushSubscription).where(PushSubscription.id == subscription_id))
        sub = result.scalar_one_or_none()
        if sub:
            sub.profile_id = new_profile_id
            await session.commit()

    async def delete_by_id(self, session: AsyncSession, subscription_id: int) -> None:
        """웹푸시 발송이 410 Gone(구독 만료/취소)으로 실패하면 스케줄러가 이걸로 정리한다."""
        await session.execute(delete(PushSubscription).where(PushSubscription.id == subscription_id))
        await session.commit()

    async def list_web_subscriptions_for_profile(
        self, session: AsyncSession, profile_id: int
    ) -> list[PushSubscription]:
        result = await session.execute(
            select(PushSubscription).where(
                PushSubscription.profile_id == profile_id, PushSubscription.platform == PushPlatform.WEB
            )
        )
        return list(result.scalars().all())

    async def list_native_subscriptions_for_profile(
        self, session: AsyncSession, profile_id: int
    ) -> list[PushSubscription]:
        """iOS/Android 네이티브 앱(device_token 기반) 구독만 가져온다 - FCM 발송용."""
        result = await session.execute(
            select(PushSubscription).where(
                PushSubscription.profile_id == profile_id, PushSubscription.platform.in_(NATIVE_PLATFORMS)
            )
        )
        return list(result.scalars().all())

    async def get_by_device_token(self, session: AsyncSession, device_token: str) -> PushSubscription | None:
        result = await session.execute(select(PushSubscription).where(PushSubscription.device_token == device_token))
        return result.scalar_one_or_none()

    async def create_native(
        self, session: AsyncSession, profile_id: int, platform: PushPlatform, device_token: str
    ) -> PushSubscription:
        sub = PushSubscription(profile_id=profile_id, platform=platform, device_token=device_token)
        session.add(sub)
        await session.commit()
        await session.refresh(sub)
        return sub

    async def delete_by_device_token(self, session: AsyncSession, device_token: str) -> None:
        await session.execute(delete(PushSubscription).where(PushSubscription.device_token == device_token))
        await session.commit()
