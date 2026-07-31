import logging
from datetime import date, timedelta
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.weekly_report_dto import WeeklyReportItemResult, WeeklyReportListResult
from app.models.profiles import Profile
from app.models.weekly_reports import WeeklyReport
from app.repositories.diet_repository import DietRepository
from app.repositories.exercise_repository import ExerciseRepository
from app.repositories.habit_repository import HabitRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.sleep_repository import SleepRepository
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
    "당신은 헬스케어 앱 ReMedi의 주간 리포트 작성자입니다. 사용자의 키/몸무게(BMI)와 이번 주 "
    "습관 실천, 복약 순응도, 식단, 운동, 수면 기록 데이터를 바탕으로 따뜻하고 격려하는 톤의 "
    "한국어 리포트를 3~5문장으로 작성하세요. 키/몸무게가 주어지면 식단·운동 칼로리가 그 사람에게 "
    "적절한 수준인지 자연스럽게 언급하세요. 숫자를 자연스러운 문장 속에 녹여서 언급하고, 딱딱한 "
    "나열식 표현은 피하세요. 의학적 조언이나 진단은 하지 마세요."
)


class WeeklyReportSummary(BaseModel):
    """AIWorkerGateway.call_structured()에는 자유텍스트 전용 메서드가 없어(스키마 필수),
    서술형 문단 하나만 담는 최소 스키마로 받는다 - generate_health_content.py의
    HealthContentCard와 같은 발상."""

    summary: str


def _body_info_line(profile: Profile | None) -> str | None:
    """키/몸무게가 둘 다 있으면 BMI를 계산해 리포트 한 줄로 만든다(2026-07-29,
    "주간 리포트에 키/몸무게도 반영해달라"는 요청). 개인식별정보와 분리 저장된
    profile.health_profile에서 읽는다(NFR-ARCH-001 리팩터링 이후 구조)."""
    if profile is None:
        return None
    health = profile.health_profile
    if health is None or health.height_cm is None or health.weight_kg is None:
        return None
    height_m = float(health.height_cm) / 100
    bmi = round(float(health.weight_kg) / (height_m**2), 1)
    return f"키 {health.height_cm}cm, 몸무게 {health.weight_kg}kg (BMI {bmi})"


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
        sleep_repo: SleepRepository | None = None,
        adherence_rate_service: AdherenceRateService | None = None,
        periodic_report_service: PeriodicReportService | None = None,
        gateway: AIWorkerGateway | None = None,
    ) -> None:
        self._weekly_report_repo = weekly_report_repo or WeeklyReportRepository()
        self._diet_repo = diet_repo or DietRepository()
        self._exercise_repo = exercise_repo or ExerciseRepository()
        self._habit_repo = habit_repo or HabitRepository()
        self._profile_repo = profile_repo or ProfileRepository()
        self._sleep_repo = sleep_repo or SleepRepository()
        self._adherence = adherence_rate_service or AdherenceRateService()
        self._periodic_report_service = periodic_report_service or PeriodicReportService()
        self._gateway = gateway or AIWorkerGateway()

    async def list_candidate_profile_ids(self, session: AsyncSession, start: date, end: date) -> set[int]:
        """이 주에 습관 선택/식단 기록/운동 기록 중 하나라도 있는 프로필만 대상으로 한다 -
        push_scheduler.py의 F-GOAL-3(월간 리포트) 대상자 선정 방식과 같은 발상."""
        habit_ids = await self._habit_repo.list_profile_ids_with_selections_in_range(session, start, end)
        diet_ids = await self._diet_repo.list_profile_ids_with_logs_in_range(session, start, end)
        exercise_ids = await self._exercise_repo.list_profile_ids_with_logs_in_range(session, start, end)
        sleep_ids = await self._sleep_repo.list_profile_ids_with_logs_in_range(session, start, end)
        return set(habit_ids) | set(diet_ids) | set(exercise_ids) | set(sleep_ids)

    async def _build_stats_lines(
        self, session: AsyncSession, profile_id: int, profile: Profile | None, week_start: date, week_end: date
    ) -> list[str]:
        """generate_and_save()의 AI 입력/폴백 문구에 쓸 통계 문장들 - 항목별로 데이터가
        있을 때만 한 줄씩 추가한다. 별도 메서드로 분리해 generate_and_save()의 분기 수를
        낮게 유지한다(ruff C901)."""
        adherence = await self._adherence.compute(session, profile_id, week_start, week_end)
        diet_totals = await self._diet_repo.list_daily_totals(session, profile_id, week_start, week_end)
        exercise_totals = await self._exercise_repo.list_daily_totals(session, profile_id, week_start, week_end)
        sleep_logs = await self._sleep_repo.list_daily(session, profile_id, week_start, week_end)

        stats_lines: list[str] = []
        body_info_line = _body_info_line(profile)
        if body_info_line is not None:
            stats_lines.append(body_info_line)
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
        if sleep_logs:
            avg_hours = sum(float(log.hours) for log in sleep_logs) / len(sleep_logs)
            avg_quality = sum(log.quality for log in sleep_logs) / len(sleep_logs)
            stats_lines.append(
                f"수면 기록 {len(sleep_logs)}일, 평균 수면시간 {round(avg_hours, 1)}시간, "
                f"평균 수면의 질 {round(avg_quality, 1)}/5"
            )
        return stats_lines

    async def generate_and_save(self, session: AsyncSession, profile_id: int) -> WeeklyReport:
        week_end = date.today()
        week_start = week_end - timedelta(days=6)

        existing = await self._weekly_report_repo.get_by_profile_and_week(session, profile_id, week_start)
        if existing is not None:
            return existing

        profile = await self._profile_repo.get_profile(session, profile_id)
        stats_lines = await self._build_stats_lines(session, profile_id, profile, week_start, week_end)

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
