from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.profiles import Gender, Profile, ProfileRelation

ALLOWED_UPDATE_FIELDS = [
    "name",
    "phone_number",
    "gender",
    "is_pregnant",
    "birth_date",
    "height_cm",
    "weight_kg",
    "special_notes",
    "other_notes",
]


class ProfileRepository:
    async def get_profile(self, session: AsyncSession, profile_id: int) -> Profile | None:
        # [정규화] diagnosis_entries/family_history_entries는 이제 별도 테이블(1:N)이라, 이 profile을
        # 넘겨받는 다른 서비스(채팅 컨텍스트/콘텐츠 개인화 등)가 그 관계를 바로 읽어도 되게 미리
        # eager load 해둔다 - 안 그러면 비동기 환경에서 lazy load 시도 시 에러가 난다.
        result = await session.execute(
            select(Profile)
            .where(Profile.id == profile_id)
            .options(
                selectinload(Profile.diagnosis_entries),
                selectinload(Profile.family_history_entries),
            )
        )
        return result.scalar_one_or_none()

    async def get_default_profile_for_user(self, session: AsyncSession, user_id: int) -> Profile | None:
        result = await session.execute(
            select(Profile).where(Profile.user_id == user_id, Profile.relation == ProfileRelation.SELF)
        )
        return result.scalar_one_or_none()

    async def create_profile(
        self,
        session: AsyncSession,
        user_id: int,
        name: str,
        phone_number: str | None = None,
        gender: Gender | None = None,
        *,
        relation: ProfileRelation = ProfileRelation.SELF,
    ) -> Profile:
        profile = Profile(
            user_id=user_id,
            name=name,
            phone_number=phone_number,
            gender=gender,
            relation=relation,
        )
        session.add(profile)
        await session.flush()
        return profile

    async def exists_by_phone_number(self, session: AsyncSession, phone_number: str) -> bool:
        result = await session.execute(select(Profile).where(Profile.phone_number == phone_number))
        return result.scalar_one_or_none() is not None

    async def update_instance(self, session: AsyncSession, profile: Profile, data: dict[str, Any]) -> None:
        update_fields = []
        for key, value in data.items():
            if value is not None and key in ALLOWED_UPDATE_FIELDS:
                setattr(profile, key, value)
                update_fields.append(key)
        if update_fields:
            await session.flush()
