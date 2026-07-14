from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.disease_entries import DiagnosisEntry, DiseaseSubtype, FamilyHistoryEntry
from app.models.profiles import Disease


class DiseaseSubtypeRepository:
    """구체적 질환명 매핑테이블. 원티드 스킬태그처럼 "검색해서 있으면 선택, 없으면 새로 추가"
    방식이라, 매번 get_or_create로 다룬다 - 그래야 같은 이름이 중복 생성되지 않는다."""

    async def search(
        self, session: AsyncSession, category: Disease, query: str, limit: int = 10
    ) -> list[DiseaseSubtype]:
        """자동완성 검색용. query가 이름에 포함되는 항목을 찾는다(대소문자 무관은 MySQL 기본 collation이 처리)."""
        stmt = (
            select(DiseaseSubtype)
            .where(DiseaseSubtype.category == category, DiseaseSubtype.name.contains(query))
            .order_by(DiseaseSubtype.is_custom, DiseaseSubtype.name)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create(self, session: AsyncSession, category: Disease, name: str) -> DiseaseSubtype:
        name = name.strip()
        result = await session.execute(
            select(DiseaseSubtype).where(DiseaseSubtype.category == category, DiseaseSubtype.name == name)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        # 목록에 없던 이름 - 새로 추가한다(is_custom=True). 이러면 다음 사람이 같은 이름을 검색할 때
        # 이번엔 기존 항목으로 잡혀서, 매핑테이블이 시간이 지나며 자라나는 구조가 된다.
        subtype = DiseaseSubtype(category=category, name=name, is_custom=True)
        session.add(subtype)
        await session.flush()
        return subtype


class DiagnosisEntryRepository:
    async def replace_all_for_profile(
        self, session: AsyncSession, profile_id: int, entries: list[DiagnosisEntry]
    ) -> None:
        """수정 화면은 항상 "지금 선택된 것 전체"를 통째로 보내므로, 기존 항목을 전부 지우고
        새로 넣는 방식이 제일 단순하고 안전하다(부분 diff 계산 없이 항상 최종 상태와 일치)."""
        await session.execute(
            DiagnosisEntry.__table__.delete().where(DiagnosisEntry.profile_id == profile_id)  # type: ignore[attr-defined]
        )
        for entry in entries:
            entry.profile_id = profile_id
            session.add(entry)
        await session.flush()

    async def list_for_profile(self, session: AsyncSession, profile_id: int) -> list[DiagnosisEntry]:
        result = await session.execute(
            select(DiagnosisEntry)
            .where(DiagnosisEntry.profile_id == profile_id)
            .options(selectinload(DiagnosisEntry.disease_subtype))
        )
        return list(result.scalars().all())


class FamilyHistoryEntryRepository:
    async def replace_all_for_profile(
        self, session: AsyncSession, profile_id: int, entries: list[FamilyHistoryEntry]
    ) -> None:
        await session.execute(
            FamilyHistoryEntry.__table__.delete().where(  # type: ignore[attr-defined]
                FamilyHistoryEntry.profile_id == profile_id
            )
        )
        for entry in entries:
            entry.profile_id = profile_id
            session.add(entry)
        await session.flush()

    async def list_for_profile(self, session: AsyncSession, profile_id: int) -> list[FamilyHistoryEntry]:
        result = await session.execute(
            select(FamilyHistoryEntry)
            .where(FamilyHistoryEntry.profile_id == profile_id)
            .options(selectinload(FamilyHistoryEntry.disease_subtype))
        )
        return list(result.scalars().all())
