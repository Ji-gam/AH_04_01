from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.common import normalize_phone_number
from app.dtos.users import UserUpdateRequest
from app.models.profiles import Profile
from app.models.users import User
from app.repositories.profile_repository import ProfileRepository
from app.services.auth import AuthService


class UserManageService:
    def __init__(self):
        self.profile_repo = ProfileRepository()
        self.auth_service = AuthService()

    async def update_user(
        self, session: AsyncSession, user: User, profile: Profile, data: UserUpdateRequest
    ) -> tuple[User, Profile]:
        if data.phone_number:
            normalized_phone_number = normalize_phone_number(data.phone_number)
            await self.auth_service.check_phone_number_exists(session, normalized_phone_number)
            data.phone_number = normalized_phone_number

        profile_fields = data.model_dump(exclude_none=True)
        await self.profile_repo.update_instance(session, profile, profile_fields)
        await session.commit()
        return user, profile
