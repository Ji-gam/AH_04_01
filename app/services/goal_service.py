import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.goal_dto import (
    GoalCreateRequest,
    GoalItemResult,
    GoalListResult,
    GoalProgressLogItemResult,
    GoalTerm,
    GoalUpdateRequest,
)
from app.models.goal_progress_logs import GoalProgressLog
from app.models.goals import Goal
from app.repositories.goal_progress_log_repository import GoalProgressLogRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.disease_code_mapper import map_diagnosis_entries

logger = logging.getLogger("app.goal_service")

_SHORT_TERM_MAX_DAYS = 31
_DECIMAL_FIELDS = {"start_value", "target_value", "current_value"}

_SYSTEM_PROMPT = (
    "당신은 헬스케어 앱 ReMedi의 목표 코치입니다. 사용자의 목표(제목, 시작 수치, 목표 수치, "
    "기간)와 진단 질병 정보를 참고해 안전하고 실천 가능한 식단·운동 가이드를 3~5문장으로 "
    "작성하세요. 지병이 있다면 그 질병에 위험할 수 있는 음식이나 과격한 운동은 피하도록 "
    "우선 반영하세요. 의학적 진단이나 처방은 하지 마세요."
)


class GoalGuideSummary(BaseModel):
    """AIWorkerGateway.call_structured()는 자유텍스트 전용 메서드가 없어(스키마 필수),
    weekly_report_service.py와 같은 발상으로 서술형 문단 하나만 담는 최소 스키마를 쓴다."""

    guide: str


def _fallback_guide(title: str) -> str:
    """AI 호출이 실패해도(ai_worker 다운 등) 가이드 자체는 항상 저장되게 하는 규칙 기반
    폴백 - weekly_report_service.py의 _fallback_report()와 같은 패턴."""
    return f"'{title}' 목표를 향해 꾸준히 기록해보세요! 균형 잡힌 식사와 무리하지 않는 운동을 병행하면 도움이 돼요."


def _term(start_date: date, end_date: date) -> GoalTerm:
    return "단기" if (end_date - start_date).days <= _SHORT_TERM_MAX_DAYS else "장기"


def _progress_rate(
    start_value: Decimal | None, target_value: Decimal | None, current_value: Decimal | None
) -> float | None:
    if start_value is None or target_value is None or current_value is None or start_value == target_value:
        return None
    rate = float(current_value - start_value) / float(target_value - start_value)
    return max(0.0, min(1.0, rate))


def _to_result(goal: Goal, recent_logs: list[GoalProgressLog]) -> GoalItemResult:
    return GoalItemResult(
        id=goal.id,
        title=goal.title,
        goal_type=goal.goal_type,
        start_value=float(goal.start_value) if goal.start_value is not None else None,
        target_value=float(goal.target_value) if goal.target_value is not None else None,
        current_value=float(goal.current_value) if goal.current_value is not None else None,
        unit=goal.unit,
        start_date=goal.start_date,
        end_date=goal.end_date,
        term=_term(goal.start_date, goal.end_date),
        progress_rate=_progress_rate(goal.start_value, goal.target_value, goal.current_value),
        is_achieved=goal.is_achieved,
        guide_content=goal.guide_content,
        guide_generated_at=goal.guide_generated_at,
        created_at=goal.created_at,
        recent_logs=[GoalProgressLogItemResult(log_date=log.log_date, value=float(log.value)) for log in recent_logs],
    )


class GoalService:
    def __init__(
        self,
        goal_repo: GoalRepository | None = None,
        profile_repo: ProfileRepository | None = None,
        gateway: AIWorkerGateway | None = None,
        progress_log_repo: GoalProgressLogRepository | None = None,
    ) -> None:
        self._repo = goal_repo or GoalRepository()
        self._profile_repo = profile_repo or ProfileRepository()
        self._gateway = gateway or AIWorkerGateway()
        self._progress_log_repo = progress_log_repo or GoalProgressLogRepository()

    async def _generate_guide(self, session: AsyncSession, profile_id: int, goal: Goal) -> str:
        profile = await self._profile_repo.get_profile(session, profile_id)
        diseases = (
            map_diagnosis_entries([{"disease": e.disease.value} for e in profile.diagnosis_entries])
            if profile is not None
            else []
        )

        value_line = ""
        if goal.start_value is not None and goal.target_value is not None:
            unit = goal.unit or ""
            value_line = f" ({goal.start_value}{unit} → {goal.target_value}{unit})"
        user_input = (
            f"목표: {goal.title}{value_line}, 기간: {goal.start_date}~{goal.end_date} / "
            f"진단 질병: {', '.join(diseases) if diseases else '없음'}"
        )

        try:
            result = await self._gateway.call_structured(
                system_prompt=_SYSTEM_PROMPT, user_input=user_input, schema=GoalGuideSummary
            )
            return cast(GoalGuideSummary, result).guide
        except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
            logger.warning("목표 가이드 AI 생성 실패, 폴백 템플릿으로 대체합니다 (goal_id=%s): %s", goal.id, e)
            return _fallback_guide(goal.title)

    async def create(self, session: AsyncSession, profile_id: int, data: GoalCreateRequest) -> GoalItemResult:
        goal = await self._repo.create(
            session,
            profile_id,
            title=data.title,
            goal_type=data.goal_type,
            start_value=Decimal(str(data.start_value)) if data.start_value is not None else None,
            target_value=Decimal(str(data.target_value)) if data.target_value is not None else None,
            current_value=(
                Decimal(str(data.current_value))
                if data.current_value is not None
                else (Decimal(str(data.start_value)) if data.start_value is not None else None)
            ),
            unit=data.unit,
            start_date=data.start_date,
            end_date=data.end_date,
        )
        guide = await self._generate_guide(session, profile_id, goal)
        goal = await self._repo.save_guide(session, goal, guide, datetime.now(tz=UTC))
        return _to_result(goal, [])

    async def update(
        self, session: AsyncSession, profile_id: int, goal_id: int, data: GoalUpdateRequest
    ) -> GoalItemResult | None:
        goal = await self._repo.get_by_id_and_profile(session, profile_id, goal_id)
        if goal is None:
            return None

        updates = data.model_dump(exclude_none=True, exclude={"is_achieved"})
        for field, value in updates.items():
            setattr(goal, field, Decimal(str(value)) if field in _DECIMAL_FIELDS else value)
        if data.is_achieved is not None:
            goal.is_achieved = data.is_achieved

        await session.commit()
        await session.refresh(goal)

        recent_logs = await self._progress_log_repo.list_recent(session, goal.id)
        if not updates:
            return _to_result(goal, recent_logs)

        # F-GOAL-2 - 목표(수치/기간/제목)가 바뀌면 가이드를 자동으로 다시 생성한다.
        guide = await self._generate_guide(session, profile_id, goal)
        goal = await self._repo.save_guide(session, goal, guide, datetime.now(tz=UTC))
        return _to_result(goal, recent_logs)

    async def list_goals(self, session: AsyncSession, profile_id: int) -> GoalListResult:
        goals = await self._repo.list_for_profile(session, profile_id)
        results = []
        for g in goals:
            recent_logs = await self._progress_log_repo.list_recent(session, g.id)
            results.append(_to_result(g, recent_logs))
        return GoalListResult(goals=results)

    async def log_progress(
        self, session: AsyncSession, profile_id: int, goal_id: int, value: float, log_date: date | None
    ) -> GoalItemResult | None:
        """ "오늘 기록하기" - 목표 정의(제목/기간 등)는 그대로 두고 수치만 하루 단위로 쌓는다.
        수정(update)과 달리 가이드는 재생성하지 않는다 - 가이드는 목표 "전략"에 대한 것이라
        매일의 측정값 하나하나에 반응할 필요가 없다(잦은 AI 호출을 피하는 의도도 있다)."""
        goal = await self._repo.get_by_id_and_profile(session, profile_id, goal_id)
        if goal is None:
            return None

        effective_date = log_date or date.today()
        decimal_value = Decimal(str(value))
        await self._progress_log_repo.upsert(session, goal_id, effective_date, decimal_value)

        goal.current_value = decimal_value
        await session.commit()
        await session.refresh(goal)

        recent_logs = await self._progress_log_repo.list_recent(session, goal.id)
        return _to_result(goal, recent_logs)

    async def compute_progress_summary(self, session: AsyncSession, profile_id: int) -> list[tuple[str, float]]:
        """F-GOAL-3(주간/월간 달성 리포트)에 넣을 활성 목표(미달성)의 (제목, 진행률) 목록.
        수치를 하나라도 안 넣어 진행률을 계산할 수 없는 목표는 제외한다."""
        goals = await self._repo.list_for_profile(session, profile_id)
        summary: list[tuple[str, float]] = []
        for g in goals:
            if g.is_achieved:
                continue
            rate = _progress_rate(g.start_value, g.target_value, g.current_value)
            if rate is not None:
                summary.append((g.title, rate))
        return summary

    async def delete(self, session: AsyncSession, profile_id: int, goal_id: int) -> bool:
        return await self._repo.delete(session, profile_id, goal_id)
