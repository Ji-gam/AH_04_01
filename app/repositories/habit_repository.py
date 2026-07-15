from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.habit_logs import HabitLog
from app.models.habit_selections import HabitSelection
from app.models.habit_subtype_suggestions import HabitSubtypeSuggestion


class HabitRepository:
    async def list_subtype_suggestions(
        self, session: AsyncSession, disease_subtype_id: int
    ) -> list[HabitSubtypeSuggestion]:
        result = await session.execute(
            select(HabitSubtypeSuggestion)
            .where(HabitSubtypeSuggestion.disease_subtype_id == disease_subtype_id)
            .order_by(HabitSubtypeSuggestion.slot)
        )
        return list(result.scalars().all())

    async def save_subtype_suggestions(
        self,
        session: AsyncSession,
        disease_subtype_id: int,
        suggestions: list[dict],
    ) -> list[HabitSubtypeSuggestion]:
        """한 진단명에 대해 생성된 습관 여러 개(slot 0부터)를 한 번에 저장한다."""
        rows = [
            HabitSubtypeSuggestion(disease_subtype_id=disease_subtype_id, slot=slot, **suggestion)
            for slot, suggestion in enumerate(suggestions)
        ]
        session.add_all(rows)
        await session.commit()
        for row in rows:
            await session.refresh(row)
        return rows

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
