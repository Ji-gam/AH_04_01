from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.medication_intake import IntakeDailyCountResult, IntakeRecordResult
from app.repositories.medication_intake_repository import MedicationIntakeRepository


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


class MedicationIntakeService:
    """복약 체크(F-ADH-1)를 서버에 기록한다. 예전엔 프론트가 localStorage에만 저장해서
    기기를 바꾸면 기록이 날아갔다 - 이 서비스가 그 자리를 대신한다."""

    def __init__(self) -> None:
        self._repo = MedicationIntakeRepository()

    async def toggle(
        self,
        session: AsyncSession,
        profile_id: int,
        source_type: str,
        source_id: int,
        scheduled_time: str,
        date_str: str,
        checked: bool,
    ) -> None:
        intake_date = _parse_date(date_str)
        existing = await self._repo.get_one(session, profile_id, source_type, source_id, scheduled_time, intake_date)
        if checked:
            if existing is None:
                await self._repo.create(session, profile_id, source_type, source_id, scheduled_time, intake_date)
            return
        if existing is not None:
            await self._repo.delete(session, existing)

    async def list_for_date(self, session: AsyncSession, profile_id: int, date_str: str) -> list[IntakeRecordResult]:
        logs = await self._repo.list_for_date(session, profile_id, _parse_date(date_str))
        return [
            IntakeRecordResult(source_type=log.source_type, source_id=log.source_id, scheduled_time=log.scheduled_time)
            for log in logs
        ]

    async def daily_counts(
        self, session: AsyncSession, profile_id: int, start_str: str, end_str: str
    ) -> list[IntakeDailyCountResult]:
        """[start, end] 구간(포함) 전체 날짜에 대해, 기록이 없는 날도 0건으로 채워 반환한다 -
        프론트가 히트맵을 그릴 때 "이 날짜는 응답에 없음"과 "0건"을 구분할 필요 없게 한다."""
        start_date, end_date = _parse_date(start_str), _parse_date(end_str)
        counts = await self._repo.count_by_date_for_range(session, profile_id, start_date, end_date)

        results = []
        current = start_date
        while current <= end_date:
            results.append(IntakeDailyCountResult(date=current.isoformat(), checked_count=counts.get(current, 0)))
            current += timedelta(days=1)
        return results
