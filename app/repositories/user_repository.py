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
    ) -> User:
        user = User(email=email, hashed_password=hashed_password, is_active=is_active, is_admin=is_admin)
        session.add(user)
        await session.flush()
        return user

    async def get_user_by_email(self, session: AsyncSession, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def exists_by_email(self, session: AsyncSession, email: str) -> bool:
        return await self.get_user_by_email(session, email) is not None

    async def get_by_sns(self, session: AsyncSession, sns_provider: str, sns_id: str) -> User | None:
        result = await session.execute(select(User).where(User.sns_provider == sns_provider, User.sns_id == sns_id))
        return result.scalar_one_or_none()

    async def create_social_user(
        self,
        session: AsyncSession,
        email: str,
        sns_provider: str,
        sns_id: str,
    ) -> User:
        # 소셜 가입자는 비밀번호가 없다(hashed_password=None) - 본인이 정한 적 없는 값이라 절대 채우지 않는다.
        user = User(email=email, hashed_password=None, sns_provider=sns_provider, sns_id=sns_id)
        session.add(user)
        await session.flush()
        return user

    async def update_last_login(self, session: AsyncSession, user_id: int) -> None:
        user = await self.get_user(session, user_id)
        if user is not None:
            user.last_login = datetime.now(config.TIMEZONE)
            await session.flush()
