from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.issued_refresh_token import IssuedRefreshToken


class RefreshTokenRepository:
    async def create(self, session: AsyncSession, user_id: int, jti: str) -> None:
        session.add(IssuedRefreshToken(user_id=user_id, jti=jti, is_revoked=False))

    async def get_by_jti(self, session: AsyncSession, jti: str) -> IssuedRefreshToken | None:
        result = await session.execute(select(IssuedRefreshToken).where(IssuedRefreshToken.jti == jti))
        return result.scalar_one_or_none()

    async def revoke(self, session: AsyncSession, jti: str) -> None:
        await session.execute(update(IssuedRefreshToken).where(IssuedRefreshToken.jti == jti).values(is_revoked=True))

    async def revoke_all_for_user(self, session: AsyncSession, user_id: int) -> None:
        """재사용 탐지(탈취 의심) 시, 그 계정의 모든 세션을 강제 로그아웃시키기 위해 호출한다."""
        await session.execute(
            update(IssuedRefreshToken).where(IssuedRefreshToken.user_id == user_id).values(is_revoked=True)
        )
