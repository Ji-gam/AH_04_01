from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models.goal_progress_logs import GoalProgressLog
from app.models.goals import GoalType
from app.models.profiles import Gender, ProfileRelation
from app.repositories.goal_progress_log_repository import GoalProgressLogRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.tests.conftest import TestSessionLocal


async def _create_profile(session, email: str) -> int:
    user = await UserRepository().create_user(session, email=email, hashed_password="hashed")
    profile = await ProfileRepository().create_profile(
        session, user_id=user.id, name="테스터", gender=Gender.MALE, relation=ProfileRelation.SELF
    )
    return profile.id


async def test_delete_goal_cascades_progress_logs():
    """목표를 지우면 그 목표에 딸린 일일 기록(goal_progress_logs)도 DB에서 함께 지워져야
    한다(FK ondelete='CASCADE') - 삭제 후 고아 기록이 남으면 안 된다."""
    goal_repo = GoalRepository()
    log_repo = GoalProgressLogRepository()
    async with TestSessionLocal() as session:
        profile_id = await _create_profile(session, "goal_repo_cascade@example.com")
        goal = await goal_repo.create(
            session,
            profile_id,
            title="캐스케이드 확인용",
            goal_type=GoalType.NUMERIC,
            start_value=None,
            target_value=None,
            current_value=None,
            unit=None,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 20),
        )
        await log_repo.upsert(session, goal.id, date(2026, 7, 2), value=Decimal("1"))

        deleted = await goal_repo.delete(session, profile_id, goal.id)

        remaining = await session.execute(select(GoalProgressLog).where(GoalProgressLog.goal_id == goal.id))

    assert deleted is True
    assert remaining.scalars().all() == []


async def test_list_for_profile_orders_by_end_date_ascending():
    """목표 목록은 종료일이 임박한 순으로 정렬돼야 한다(늦게 만들어도 마감이 가까우면 먼저)."""
    goal_repo = GoalRepository()
    async with TestSessionLocal() as session:
        profile_id = await _create_profile(session, "goal_repo_order@example.com")
        await goal_repo.create(
            session,
            profile_id,
            title="늦게 끝남",
            goal_type=GoalType.NUMERIC,
            start_value=None,
            target_value=None,
            current_value=None,
            unit=None,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 12, 31),
        )
        await goal_repo.create(
            session,
            profile_id,
            title="빨리 끝남",
            goal_type=GoalType.NUMERIC,
            start_value=None,
            target_value=None,
            current_value=None,
            unit=None,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
        )

        goals = await goal_repo.list_for_profile(session, profile_id)

    assert [g.title for g in goals] == ["빨리 끝남", "늦게 끝남"]
