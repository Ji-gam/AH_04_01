from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profiles import Gender, Profile, ProfileRelation

ALLOWED_UPDATE_FIELDS = [
    "name",
    "phone_number",
    "gender",
    "age",
    "height_cm",
    "weight_kg",
    "diagnosis_history",
    "family_history",
    "special_notes",
    "other_notes",
]


class ProfileRepository:
    async def get_profile(self, session: AsyncSession, profile_id: int) -> Profile | None:
        return await session.get(Profile, profile_id)

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
