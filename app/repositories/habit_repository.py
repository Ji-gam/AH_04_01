from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.habit_logs import HabitLog
from app.models.habit_selections import HabitSelection
from app.models.habit_subtype_suggestions import HabitSubtypeSuggestion


class HabitRepository:
    async def get_subtype_suggestion(
        self, session: AsyncSession, disease_subtype_id: int
    ) -> HabitSubtypeSuggestion | None:
        result = await session.execute(
            select(HabitSubtypeSuggestion).where(HabitSubtypeSuggestion.disease_subtype_id == disease_subtype_id)
        )
        return result.scalar_one_or_none()

    async def save_subtype_suggestion(
        self,
        session: AsyncSession,
        disease_subtype_id: int,
        label: str,
        icon: str,
        unit: str,
        target: int,
    ) -> HabitSubtypeSuggestion:
        suggestion = HabitSubtypeSuggestion(
            disease_subtype_id=disease_subtype_id, label=label, icon=icon, unit=unit, target=target
        )
        session.add(suggestion)
        await session.commit()
        await session.refresh(suggestion)
        return suggestion

    async def list_selected_keys(self, session: AsyncSession, profile_id: int, select_date: date) -> list[str]:
        result = await session.execute(
            select(HabitSelection.habit_key).where(
                HabitSelection.profile_id == profile_id, HabitSelection.select_date == select_date
            )
        )
        return list(result.scalars().all())

    async def replace_selection(
        self, session: AsyncSession, profile_id: int, select_date: date, habit_keys: list[str]
    ) -> None:
        """오늘 선택을 통째로 교체한다(다시 고르면 이전 선택은 사라짐) - 몇 개를 고르든(0개 포함)
        그대로 반영되는 게 의도라, 증분 추가/삭제가 아니라 전체 삭제 후 재삽입이 제일 단순하다."""
        await session.execute(
            delete(HabitSelection).where(
                HabitSelection.profile_id == profile_id, HabitSelection.select_date == select_date
            )
        )
        for key in habit_keys:
            session.add(HabitSelection(profile_id=profile_id, select_date=select_date, habit_key=key))
        await session.commit()

    async def list_logs_for_date(self, session: AsyncSession, profile_id: int, log_date: date) -> list[HabitLog]:
        result = await session.execute(
            select(HabitLog).where(HabitLog.profile_id == profile_id, HabitLog.log_date == log_date)
        )
        return list(result.scalars().all())

    async def get_log(self, session: AsyncSession, profile_id: int, log_date: date, habit_key: str) -> HabitLog | None:
        result = await session.execute(
            select(HabitLog).where(
                HabitLog.profile_id == profile_id,
                HabitLog.log_date == log_date,
                HabitLog.habit_key == habit_key,
            )
        )
        return result.scalar_one_or_none()

    async def increment_progress(
        self, session: AsyncSession, profile_id: int, log_date: date, habit_key: str, cap: int
    ) -> HabitLog:
        log = await self.get_log(session, profile_id, log_date, habit_key)
        if log is None:
            log = HabitLog(profile_id=profile_id, log_date=log_date, habit_key=habit_key, progress=0)
            session.add(log)
        log.progress = min(log.progress + 1, cap)
        await session.commit()
        await session.refresh(log)
        return log
