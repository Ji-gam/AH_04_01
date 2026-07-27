import logging
from datetime import date, timedelta
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.weekly_report_dto import WeeklyReportItemResult, WeeklyReportListResult
from app.models.weekly_reports import WeeklyReport
from app.repositories.diet_repository import DietRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.habit_repository import HabitRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.weekly_report_repository import WeeklyReportRepository
from app.services.adherence_rate_service import AdherenceRateService
from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.periodic_report_service import PeriodicReportService

logger = logging.getLogger("app.weekly_report_service")

_SYSTEM_PROMPT = (
    "당신은 헬스케어 앱 ReMedi의 주간 리포트 작성자입니다. 사용자의 이번 주 습관 실천, "
    "복약 순응도, 식단, 운동 기록 데이터를 바탕으로 따뜻하고 격려하는 톤의 한국어 리포트를 "
    "3~5문장으로 작성하세요. 숫자를 자연스러운 문장 속에 녹여서 언급하고, 딱딱한 나열식 "
    "표현은 피하세요. 의학적 조언이나 진단은 하지 마세요."
)


class WeeklyReportSummary(BaseModel):
    """AIWorkerGateway.call_structured()에는 자유텍스트 전용 메서드가 없어(스키마 필수),
    서술형 문단 하나만 담는 최소 스키마로 받는다 - generate_health_content.py의
    HealthContentCard와 같은 발상."""

    summary: str


def _fallback_report(stats_lines: list[str]) -> str:
    """AI 호출이 실패해도(ai_worker 다운, 키 미설정 등) 리포트 자체는 항상 저장되게 하는
    규칙 기반 폴백 - habit_service.py가 AIWorkerUnavailableError 등에서 템플릿으로
    대체하는 것과 같은 패턴."""
    return "\n".join(stats_lines) + "\n\n이번 주도 수고 많으셨어요! 다음 주도 같이 파이팅해봐요 💪"


class WeeklyReportService:
    def __init__(
        self,
        weekly_report_repo: WeeklyReportRepository | None = None,
        diet_repo: DietRepository | None = None,
        exercise_repo: ExerciseRepository | None = None,
        habit_repo: HabitRepository | None = None,
        profile_repo: ProfileRepository | None = None,
        adherence_rate_service: AdherenceRateService | None = None,
        periodic_report_service: PeriodicReportService | None = None,
        gateway: AIWorkerGateway | None = None,
    ) -> None:
        self._weekly_report_repo = weekly_report_repo or WeeklyReportRepository()
        self._diet_repo = diet_repo or DietRepository()
        self._exercise_repo = exercise_repo or ExerciseRepository()
        self._habit_repo = habit_repo or HabitRepository()
        self._profile_repo = profile_repo or ProfileRepository()
        self._adherence = adherence_rate_service or AdherenceRateService()
        self._periodic_report_service = periodic_report_service or PeriodicReportService()
        self._gateway = gateway or AIWorkerGateway()

    async def list_candidate_profile_ids(self, session: AsyncSession, start: date, end: date) -> set[int]:
        """이 주에 습관 선택/식단 기록/운동 기록 중 하나라도 있는 프로필만 대상으로 한다 -
        push_scheduler.py의 F-GOAL-3(월간 리포트) 대상자 선정 방식과 같은 발상."""
        habit_ids = await self._habit_repo.list_profile_ids_with_selections_in_range(session, start, end)
        diet_ids = await self._diet_repo.list_profile_ids_with_logs_in_range(session, start, end)
        exercise_ids = await self._exercise_repo.list_profile_ids_with_logs_in_range(session, start, end)
        return set(habit_ids) | set(diet_ids) | set(exercise_ids)

    async def generate_and_save(self, session: AsyncSession, profile_id: int) -> WeeklyReport:
        week_end = date.today()
        week_start = week_end - timedelta(days=6)

        existing = await self._weekly_report_repo.get_by_profile_and_week(session, profile_id, week_start)
        if existing is not None:
            return existing

        profile = await self._profile_repo.get_profile(session, profile_id)
        adherence = await self._adherence.compute(session, profile_id, week_start, week_end)
        diet_totals = await self._diet_repo.list_daily_totals(session, profile_id, week_start, week_end)
        exercise_totals = await self._exercise_repo.list_daily_totals(session, profile_id, week_start, week_end)

        stats_lines: list[str] = []
        if profile is not None:
            habit_rate = await self._periodic_report_service.compute_habit_rate(session, profile, week_start, week_end)
            if habit_rate.rate is not None:
                stats_lines.append(
                    f"습관 달성률 {round(habit_rate.rate * 100)}% ({habit_rate.done}/{habit_rate.total}회)"
                )
        if adherence.rate is not None:
            stats_lines.append(f"복약 순응도 {round(adherence.rate * 100)}% ({adherence.done}/{adherence.total}회)")
        if diet_totals:
            avg_kcal = sum(float(total) for _, total in diet_totals) / len(diet_totals)
            stats_lines.append(f"식단 기록 {len(diet_totals)}일, 평균 일일 섭취 칼로리 {round(avg_kcal)}kcal")
        if exercise_totals:
            total_kcal = sum(float(total) for _, total in exercise_totals)
            stats_lines.append(f"운동 기록 {len(exercise_totals)}일, 이번 주 총 소모 칼로리 {round(total_kcal)}kcal")

        if not stats_lines:
            content = (
                "이번 주는 기록된 활동이 없어요. 다음 주엔 습관이나 식단, 운동 중 하나라도 기록해보는 건 어떨까요?"
            )
        else:
            try:
                result = await self._gateway.call_structured(
                    system_prompt=_SYSTEM_PROMPT,
                    user_input=" / ".join(stats_lines),
                    schema=WeeklyReportSummary,
                )
                content = cast(WeeklyReportSummary, result).summary
            except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
                logger.warning(
                    "주간 리포트 AI 생성 실패, 폴백 템플릿으로 대체합니다 (profile_id=%s): %s", profile_id, e
                )
                content = _fallback_report(stats_lines)

        return await self._weekly_report_repo.create(session, profile_id, week_start, week_end, content)

    async def list_reports(self, session: AsyncSession, profile_id: int) -> WeeklyReportListResult:
        reports = await self._weekly_report_repo.list_for_profile(session, profile_id)
        return WeeklyReportListResult(
            reports=[
                WeeklyReportItemResult(
                    id=r.id,
                    week_start_date=r.week_start_date,
                    week_end_date=r.week_end_date,
                    content=r.content,
                    created_at=r.created_at,
                )
                for r in reports
            ]
        )
