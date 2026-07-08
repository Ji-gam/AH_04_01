from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.common import normalize_phone_number
from app.dtos.users import BiometricInfoRequest, UserUpdateRequest
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
        if data.email:
            await self.auth_service.check_email_exists(session, data.email)
            user.email = data.email

        if data.phone_number:
            normalized_phone_number = normalize_phone_number(data.phone_number)
            await self.auth_service.check_phone_number_exists(session, normalized_phone_number)
            data.phone_number = normalized_phone_number

        profile_fields = data.model_dump(exclude_none=True, exclude={"email"})
        await self.profile_repo.update_instance(session, profile, profile_fields)
        await session.commit()
        return user, profile

    async def update_biometric_info(
        self, session: AsyncSession, user: User, profile: Profile, data: BiometricInfoRequest
    ) -> tuple[User, Profile]:
        """[T-PROFILE-1] 회원가입 직후 별도 화면(키/체중/진단병력/가족력)에서 호출된다.
        Enum 리스트는 문자열 리스트로 바꿔서 저장한다(JSON 컬럼이라 Enum 객체를 그대로 못 넣는다)."""
        profile_fields = data.model_dump(exclude_none=True)
        if "diagnosis_history" in profile_fields:
            profile_fields["diagnosis_history"] = [
                d.value if hasattr(d, "value") else d for d in profile_fields["diagnosis_history"]
            ]
        if "family_history" in profile_fields:
            profile_fields["family_history"] = [
                d.value if hasattr(d, "value") else d for d in profile_fields["family_history"]
            ]

        await self.profile_repo.update_instance(session, profile, profile_fields)
        await session.commit()
        return user, profile
