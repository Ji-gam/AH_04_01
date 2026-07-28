from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.sleep_dto import (
    SleepLogCreateRequest,
    SleepLogResult,
    SleepRecentDayResult,
    SleepRecentResult,
    SleepTodayResult,
)
from app.models.profiles import Profile
from app.repositories.sleep_repository import SleepRepository

# 목표 수면시간 개인화 필드가 아직 없어서, diet_service.py의 DIET_REFERENCE_KCAL과 같은
# 방식으로 일반 권장 수면시간(성인 기준)으로 비교한다.
SLEEP_REFERENCE_HOURS = 8


def _to_result(log) -> SleepLogResult:
    return SleepLogResult(
        log_date=log.log_date, hours=float(log.hours), bed_time=log.bed_time, quality=log.quality, reason=log.reason
    )


class SleepService:
    def __init__(self, repository: SleepRepository | None = None) -> None:
        self._repository = repository or SleepRepository()

    async def log_sleep(
        self, session: AsyncSession, profile: Profile, request: SleepLogCreateRequest
    ) -> SleepTodayResult:
        await self._repository.upsert_log(
            session,
            profile_id=profile.id,
            log_date=date.today(),
            hours=request.hours,
            bed_time=request.bed_time,
            quality=request.quality,
            reason=request.reason,
        )
        return await self.get_today(session, profile)

    async def get_today(self, session: AsyncSession, profile: Profile) -> SleepTodayResult:
        log = await self._repository.get_for_date(session, profile.id, date.today())
        return SleepTodayResult(log=_to_result(log) if log is not None else None, reference_hours=SLEEP_REFERENCE_HOURS)

    async def get_recent(self, session: AsyncSession, profile: Profile) -> SleepRecentResult:
        end = date.today()
        start = end - timedelta(days=6)
        logs = {log.log_date: log for log in await self._repository.list_daily(session, profile.id, start, end)}
        days = [
            SleepRecentDayResult(
                log_date=day,
                hours=float(logs[day].hours) if day in logs else 0.0,
                quality=logs[day].quality if day in logs else None,
            )
            for day in (start + timedelta(days=offset) for offset in range(7))
        ]
        return SleepRecentResult(days=days)
