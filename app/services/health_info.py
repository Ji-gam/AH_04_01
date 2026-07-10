from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.health_info import HealthInfoUpdateRequest
from app.models.profiles import Profile
from app.repositories.profile_repository import ProfileRepository


class HealthInfoService:
    """더보기 > 개인건강정보. 회원가입 흐름과 분리된 별도 도메인이지만, [변경] 가입 시 나이/성별을 안 받게
    되면서 이 화면이 나이/성별을 처음 입력받는 곳이 됐다 - 그래서 age/gender도 여기서 수정 가능하다."""

    def __init__(self):
        self.profile_repo = ProfileRepository()

    async def update_health_info(
        self, session: AsyncSession, profile: Profile, data: HealthInfoUpdateRequest
    ) -> Profile:
        fields = data.model_dump(exclude_none=True)

        # DiseaseEntry(disease: StrEnum, detail: str|None) 리스트를 JSON 컬럼에 저장 가능한 plain dict 리스트로 변환한다.
        # (dict 멤버십이 아니라 data.xxx is not None으로 직접 좁혀야 mypy가 None을 배제한다.)
        if data.diagnosis_history is not None:
            fields["diagnosis_history"] = [
                {"disease": entry.disease.value, "detail": entry.detail} for entry in data.diagnosis_history
            ]
        if data.family_history is not None:
            fields["family_history"] = [
                {"disease": entry.disease.value, "detail": entry.detail} for entry in data.family_history
            ]

        await self.profile_repo.update_instance(session, profile, fields)
        await session.commit()
        return profile
