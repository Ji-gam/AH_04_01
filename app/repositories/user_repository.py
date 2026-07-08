from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.users import User


class UserRepository:
    async def get_user(self, session: AsyncSession, user_id: int) -> User | None:
        return await session.get(User, user_id)

    async def create_user(
        self,
        session: AsyncSession,
        email: str,
        hashed_password: str,
        *,
        is_active: bool = True,
        is_admin: bool = False,
        service_terms_agreed_at: datetime | None = None,
        privacy_agreed_at: datetime | None = None,
        sensitive_info_agreed_at: datetime | None = None,
        marketing_agreed_at: datetime | None = None,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            is_active=is_active,
            is_admin=is_admin,
            service_terms_agreed_at=service_terms_agreed_at,
            privacy_agreed_at=privacy_agreed_at,
            sensitive_info_agreed_at=sensitive_info_agreed_at,
            marketing_agreed_at=marketing_agreed_at,
        )
        session.add(user)
        await session.flush()
        return user

    async def get_user_by_email(self, session: AsyncSession, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def exists_by_email(self, session: AsyncSession, email: str) -> bool:
        return await self.get_user_by_email(session, email) is not None

    async def update_last_login(self, session: AsyncSession, user_id: int) -> None:
        user = await self.get_user(session, user_id)
        if user is not None:
            user.last_login = datetime.now(config.TIMEZONE)
            await session.flush()

    # [T-AUTH-3 로그아웃/Refresh Token 검증]
    async def update_refresh_token(self, session: AsyncSession, user_id: int, refresh_token: str | None) -> None:
        user = await self.get_user(session, user_id)
        if user is not None:
            user.refresh_token = refresh_token
            await session.flush()

    async def get_by_valid_refresh_token(self, session: AsyncSession, user_id: int, refresh_token: str) -> User | None:
        """DB에 저장된 refresh_token과 넘어온 값이 정확히 일치할 때만 사용자를 반환한다.
        로그아웃했거나(값이 null) 다른 값으로 이미 대체된 토큰은 여기서 걸러진다."""
        result = await session.execute(select(User).where(User.id == user_id, User.refresh_token == refresh_token))
        return result.scalar_one_or_none()

    # [소셜로그인 추가]
    async def get_by_sns(self, session: AsyncSession, provider: str, sns_id: str) -> User | None:
        result = await session.execute(select(User).where(User.sns_provider == provider, User.sns_id == sns_id))
        return result.scalar_one_or_none()

    async def link_sns_to_existing_user(self, session: AsyncSession, user: User, provider: str, sns_id: str) -> None:
        user.sns_provider = provider
        user.sns_id = sns_id
        await session.flush()

    async def create_social_user(
        self,
        session: AsyncSession,
        email: str,
        hashed_password: str,
        provider: str,
        sns_id: str,
        *,
        service_terms_agreed_at: datetime | None = None,
        privacy_agreed_at: datetime | None = None,
        sensitive_info_agreed_at: datetime | None = None,
        marketing_agreed_at: datetime | None = None,
    ) -> User:
        # hashed_password는 본인만 아는 값이 아니라 사용 불가능한 임의 문자열을 해시한 것 (컬럼이 NOT NULL이라 채워야 함)
        user = User(
            email=email,
            hashed_password=hashed_password,
            sns_provider=provider,
            sns_id=sns_id,
            service_terms_agreed_at=service_terms_agreed_at,
            privacy_agreed_at=privacy_agreed_at,
            sensitive_info_agreed_at=sensitive_info_agreed_at,
            marketing_agreed_at=marketing_agreed_at,
        )
        session.add(user)
        await session.flush()
        return user
