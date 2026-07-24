from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diary_entries import DiaryEntry


class DiaryRepository:
    async def get_by_date(self, session: AsyncSession, profile_id: int, entry_date: date) -> DiaryEntry | None:
        result = await session.execute(
            select(DiaryEntry).where(DiaryEntry.profile_id == profile_id, DiaryEntry.entry_date == entry_date)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        session: AsyncSession,
        profile_id: int,
        entry_date: date,
        content: str,
        image_base64: str | None = None,
    ) -> DiaryEntry:
        """하루 한 건 - 이미 그날 기록이 있으면 내용을 덮어쓰고, 없으면 새로 만든다."""
        existing = await self.get_by_date(session, profile_id, entry_date)
        if existing is not None:
            existing.content = content
            existing.image_base64 = image_base64
            await session.commit()
            await session.refresh(existing)
            return existing

        entry = DiaryEntry(profile_id=profile_id, entry_date=entry_date, content=content, image_base64=image_base64)
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry

    async def list_for_profile(self, session: AsyncSession, profile_id: int) -> list[DiaryEntry]:
        result = await session.execute(
            select(DiaryEntry).where(DiaryEntry.profile_id == profile_id).order_by(DiaryEntry.entry_date.desc())
        )
        return list(result.scalars().all())
