from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goals import Goal, GoalType


class GoalRepository:
    async def create(
        self,
        session: AsyncSession,
        profile_id: int,
        title: str,
        goal_type: GoalType,
        start_value: Decimal | None,
        target_value: Decimal | None,
        current_value: Decimal | None,
        unit: str | None,
        start_date: date,
        end_date: date,
    ) -> Goal:
        goal = Goal(
            profile_id=profile_id,
            title=title,
            goal_type=goal_type,
            start_value=start_value,
            target_value=target_value,
            current_value=current_value,
            unit=unit,
            start_date=start_date,
            end_date=end_date,
        )
        session.add(goal)
        await session.commit()
        await session.refresh(goal)
        return goal

    async def get_by_id_and_profile(self, session: AsyncSession, profile_id: int, goal_id: int) -> Goal | None:
        result = await session.execute(select(Goal).where(Goal.id == goal_id, Goal.profile_id == profile_id))
        return result.scalar_one_or_none()

    async def list_for_profile(self, session: AsyncSession, profile_id: int) -> list[Goal]:
        result = await session.execute(select(Goal).where(Goal.profile_id == profile_id).order_by(Goal.end_date.asc()))
        return list(result.scalars().all())

    async def list_profile_ids_with_goals(self, session: AsyncSession) -> list[int]:
        """F-GOAL-3(주간/월간 리포트) 발송 대상 선정용 - 목표를 하나라도 등록한 프로필.
        기간 무관하게 전부 대상으로 한다(목표 진행률은 스냅샷이라 "이 기간에 생겼는지"가
        중요하지 않다)."""
        result = await session.execute(select(Goal.profile_id).distinct())
        return list(result.scalars().all())

    async def save_guide(self, session: AsyncSession, goal: Goal, guide_content: str, generated_at: datetime) -> Goal:
        goal.guide_content = guide_content
        goal.guide_generated_at = generated_at
        await session.commit()
        await session.refresh(goal)
        return goal

    async def delete(self, session: AsyncSession, profile_id: int, goal_id: int) -> bool:
        goal = await self.get_by_id_and_profile(session, profile_id, goal_id)
        if goal is None:
            return False
        await session.delete(goal)
        await session.commit()
        return True
