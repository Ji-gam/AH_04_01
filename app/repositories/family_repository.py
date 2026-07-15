from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_link import FamilyLink, FamilyLinkStatus


class FamilyRepository:
    async def create_link(
        self, session: AsyncSession, guardian_profile_id: int, member_profile_id: int, relation_label: str
    ) -> FamilyLink:
        """항상 PENDING(대기중) 상태로 생성한다 - 상대방이 수락해야 ACCEPTED가 된다."""
        link = FamilyLink(
            guardian_profile_id=guardian_profile_id,
            member_profile_id=member_profile_id,
            relation_label=relation_label,
            status=FamilyLinkStatus.PENDING,
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link

    async def get_link(self, session: AsyncSession, guardian_profile_id: int, member_profile_id: int) -> FamilyLink | None:
        result = await session.execute(
            select(FamilyLink).where(
                FamilyLink.guardian_profile_id == guardian_profile_id,
                FamilyLink.member_profile_id == member_profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_link_by_id(self, session: AsyncSession, link_id: int) -> FamilyLink | None:
        result = await session.execute(select(FamilyLink).where(FamilyLink.id == link_id))
        return result.scalar_one_or_none()

    async def list_as_guardian(
        self, session: AsyncSession, guardian_profile_id: int, status: FamilyLinkStatus | None = None
    ) -> list[FamilyLink]:
        """내가 보호자로서 보낸 연결 요청 목록 (status 지정 시 그 상태만)."""
        query = select(FamilyLink).where(FamilyLink.guardian_profile_id == guardian_profile_id)
        if status is not None:
            query = query.where(FamilyLink.status == status)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_as_member(
        self, session: AsyncSession, member_profile_id: int, status: FamilyLinkStatus | None = None
    ) -> list[FamilyLink]:
        """내가 피보호자로서 받은 연결 요청 목록 (status 지정 시 그 상태만)."""
        query = select(FamilyLink).where(FamilyLink.member_profile_id == member_profile_id)
        if status is not None:
            query = query.where(FamilyLink.status == status)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def is_guardian_of(self, session: AsyncSession, guardian_profile_id: int, member_profile_id: int) -> bool:
        """본인 명의는 항상 허용. 남의 프로필은 ACCEPTED 상태의 연결이 있어야만 허용 -
        PENDING(아직 상대방이 수락 안 함) 상태로는 어떤 권한도 생기지 않는다."""
        if guardian_profile_id == member_profile_id:
            return True
        link = await self.get_link(session, guardian_profile_id, member_profile_id)
        return link is not None and link.status == FamilyLinkStatus.ACCEPTED

    async def accept(self, session: AsyncSession, link: FamilyLink) -> FamilyLink:
        link.status = FamilyLinkStatus.ACCEPTED
        await session.commit()
        await session.refresh(link)
        return link

    async def delete_link(self, session: AsyncSession, link: FamilyLink) -> None:
        """연결 해제(보호자 쪽 취소)와 요청 거절(피보호자 쪽 거절) 둘 다 이 메서드로 처리한다 -
        거절된 요청을 남겨두면 uq_family_links_pair 제약 때문에 재요청이 막히므로, 거절 시
        row 자체를 지워서 나중에 다시 요청할 수 있게 한다."""
        result = await session.execute(select(FamilyLink).where(FamilyLink.id == link.id))
        obj = result.scalar_one_or_none()
        if obj is not None:
            await session.delete(obj)
            await session.commit()
