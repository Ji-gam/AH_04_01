from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.diary_dto import (
    DiaryEntryItemResult,
    DiaryEntryListResult,
    DiaryEntrySaveRequest,
    DiaryTodayResult,
)
from app.models.diary_entries import DiaryEntry
from app.models.profiles import Profile
from app.repositories.diary_repository import DiaryRepository


def _to_item_result(entry: DiaryEntry) -> DiaryEntryItemResult:
    return DiaryEntryItemResult(
        id=entry.id,
        entry_date=entry.entry_date,
        content=entry.content,
        image_base64=entry.image_base64,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


class DiaryService:
    def __init__(self, repository: DiaryRepository | None = None) -> None:
        self._repository = repository or DiaryRepository()

    async def get_today(self, session: AsyncSession, profile: Profile) -> DiaryTodayResult:
        entry = await self._repository.get_by_date(session, profile.id, date.today())
        return DiaryTodayResult(entry=_to_item_result(entry) if entry is not None else None)

    async def save_today(
        self, session: AsyncSession, profile: Profile, request: DiaryEntrySaveRequest
    ) -> DiaryEntryItemResult:
        entry = await self._repository.upsert(session, profile.id, date.today(), request.content, request.image_base64)
        return _to_item_result(entry)

    async def list_entries(self, session: AsyncSession, profile: Profile) -> DiaryEntryListResult:
        entries = await self._repository.list_for_profile(session, profile.id)
        return DiaryEntryListResult(entries=[_to_item_result(e) for e in entries])
