from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.disease_entries import DiagnosisEntry, FamilyHistoryEntry
from app.models.health_profiles import HealthProfile
from app.models.profiles import Profile, ProfileRelation

# [PII/건강정보 분리, 2026-07-29] 이제 Profile엔 순수 개인식별정보만 남는다 - 건강 관련
# 필드(gender/birth_date/is_pregnant/height_cm/weight_kg/special_notes/other_notes)는
# health_profiles로 이관되어 HealthProfileRepository.ALLOWED_UPDATE_FIELDS가 담당한다.
ALLOWED_UPDATE_FIELDS = [
    "name",
    "phone_number",
]


class ProfileRepository:
    async def get_profile(self, session: AsyncSession, profile_id: int) -> Profile | None:
        # [정규화] diagnosis_entries/family_history_entries는 이제 별도 테이블(1:N)이라, 이 profile을
        # 넘겨받는 다른 서비스(채팅 컨텍스트/콘텐츠 개인화/습관 추천 등)가 그 관계를 바로 읽어도
        # 되게 미리 eager load 해둔다 - 안 그러면 비동기 환경에서 lazy load 시도 시 에러가 난다.
        # disease_subtype까지 중첩으로 eager load하는 이유: habit_service의 진단명별 습관 생성이
        # entry.disease_subtype.name을 바로 읽기 때문(T-HOME 습관 2단계).
        # health_profile도 같은 이유로 eager load - `profile.age`/`profile.health_profile.*`를
        # 바로 읽는 도메인(채팅 컨텍스트, 운동 서비스 등)이 lazy load 에러 없이 동작해야 한다.
        result = await session.execute(
            select(Profile)
            .where(Profile.id == profile_id)
            .options(
                selectinload(Profile.health_profile),
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
        *,
        relation: ProfileRelation = ProfileRelation.SELF,
    ) -> Profile:
        """Profile 생성 시 health_profile도 항상 같이 만든다(전부 null이어도) - "모든
        Profile은 health_profile을 갖는다"는 불변식을 유지해서, age 프로퍼티 등 다른
        코드가 None 체크만으로 안전하게 동작하게 한다."""
        profile = Profile(
            user_id=user_id,
            name=name,
            phone_number=phone_number,
            relation=relation,
        )
        profile.health_profile = HealthProfile()
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


class HealthProfileRepository:
    """(2026-07-29 신설) profiles에서 분리된 건강 정보 전용 리포지토리. Profile과 항상
    1:1로 존재한다는 불변식을 전제로 하되, 혹시 모를 예외 상황(과거 데이터 등)을 대비해
    get_or_create로 안전하게 접근한다."""

    ALLOWED_UPDATE_FIELDS = [
        "gender",
        "birth_date",
        "is_pregnant",
        "height_cm",
        "weight_kg",
        "special_notes",
        "other_notes",
    ]

    async def get_or_create_for_profile(self, session: AsyncSession, profile: Profile) -> HealthProfile:
        if profile.health_profile is not None:
            return profile.health_profile
        health_profile = HealthProfile(profile_id=profile.id)
        profile.health_profile = health_profile
        session.add(health_profile)
        await session.flush()
        return health_profile

    async def update_instance(self, session: AsyncSession, health_profile: HealthProfile, data: dict[str, Any]) -> None:
        update_fields = []
        for key, value in data.items():
            if value is not None and key in self.ALLOWED_UPDATE_FIELDS:
                setattr(health_profile, key, value)
                update_fields.append(key)
        if update_fields:
            await session.flush()
