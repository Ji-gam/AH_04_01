from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.health_info import HealthInfoUpdateRequest
from app.models.disease_entries import DiagnosisEntry, FamilyHistoryEntry
from app.models.profiles import Profile
from app.repositories.disease_entry_repository import (
    DiagnosisEntryRepository,
    DiseaseSubtypeRepository,
    FamilyHistoryEntryRepository,
)
from app.repositories.profile_repository import ProfileRepository


class HealthInfoService:
    """더보기 > 개인건강정보. 회원가입 흐름과 분리된 별도 도메인이지만, [변경] 가입 시 나이/성별을 안 받게
    되면서 이 화면이 나이/성별을 처음 입력받는 곳이 됐다 - 그래서 birth_date/gender도 여기서 수정 가능하다.

    [정규화] 진단병력/가족력은 더 이상 JSON 컬럼이 아니라 diagnosis_entries/family_history_entries
    테이블에 저장한다. 구체적 질환명(disease_subtype)은 disease_subtypes 매핑테이블에서
    검색/자동생성(get_or_create)해서 실제 FK로 연결한다 - 원티드 스킬태그 검색과 같은 방식.

    [재설계] 나이는 저장하지 않는다 - birth_date만 저장하고, 나이는 항상 그로부터 자동 계산된다
    (Profile.age 프로퍼티 참고). 그래서 여기서 "나이 입력 시점"을 따로 추적할 필요가 없어졌다."""

    def __init__(self):
        self.profile_repo = ProfileRepository()
        self.subtype_repo = DiseaseSubtypeRepository()
        self.diagnosis_repo = DiagnosisEntryRepository()
        self.family_repo = FamilyHistoryEntryRepository()

    async def update_health_info(
        self, session: AsyncSession, profile: Profile, data: HealthInfoUpdateRequest
    ) -> Profile:
        fields = data.model_dump(exclude_none=True, exclude={"diagnosis_history", "family_history"})

        await self.profile_repo.update_instance(session, profile, fields)

        if data.diagnosis_history is not None:
            diagnosis_rows: list[DiagnosisEntry] = []
            for entry in data.diagnosis_history:
                subtype = None
                if entry.disease_subtype:
                    subtype = await self.subtype_repo.get_or_create(session, entry.disease, entry.disease_subtype)
                diagnosis_rows.append(
                    DiagnosisEntry(
                        disease=entry.disease,
                        disease_subtype_id=subtype.id if subtype else None,
                        diagnosed_years_ago=entry.diagnosed_years_ago,
                        status=entry.status,
                        on_medication=entry.on_medication,
                        detail=entry.detail,
                    )
                )
            await self.diagnosis_repo.replace_all_for_profile(session, profile.id, diagnosis_rows)

        if data.family_history is not None:
            family_rows: list[FamilyHistoryEntry] = []
            for family_entry in data.family_history:
                subtype = None
                if family_entry.disease_subtype:
                    subtype = await self.subtype_repo.get_or_create(
                        session, family_entry.disease, family_entry.disease_subtype
                    )
                family_rows.append(
                    FamilyHistoryEntry(
                        disease=family_entry.disease,
                        disease_subtype_id=subtype.id if subtype else None,
                        relation=family_entry.relation,
                        detail=family_entry.detail,
                    )
                )
            await self.family_repo.replace_all_for_profile(session, profile.id, family_rows)

        await session.commit()
        return profile
