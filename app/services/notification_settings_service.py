from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.notification_settings import NotificationSettingsUpdateRequest
from app.models.notification_settings import NotificationSetting
from app.repositories.notification_settings_repository import NotificationSettingsRepository


class NotificationSettingsService:
    def __init__(self) -> None:
        self._repo = NotificationSettingsRepository()

    async def get_settings(self, session: AsyncSession, profile_id: int) -> NotificationSetting:
        setting = await self._repo.get_or_create(session, profile_id)
        await session.commit()
        return setting

    async def update_settings(
        self, session: AsyncSession, profile_id: int, data: NotificationSettingsUpdateRequest
    ) -> NotificationSetting:
        setting = await self._repo.get_or_create(session, profile_id)
        await self._repo.update_instance(session, setting, data.model_dump(exclude_unset=True))
        await session.commit()
        return setting
