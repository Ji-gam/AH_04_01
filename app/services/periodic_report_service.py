import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profiles import Profile
from app.repositories.habit_repository import HabitRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.adherence_rate_service import AdherenceRateService, RateResult
from app.services.habit_service import HabitService
from app.services.push_service import PushService

logger = logging.getLogger("app.periodic_report_service")


def _tone(rate: float) -> tuple[str, str]:
    """PRD가 요구하는 "긍정적" 톤을 유지하면서도 순응도에 따라 코멘트를 달리한다(T-ADH-2/
    T-GOAL-3 "저조한 항목엔 격려·조언 코멘트"). 낮은 순응도라도 나무라지 않고 격려로만 이어간다."""
    if rate >= 0.9:
        return ("🌟", "정말 잘 챙기고 계세요! 이 페이스를 유지하면 치료 효과를 꾸준히 볼 수 있어요.")
    if rate >= 0.7:
        return ("👍", "잘 하고 계세요. 조금만 더 챙기면 훨씬 좋아질 거예요.")
    return ("💛", "이번엔 조금 아쉬웠지만 괜찮아요. 다음엔 알림을 확인하는 것부터 다시 시작해봐요.")


def _pct(rate: float) -> int:
    return round(rate * 100)


class PeriodicReportService:
    """F-ADH-2(주간 순응도 피드백) / F-GOAL-3(월간 달성 리포트) 발송 로직.

    스케줄링(요일/월말 판정, 중복발송 방지)은 push_scheduler.py가 맡고, 여기는 "이 프로필에게
    보낼 리포트 내용을 계산하고 발송한다"는 것만 책임진다 - 관심사를 나눠 스케줄러 쪽 코드가
    발송 대상/타이밍 판단에만 집중하게 한다."""

    def __init__(
        self,
        adherence_rate_service: AdherenceRateService | None = None,
        habit_repo: HabitRepository | None = None,
        habit_service: HabitService | None = None,
        profile_repo: ProfileRepository | None = None,
        push_service: PushService | None = None,
    ) -> None:
        self._adherence = adherence_rate_service or AdherenceRateService()
        self._habit_repo = habit_repo or HabitRepository()
        self._habit_service = habit_service or HabitService()
        self._profile_repo = profile_repo or ProfileRepository()
        self._push_service = push_service or PushService()

    async def compute_habit_rate(self, session: AsyncSession, profile: Profile, start: date, end: date) -> RateResult:
        """선택된(습관 선택) 항목 중 그 날짜 진행량이 목표치 이상이면 완료로 센다. 습관 키가
        나중에 바뀌어(예: 세부 진단명 재생성) 지금 카탈로그에 없으면 그 선택은 집계에서
        제외한다 - habit_service.get_recommendations의 "유령 키" 처리와 같은 이유다."""
        target_by_key = {h.key: h.target for h in await self._habit_service.build_full_pool(session, profile)}
        selections = await self._habit_repo.list_selections_for_range(session, profile.id, start, end)
        selections = [s for s in selections if s.habit_key in target_by_key]
        if not selections:
            return RateResult(done=0, total=0, rate=None)

        logs = await self._habit_repo.list_logs_for_range(session, profile.id, start, end)
        progress_by_key = {(log.log_date, log.habit_key): log.progress for log in logs}

        done = sum(
            1
            for s in selections
            if progress_by_key.get((s.select_date, s.habit_key), 0) >= target_by_key[s.habit_key]
        )
        total = len(selections)
        return RateResult(done=done, total=total, rate=done / total)

    async def send_weekly_adherence_feedback(
        self, session: AsyncSession, profile_id: int, week_start: date, week_end: date
    ) -> None:
        """F-ADH-2 - 지난 7일간 복약 순응도를 긍정적인 톤으로 요약해 보낸다."""
        result = await self._adherence.compute(session, profile_id, week_start, week_end)
        if result.rate is None:
            return
        emoji, comment = _tone(result.rate)
        body = f"이번 주 {result.done}/{result.total}회 복용해서 순응도 {_pct(result.rate)}%예요. {comment}"
        await self._push_service.send_to_profile(
            session, profile_id, title=f"{emoji} 이번 주 복약 순응도 리포트", body=body
        )

    async def send_monthly_goal_report(
        self, session: AsyncSession, profile_id: int, month_start: date, month_end: date
    ) -> None:
        """F-GOAL-3 - 지난 한 달 복약 순응도 + 습관 달성률을 함께 요약해 보낸다. 실제 "목표"
        (F-GOAL-1)가 아직 없어, 이 앱에서 "달성률"로 부를 수 있는 두 지표(복약/습관)를 각각
        보고한다(팀 결정: 둘 다 포함)."""
        adherence = await self._adherence.compute(session, profile_id, month_start, month_end)

        profile = await self._profile_repo.get_profile(session, profile_id)
        habit = (
            await self.compute_habit_rate(session, profile, month_start, month_end)
            if profile is not None
            else RateResult(done=0, total=0, rate=None)
        )

        if adherence.rate is None and habit.rate is None:
            return

        lines = []
        if adherence.rate is not None:
            emoji, comment = _tone(adherence.rate)
            lines.append(f"{emoji} 복약 순응도 {_pct(adherence.rate)}% ({adherence.done}/{adherence.total}회) — {comment}")
        if habit.rate is not None:
            emoji, comment = _tone(habit.rate)
            lines.append(f"{emoji} 습관 달성률 {_pct(habit.rate)}% ({habit.done}/{habit.total}회) — {comment}")

        await self._push_service.send_to_profile(
            session,
            profile_id,
            title="🗓️ 이번 달 달성 리포트",
            body="\n".join(lines),
        )
