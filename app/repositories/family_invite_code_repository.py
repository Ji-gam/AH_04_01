from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_invite_code import (
    FamilyInviteCode,
    default_expiry,
    generate_invite_code,
)


class FamilyInviteCodeRepository:
    async def create(self, session: AsyncSession, guardian_profile_id: int, relation_label: str) -> FamilyInviteCode:
        """코드 충돌(극히 낮은 확률이지만 unique 제약이 있음)이 나면 재생성해서 재시도한다."""
        now = datetime.now().astimezone()
        for _ in range(5):
            code = generate_invite_code()
            existing = await self.get_by_code(session, code)
            if existing is not None:
                continue
            invite = FamilyInviteCode(
                guardian_profile_id=guardian_profile_id,
                code=code,
                relation_label=relation_label,
                expires_at=default_expiry(now),
            )
            session.add(invite)
            await session.commit()
            await session.refresh(invite)
            return invite
        raise RuntimeError("초대코드 생성에 반복 실패했습니다 (충돌 재시도 초과)")

    async def get_by_code(self, session: AsyncSession, code: str) -> FamilyInviteCode | None:
        result = await session.execute(select(FamilyInviteCode).where(FamilyInviteCode.code == code))
        return result.scalar_one_or_none()

    async def mark_used(self, session: AsyncSession, invite: FamilyInviteCode) -> None:
        invite.used_at = datetime.now().astimezone()
        await session.commit()
