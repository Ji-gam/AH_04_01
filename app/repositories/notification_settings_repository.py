from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_settings import NotificationSetting


class NotificationSettingsRepository:
    async def get_by_profile(self, session: AsyncSession, profile_id: int) -> NotificationSetting | None:
        result = await session.execute(select(NotificationSetting).where(NotificationSetting.profile_id == profile_id))
        return result.scalar_one_or_none()

    async def get_or_create(self, session: AsyncSession, profile_id: int) -> NotificationSetting:
        """설정이 없으면 모델 기본값(무음 22:00~07:00 등)으로 새로 만들어 반환한다. 같은
        프로필에 대해 동시에 두 요청이 들어오면 둘 다 없다고 보고 생성을 시도할 수 있는데,
        profile_id 유니크 제약으로 뒤늦게 커밋하는 쪽만 실패하니 그땐 이미 만들어진 걸
        재조회해서 반환한다(habit_repository.save_subtype_suggestions와 같은 패턴)."""
        existing = await self.get_by_profile(session, profile_id)
        if existing is not None:
            return existing

        setting = NotificationSetting(profile_id=profile_id)
        session.add(setting)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            existing = await self.get_by_profile(session, profile_id)
            if existing is not None:
                return existing
            raise
        return setting

    async def update_instance(self, session: AsyncSession, setting: NotificationSetting, data: dict[str, Any]) -> None:
        for key, value in data.items():
            setattr(setting, key, value)
        await session.flush()

    async def list_settings_with_notice_enabled(self, session: AsyncSession) -> list[NotificationSetting]:
        """전체 행을 반환한다(profile_id만이 아니라) - 브로드캐스트 쪽(notice_service.py)이
        무음 시간대까지 같이 확인해야 해서 quiet_mode_enabled/quiet_start/quiet_end도 필요하다."""
        result = await session.execute(select(NotificationSetting).where(NotificationSetting.notice_enabled.is_(True)))
        return list(result.scalars().all())

    async def list_settings_with_marketing_enabled(self, session: AsyncSession) -> list[NotificationSetting]:
        result = await session.execute(
            select(NotificationSetting).where(NotificationSetting.marketing_enabled.is_(True))
        )
        return list(result.scalars().all())
