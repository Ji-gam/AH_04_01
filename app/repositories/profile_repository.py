from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.disease_entries import DiagnosisEntry, FamilyHistoryEntry
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
        # 넘겨받는 다른 서비스(채팅 컨텍스트/콘텐츠 개인화/습관 추천 등)가 그 관계를 바로 읽어도
        # 되게 미리 eager load 해둔다 - 안 그러면 비동기 환경에서 lazy load 시도 시 에러가 난다.
        # disease_subtype까지 중첩으로 eager load하는 이유: habit_service의 진단명별 습관 생성이
        # entry.disease_subtype.name을 바로 읽기 때문(T-HOME 습관 2단계).
        result = await session.execute(
            select(Profile)
            .where(Profile.id == profile_id)
            .options(
                selectinload(Profile.diagnosis_entries).selectinload(DiagnosisEntry.disease_subtype),
                selectinload(Profile.family_history_entries).selectinload(FamilyHistoryEntry.disease_subtype),
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

    async def set_guardian_document_access(self, session: AsyncSession, profile: Profile, allow: bool) -> None:
        """(REQ-DOC-003) 가족(보호자) 문서함 이미지 공개 여부 토글. 처방전/진료기록 원본
        이미지는 다른 개인건강정보 필드보다 훨씬 민감해서, 범용 update_instance/
        ALLOWED_UPDATE_FIELDS 경로(HealthInfoUpdateRequest 등 다른 필드와 함께 묶여 실수로
        바뀌는 것을 피하기 위해)와는 별도로 전용 메서드로 분리한다."""
        profile.allow_guardian_document_access = allow
        await session.commit()
        await session.refresh(profile)

    async def update_instance(self, session: AsyncSession, profile: Profile, data: dict[str, Any]) -> None:
        update_fields = []
        for key, value in data.items():
            if value is not None and key in ALLOWED_UPDATE_FIELDS:
                setattr(profile, key, value)
                update_fields.append(key)
        if update_fields:
            await session.flush()
