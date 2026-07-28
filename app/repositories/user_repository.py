from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.admin_action import AdminAction
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

    async def list_users(self, session: AsyncSession, search: str | None = None, limit: int = 50) -> list[User]:
        """(관리자 화면) 이메일 부분일치 검색 + 최신 가입순. limit 기본 50 - 이 화면은
        전체 유저를 한 번에 다 보여주는 용도가 아니라, 승격 대상을 검색해서 찾는 용도라
        무제한 조회를 막아둔다."""
        stmt = select(User).order_by(User.created_at.desc()).limit(limit)
        if search:
            stmt = stmt.where(User.email.ilike(f"%{search}%"))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def set_admin(self, session: AsyncSession, user_id: int, is_admin: bool) -> User | None:
        user = await self.get_user(session, user_id)
        if user is None:
            return None
        user.is_admin = is_admin
        await session.flush()
        return user

    async def count_all(self, session: AsyncSession) -> int:
        result = await session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def count_admins(self, session: AsyncSession) -> int:
        result = await session.execute(select(func.count()).select_from(User).where(User.is_admin.is_(True)))
        return result.scalar_one()

    async def count_consented(self, session: AsyncSession, column) -> int:  # noqa: ANN001
        """4개 동의 컬럼 전부 같은 방식(null이 아니면 동의함)이라 컬럼만 바꿔 재사용한다."""
        result = await session.execute(select(func.count()).select_from(User).where(column.is_not(None)))
        return result.scalar_one()

    async def signup_trend(self, session: AsyncSession, days: int = 7) -> list[tuple[str, int]]:
        """(관리자 대시보드) 최근 N일간 하루 단위 가입자 수. 가입자가 없는 날짜도
        0으로 채워서 그래프 x축이 끊기지 않게 한다."""
        since = datetime.now(tz=config.TIMEZONE) - timedelta(days=days - 1)
        day_col = func.date(User.created_at)
        stmt = (
            select(day_col.label("day"), func.count().label("cnt"))
            .where(User.created_at >= since)
            .group_by(day_col)
        )
        result = await session.execute(stmt)
        counts_by_day = {str(row.day): row.cnt for row in result.all()}

        trend: list[tuple[str, int]] = []
        for i in range(days):
            day = (since + timedelta(days=i)).date()
            trend.append((str(day), counts_by_day.get(str(day), 0)))
        return trend


class AdminActionRepository:
    """관리자 화면 행위(권한 변경, 공지 발송) 감사로그. list_users처럼 무제한 조회를
    막기 위해 limit 기본값을 둔다."""

    async def log(
        self, session: AsyncSession, *, actor_user_id: int, action: str, target: str | None, detail: str | None
    ) -> AdminAction:
        record = AdminAction(actor_user_id=actor_user_id, action=action, target=target, detail=detail)
        session.add(record)
        await session.flush()
        return record

    async def list_recent(self, session: AsyncSession, limit: int = 100) -> list[AdminAction]:
        stmt = select(AdminAction).order_by(AdminAction.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())
