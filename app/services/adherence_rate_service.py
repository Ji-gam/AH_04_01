from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medication_model import MedicationSchedule
from app.repositories.medication_intake_repository import MedicationIntakeRepository


@dataclass(frozen=True)
class RateResult:
    done: int
    total: int
    rate: float | None  # 그 기간에 등록된 복약 스케줄이 하나도 없으면 None(집계 대상 없음)


class AdherenceRateService:
    """F-ADH-2(주간 피드백)/F-GOAL-3(월간 리포트)가 공유하는 복약 순응도 계산.

    분모(그 기간 동안 예정됐던 총 복용 횟수)는 히트맵(AdherenceHeatmapSection)과 달리 요일별
    반복 규칙을 따지지 않아도 된다 - MedicationSchedule은 등록된 시각이면 매일 반복이라
    "지금 등록된 스케줄 수 × 기간 일수"로 충분하다(scheduleData.ts의 buildGroups가 meds는
    요일 필터 없이 전부 push하는 것과 동일한 전제). 다만 기간 중간에 새로 등록되거나 삭제된
    스케줄은 "지금 등록된 것"만 반영되어 과거 시점 실제 상태와 다를 수 있다 - 히트맵 쪽에서
    이미 받아들인 것과 같은 한계라 여기서도 동일하게 둔다."""

    def __init__(self, repo: MedicationIntakeRepository | None = None) -> None:
        self._repo = repo or MedicationIntakeRepository()

    async def compute(self, session: AsyncSession, profile_id: int, start_date: date, end_date: date) -> RateResult:
        result = await session.execute(
            select(MedicationSchedule.times).where(MedicationSchedule.profile_id == profile_id)
        )
        schedules_times = result.scalars().all()
        doses_per_day = sum(len(times) for times in schedules_times)
        days = (end_date - start_date).days + 1
        total = doses_per_day * days
        if total == 0:
            return RateResult(done=0, total=0, rate=None)

        counts_by_date = await self._repo.count_by_date_for_range(session, profile_id, start_date, end_date)
        done = min(sum(counts_by_date.values()), total)
        return RateResult(done=done, total=total, rate=done / total)
