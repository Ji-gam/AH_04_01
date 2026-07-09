from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.health_info import HealthInfoUpdateRequest
from app.models.profiles import Profile
from app.repositories.profile_repository import ProfileRepository


class HealthInfoService:
    """더보기 > 개인건강정보. 회원가입 흐름과 완전히 분리된 별도 도메인이다.
    생년월일/성별은 이미 Profile에 있는 필드를 조회에만 포함시킨다(수정은 여기서 안 하고 PATCH /users/me에서 한다)."""

    def __init__(self):
        self.profile_repo = ProfileRepository()

    async def update_health_info(
        self, session: AsyncSession, profile: Profile, data: HealthInfoUpdateRequest
    ) -> Profile:
        fields = data.model_dump(exclude_none=True)

        # StrEnum 리스트는 순수 str 리스트로 변환해서 JSON 컬럼에 저장한다.
        if "diagnosis_history" in fields:
            fields["diagnosis_history"] = [d.value for d in data.diagnosis_history]
        if "family_history" in fields:
            fields["family_history"] = [d.value for d in data.family_history]

        await self.profile_repo.update_instance(session, profile, fields)
        await session.commit()
        return profile
