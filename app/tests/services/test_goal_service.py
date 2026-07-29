from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.goal_dto import GoalCreateRequest, GoalUpdateRequest
from app.models.goals import GoalType
from app.models.profiles import Disease
from app.repositories.goal_progress_log_repository import GoalProgressLogRepository
from app.repositories.goal_repository import GoalRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.ai_worker_gateway import AIWorkerGateway, AIWorkerUnavailableError
from app.services.goal_service import GoalGuideSummary, GoalService, _fallback_guide, _progress_rate, _term


@dataclass
class FakeDiagnosisEntry:
    disease: Disease


@dataclass
class FakeProfile:
    id: int
    diagnosis_entries: list[FakeDiagnosisEntry] = field(default_factory=list)


class FakeProfileRepository:
    """진단병력만 흉내낸다 - test_habit_service.py의 FakeProfile과 같은 발상."""

    def __init__(self, profile: FakeProfile | None) -> None:
        self._profile = profile

    async def get_profile(self, session: object, profile_id: int) -> FakeProfile | None:
        return self._profile


@dataclass
class FakeGoal:
    """SQLAlchemy Goal과 속성명이 1:1로 같은 순수 파이썬 객체 - GoalService.update()의
    setattr(goal, field, value)이 필드명 그대로 동작해야 하므로 이름을 맞춘다."""

    id: int
    profile_id: int
    title: str
    goal_type: GoalType
    start_value: Decimal | None
    target_value: Decimal | None
    current_value: Decimal | None
    unit: str | None
    start_date: date
    end_date: date
    is_achieved: bool = False
    guide_content: str | None = None
    guide_generated_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime(2026, 7, 29, tzinfo=UTC))


class FakeGoalRepository:
    def __init__(self) -> None:
        self._store: dict[int, FakeGoal] = {}
        self._next_id = 1

    async def create(
        self,
        session: object,
        profile_id: int,
        title: str,
        goal_type: GoalType,
        start_value: Decimal | None,
        target_value: Decimal | None,
        current_value: Decimal | None,
        unit: str | None,
        start_date: date,
        end_date: date,
    ) -> FakeGoal:
        goal = FakeGoal(
            id=self._next_id,
            profile_id=profile_id,
            title=title,
            goal_type=goal_type,
            start_value=start_value,
            target_value=target_value,
            current_value=current_value,
            unit=unit,
            start_date=start_date,
            end_date=end_date,
        )
        self._store[goal.id] = goal
        self._next_id += 1
        return goal

    async def get_by_id_and_profile(self, session: object, profile_id: int, goal_id: int) -> FakeGoal | None:
        goal = self._store.get(goal_id)
        return goal if goal is not None and goal.profile_id == profile_id else None

    async def list_for_profile(self, session: object, profile_id: int) -> list[FakeGoal]:
        return [g for g in self._store.values() if g.profile_id == profile_id]

    async def save_guide(self, session: object, goal: FakeGoal, guide_content: str, generated_at: datetime) -> FakeGoal:
        goal.guide_content = guide_content
        goal.guide_generated_at = generated_at
        return goal

    async def delete(self, session: object, profile_id: int, goal_id: int) -> bool:
        goal = await self.get_by_id_and_profile(session, profile_id, goal_id)
        if goal is None:
            return False
        del self._store[goal_id]
        return True


@dataclass
class FakeLog:
    log_date: date
    value: Decimal


class FakeGoalProgressLogRepository:
    def __init__(self) -> None:
        self._logs: dict[int, list[FakeLog]] = {}

    async def upsert(self, session: object, goal_id: int, log_date: date, value: Decimal) -> FakeLog:
        logs = self._logs.setdefault(goal_id, [])
        existing = next((row for row in logs if row.log_date == log_date), None)
        if existing is not None:
            existing.value = value
            return existing
        row = FakeLog(log_date=log_date, value=value)
        logs.append(row)
        return row

    async def list_recent(self, session: object, goal_id: int) -> list[FakeLog]:
        return sorted(self._logs.get(goal_id, []), key=lambda row: row.log_date)[-7:]


class FakeSession:
    """GoalService.update()/log_progress()는 repository를 안 거치고 session.commit()/
    refresh()를 직접 호출한다(create()와 달리) - 그 두 메서드만 no-op으로 흉내낸다."""

    async def commit(self) -> None:
        return None

    async def refresh(self, instance: object, attribute_names: object = None) -> None:
        return None


class FakeGateway:
    def __init__(self, guide: str = "테스트 가이드입니다.", error: Exception | None = None) -> None:
        self.guide = guide
        self.error = error
        self.call_count = 0
        self.last_user_input: str | None = None

    async def call_structured(self, system_prompt: str, user_input: str, schema: type) -> GoalGuideSummary:
        self.call_count += 1
        self.last_user_input = user_input
        if self.error is not None:
            raise self.error
        return GoalGuideSummary(guide=self.guide)


def _build_service(
    gateway: FakeGateway,
    goal_repo: FakeGoalRepository | None = None,
    profile: FakeProfile | None = None,
    progress_repo: FakeGoalProgressLogRepository | None = None,
) -> GoalService:
    return GoalService(
        goal_repo=cast(GoalRepository, goal_repo or FakeGoalRepository()),
        profile_repo=cast(ProfileRepository, FakeProfileRepository(profile)),
        gateway=cast(AIWorkerGateway, gateway),
        progress_log_repo=cast(GoalProgressLogRepository, progress_repo or FakeGoalProgressLogRepository()),
    )


def _create_request(**overrides: object) -> GoalCreateRequest:
    defaults: dict[str, object] = {
        "title": "체중 감량",
        "start_value": 80,
        "target_value": 75,
        "current_value": None,
        "unit": "kg",
        "start_date": date(2026, 7, 1),
        "end_date": date(2026, 7, 20),
    }
    defaults.update(overrides)
    return GoalCreateRequest(**defaults)  # type: ignore[arg-type]


async def test_create_goal_generates_guide_with_disease_context():
    """진단병력이 있으면 AI 호출 시 user_input에 그 질환명이 한글로 포함돼야 한다."""
    profile = FakeProfile(id=1, diagnosis_entries=[FakeDiagnosisEntry(disease=Disease.DIABETES)])
    gateway = FakeGateway(guide="당뇨에 맞춘 가이드입니다.")
    service = _build_service(gateway, profile=profile)

    result = await service.create(cast(AsyncSession, FakeSession()), profile_id=1, data=_create_request())

    assert result.guide_content == "당뇨에 맞춘 가이드입니다."
    assert result.guide_generated_at is not None
    assert gateway.last_user_input is not None
    assert "당뇨" in gateway.last_user_input


async def test_create_goal_generates_guide_without_disease():
    """진단병력이 하나도 없으면 user_input에 '없음'이 들어가야 한다(질환명 대신)."""
    profile = FakeProfile(id=2, diagnosis_entries=[])
    gateway = FakeGateway()
    service = _build_service(gateway, profile=profile)

    await service.create(cast(AsyncSession, FakeSession()), profile_id=2, data=_create_request())

    assert gateway.last_user_input is not None
    assert "없음" in gateway.last_user_input


async def test_create_goal_defaults_to_numeric_type_when_omitted():
    """goal_type을 안 보내면 NUMERIC이 기본값이어야 한다(하위호환)."""
    gateway = FakeGateway()
    service = _build_service(gateway, profile=FakeProfile(id=3))

    result = await service.create(cast(AsyncSession, FakeSession()), profile_id=3, data=_create_request())

    assert result.goal_type == GoalType.NUMERIC


async def test_create_frequency_goal_persists_goal_type():
    """goal_type=FREQUENCY로 만들면 그대로 저장·반환돼야 한다."""
    gateway = FakeGateway()
    service = _build_service(gateway, profile=FakeProfile(id=4))
    data = _create_request(goal_type=GoalType.FREQUENCY, start_value=0, target_value=3, current_value=0, unit="회")

    result = await service.create(cast(AsyncSession, FakeSession()), profile_id=4, data=data)

    assert result.goal_type == GoalType.FREQUENCY


async def test_ai_failure_uses_fallback_guide():
    """ai_worker 호출이 실패해도 예외를 올리지 않고 폴백 템플릿으로 저장돼야 한다."""
    gateway = FakeGateway(error=AIWorkerUnavailableError("ai_worker 연결 실패"))
    service = _build_service(gateway, profile=FakeProfile(id=5))

    result = await service.create(
        cast(AsyncSession, FakeSession()), profile_id=5, data=_create_request(title="꾸준히 걷기")
    )

    assert result.guide_content == _fallback_guide("꾸준히 걷기")
    assert result.guide_generated_at is not None


async def test_update_regenerates_guide_when_title_changes():
    """제목처럼 추적 가능한 필드가 바뀌면 가이드가 다시 생성돼야 한다."""
    gateway = FakeGateway(guide="첫 가이드")
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=6))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=6, data=_create_request())

    gateway.guide = "갱신된 가이드"
    result = await service.update(
        cast(AsyncSession, FakeSession()), profile_id=6, goal_id=created.id, data=GoalUpdateRequest(title="새 목표명")
    )

    assert result is not None
    assert gateway.call_count == 2
    assert result.guide_content == "갱신된 가이드"


async def test_update_does_not_regenerate_when_only_is_achieved_changes():
    """is_achieved만 바뀌는 경우는 목표 '전략' 자체가 안 바뀐 것이므로 가이드를 다시 만들지 않는다."""
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=7))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=7, data=_create_request())
    assert gateway.call_count == 1

    result = await service.update(
        cast(AsyncSession, FakeSession()), profile_id=7, goal_id=created.id, data=GoalUpdateRequest(is_achieved=True)
    )

    assert result is not None
    assert result.is_achieved is True
    assert gateway.call_count == 1


async def test_update_does_not_regenerate_when_no_fields_given():
    """빈 PATCH 요청은 가이드를 다시 만들지 않는다."""
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=8))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=8, data=_create_request())

    await service.update(cast(AsyncSession, FakeSession()), profile_id=8, goal_id=created.id, data=GoalUpdateRequest())

    assert gateway.call_count == 1


async def test_update_returns_none_for_goal_owned_by_other_profile():
    """다른 프로필 소유의 목표는 수정할 수 없어야 한다(profile_id 기준 스코핑)."""
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=9))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=9, data=_create_request())

    result = await service.update(
        cast(AsyncSession, FakeSession()), profile_id=999, goal_id=created.id, data=GoalUpdateRequest(title="가로채기")
    )

    assert result is None


async def test_log_progress_does_not_regenerate_guide():
    """일일 기록(log_progress)은 가이드를 재생성하지 않는다 - update()와의 핵심 차이."""
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=10))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=10, data=_create_request())
    assert gateway.call_count == 1

    result = await service.log_progress(
        cast(AsyncSession, FakeSession()), profile_id=10, goal_id=created.id, value=78.5, log_date=None
    )

    assert result is not None
    assert result.current_value == 78.5
    assert gateway.call_count == 1


async def test_log_progress_upserts_same_day_instead_of_duplicating():
    """같은 날 두 번 기록하면 그날 값이 덮어써지고 최근 기록은 1건만 남아야 한다."""
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=11))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=11, data=_create_request())
    today = date(2026, 7, 29)

    await service.log_progress(
        cast(AsyncSession, FakeSession()), profile_id=11, goal_id=created.id, value=79.0, log_date=today
    )
    result = await service.log_progress(
        cast(AsyncSession, FakeSession()), profile_id=11, goal_id=created.id, value=78.0, log_date=today
    )

    assert result is not None
    assert len(result.recent_logs) == 1
    assert result.recent_logs[0].value == 78.0


async def test_delete_removes_goal_for_owner():
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=12))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=12, data=_create_request())

    deleted = await service.delete(cast(AsyncSession, FakeSession()), profile_id=12, goal_id=created.id)
    still_there = await service.update(
        cast(AsyncSession, FakeSession()), profile_id=12, goal_id=created.id, data=GoalUpdateRequest(title="x")
    )

    assert deleted is True
    assert still_there is None


async def test_delete_returns_false_for_goal_owned_by_other_profile():
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=13))
    created = await service.create(cast(AsyncSession, FakeSession()), profile_id=13, data=_create_request())

    deleted = await service.delete(cast(AsyncSession, FakeSession()), profile_id=999, goal_id=created.id)

    assert deleted is False


async def test_list_goals_only_returns_goals_for_that_profile():
    gateway = FakeGateway()
    repo = FakeGoalRepository()
    service = _build_service(gateway, goal_repo=repo, profile=FakeProfile(id=14))
    await service.create(cast(AsyncSession, FakeSession()), profile_id=14, data=_create_request(title="내 목표"))
    await service.create(cast(AsyncSession, FakeSession()), profile_id=15, data=_create_request(title="남의 목표"))

    result = await service.list_goals(cast(AsyncSession, FakeSession()), profile_id=14)

    assert [g.title for g in result.goals] == ["내 목표"]


def test_term_is_short_when_within_31_days():
    assert _term(date(2026, 7, 1), date(2026, 7, 20)) == "단기"
    assert _term(date(2026, 7, 1), date(2026, 8, 1)) == "단기"


def test_term_is_long_when_over_31_days():
    assert _term(date(2026, 7, 1), date(2026, 9, 1)) == "장기"


def test_progress_rate_handles_decreasing_target():
    """체중감량처럼 줄이는 목표도 같은 공식으로 0~1 사이 값이 나와야 한다."""
    rate = _progress_rate(Decimal("80"), Decimal("75"), Decimal("77.5"))
    assert rate == 0.5


def test_progress_rate_clamps_when_overshot_past_target():
    rate = _progress_rate(Decimal("80"), Decimal("75"), Decimal("70"))
    assert rate == 1.0


def test_progress_rate_is_none_when_any_value_missing():
    assert _progress_rate(None, Decimal("75"), Decimal("77")) is None
    assert _progress_rate(Decimal("80"), None, Decimal("77")) is None
    assert _progress_rate(Decimal("80"), Decimal("75"), None) is None
