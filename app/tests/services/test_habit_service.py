from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profiles import Disease, Profile
from app.repositories.habit_repository import HabitRepository
from app.services.ai_worker_gateway import AIWorkerGateway, AIWorkerUnavailableError
from app.services.habit_service import (
    BASE_HABITS,
    DISEASE_HABITS,
    MAX_RECOMMENDATIONS,
    HabitDef,
    HabitService,
    SubtypeHabitSuggestion,
    SubtypeHabitSuggestionBatch,
    pick_recommendations,
)


@dataclass
class FakeDiseaseSubtype:
    id: int
    name: str


@dataclass
class FakeDiagnosisEntry:
    disease: Disease
    disease_subtype_id: int | None = None
    disease_subtype: FakeDiseaseSubtype | None = None
    id: int = 1
    detail: str | None = None
    diagnosed_years_ago: int | None = None
    status: Any | None = None
    on_medication: bool | None = None


@dataclass
class FakeProfile:
    id: int
    diagnosis_entries: list[FakeDiagnosisEntry] = field(default_factory=list)


@dataclass
class FakeSuggestionRow:
    disease_subtype_id: int
    slot: int
    label: str
    icon: str
    unit: str
    target: int


class FakeHabitRepository:
    """실제 DB 없이 캐시 조회/저장만 인메모리로 흉내낸다 - test_chat_service.py의
    FakeChatRepository와 같은 방식(session 인자는 받되 안 쓴다)."""

    def __init__(self) -> None:
        self._suggestions: dict[int, list[FakeSuggestionRow]] = {}

    async def list_subtype_suggestions(self, session: Any, disease_subtype_id: int) -> list[FakeSuggestionRow]:
        return self._suggestions.get(disease_subtype_id, [])

    async def save_subtype_suggestions(
        self, disease_subtype_id: int, suggestions: list[dict]
    ) -> list[FakeSuggestionRow]:
        rows = [
            FakeSuggestionRow(disease_subtype_id=disease_subtype_id, slot=slot, **suggestion)
            for slot, suggestion in enumerate(suggestions)
        ]
        self._suggestions[disease_subtype_id] = rows
        return rows


class FakeGateway:
    def __init__(self, result: SubtypeHabitSuggestionBatch | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.call_count = 0

    async def call_structured(self, system_prompt: str, user_input: str, schema: type) -> SubtypeHabitSuggestionBatch:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _habits_batch(*specs: tuple[str, str, str, int]) -> SubtypeHabitSuggestionBatch:
    return SubtypeHabitSuggestionBatch(
        habits=[
            SubtypeHabitSuggestion(label=label, icon=icon, unit=unit, target=target)
            for label, icon, unit, target in specs
        ]
    )


def _build_service(gateway: FakeGateway, repository: FakeHabitRepository | None = None) -> HabitService:
    return HabitService(
        repository=cast(HabitRepository, repository or FakeHabitRepository()),
        gateway=cast(AIWorkerGateway, gateway),
    )


async def test_subtype_with_disease_subtype_uses_llm_generated_habits():
    """세부 진단명이 있으면 6개 broad 카테고리 기본 습관 대신, LLM이 한 번에 만든 습관 여러 개가
    들어가야 한다(진단 1개만 등록해도 그 질환 관련 습관으로 오늘의 추천을 채울 수 있게)."""
    subtype = FakeDiseaseSubtype(id=101, name="고혈압")
    entry = FakeDiagnosisEntry(disease=Disease.HEART_DISEASE, disease_subtype_id=101, disease_subtype=subtype)
    profile = FakeProfile(id=1, diagnosis_entries=[entry])
    gateway = FakeGateway(
        result=_habits_batch(
            ("저염식 30분 식사하기", "🥗", "회", 1),
            ("매일 30분 걷기", "🚶", "분", 30),
            ("혈압 체크하기", "🩺", "회", 1),
            ("금연 실천하기", "🚭", "회", 1),
            ("스트레스 줄이기", "🧘", "회", 1),
        )
    )
    service = _build_service(gateway)

    pool, _ = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    generated_keys = [h.key for h in pool if h.key.startswith("subtype_101_")]
    assert len(generated_keys) == 5
    first = next(h for h in pool if h.key == "subtype_101_0")
    assert first.label == "저염식 30분 식사하기"
    assert first.icon == "🥗"
    # broad 카테고리(심장질환) 기본 습관은 세부 진단명이 있을 때 안 섞여 들어가야 한다.
    assert DISEASE_HABITS[Disease.HEART_DISEASE].key not in [h.key for h in pool]


async def test_subtype_habits_are_cached_after_first_generation():
    """같은 세부 진단명으로 두 번 호출해도 LLM은 한 번만 불러야 한다(캐시 재사용)."""
    subtype = FakeDiseaseSubtype(id=202, name="협심증")
    entry = FakeDiagnosisEntry(disease=Disease.HEART_DISEASE, disease_subtype_id=202, disease_subtype=subtype)
    profile = FakeProfile(id=2, diagnosis_entries=[entry])
    gateway = FakeGateway(result=_habits_batch(("가슴 통증 기록하기", "📋", "회", 1)))
    repository = FakeHabitRepository()
    service = _build_service(gateway, repository)

    await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))
    await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    assert gateway.call_count == 1


async def test_subtype_habit_falls_back_to_disease_category_on_gateway_failure():
    """LLM 호출이 실패하면(ai_worker 무응답 등) 6개 broad 카테고리 기본 습관 1개로 대체돼야 한다."""
    subtype = FakeDiseaseSubtype(id=303, name="부정맥")
    entry = FakeDiagnosisEntry(disease=Disease.HEART_DISEASE, disease_subtype_id=303, disease_subtype=subtype)
    profile = FakeProfile(id=3, diagnosis_entries=[entry])
    gateway = FakeGateway(error=AIWorkerUnavailableError("ai_worker 연결 실패"))
    service = _build_service(gateway)

    pool, _ = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    keys = [h.key for h in pool]
    assert DISEASE_HABITS[Disease.HEART_DISEASE].key in keys
    assert not any(k.startswith("subtype_303_") for k in keys)


async def test_subtype_habits_sanitize_bad_llm_output():
    """LLM이 형식에 안 맞는 값(너무 긴 라벨, 빈 아이콘/단위, target<=0)을 줘도 안전한 값으로
    다듬어져야 한다."""
    subtype = FakeDiseaseSubtype(id=404, name="희귀질환")
    entry = FakeDiagnosisEntry(disease=Disease.OTHER, disease_subtype_id=404, disease_subtype=subtype)
    profile = FakeProfile(id=4, diagnosis_entries=[entry])
    gateway = FakeGateway(result=_habits_batch(("가" * 200, "", "", 0)))
    service = _build_service(gateway)

    pool, _ = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    generated = next(h for h in pool if h.key == "subtype_404_0")
    assert len(generated.label) <= 50
    assert generated.icon != ""
    assert generated.unit != ""
    assert generated.target >= 1


async def test_subtype_habits_capped_at_five_even_if_llm_returns_more():
    """LLM이 5개보다 많이 줘도 최대 5개까지만 저장/사용한다."""
    subtype = FakeDiseaseSubtype(id=505, name="다낭성난소증후군")
    entry = FakeDiagnosisEntry(disease=Disease.OTHER, disease_subtype_id=505, disease_subtype=subtype)
    profile = FakeProfile(id=5, diagnosis_entries=[entry])
    gateway = FakeGateway(
        result=_habits_batch(*[(f"습관{i}", "🙂", "회", 1) for i in range(8)]),
    )
    service = _build_service(gateway)

    pool, _ = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    generated_keys = [h.key for h in pool if h.key.startswith("subtype_505_")]
    assert len(generated_keys) == 5


async def test_different_subtypes_under_same_disease_both_kept():
    """같은 broad 카테고리라도 세부 진단명이 다르면(둘 다 등록된 경우) 둘 다 후보에 남아야 한다."""
    subtype_a = FakeDiseaseSubtype(id=601, name="협심증")
    subtype_b = FakeDiseaseSubtype(id=602, name="부정맥")
    entries = [
        FakeDiagnosisEntry(disease=Disease.HEART_DISEASE, disease_subtype_id=601, disease_subtype=subtype_a),
        FakeDiagnosisEntry(disease=Disease.HEART_DISEASE, disease_subtype_id=602, disease_subtype=subtype_b),
    ]
    profile = FakeProfile(id=6, diagnosis_entries=entries)
    gateway = FakeGateway(result=_habits_batch(("습관", "🙂", "회", 1)))
    service = _build_service(gateway)

    pool, _ = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    keys = [h.key for h in pool]
    assert any(k.startswith("subtype_601_") for k in keys)
    assert any(k.startswith("subtype_602_") for k in keys)


async def test_no_diagnosis_returns_base_habits_only():
    """진단이 하나도 없으면 build_full_pool은 BASE_HABITS만 그대로 반환해야 한다
    (질병 등록 시 기본 습관을 배제하는 분기와 대칭되는 반대쪽 분기)."""
    profile = FakeProfile(id=7, diagnosis_entries=[])
    gateway = FakeGateway(error=AssertionError("진단이 없으면 AI 게이트웨이를 호출하면 안 된다"))
    service = _build_service(gateway)

    pool, habit_to_disease = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    assert pool == list(BASE_HABITS)
    assert habit_to_disease == {}
    assert gateway.call_count == 0


def _habit(key: str, label: str) -> HabitDef:
    return HabitDef(key=key, label=label, icon="🙂", unit="회", target=1, is_disease_related=True)


def test_pick_recommendations_multi_disease_dedupes_by_label():
    """서로 다른 질병에서 나온 습관이라도 라벨(이름)이 같으면 최종 추천에는 한 번만 남아야
    한다 - "같은 습관, 다른 질병"으로 중복 추천되던 문제의 회귀 테스트."""
    pool = [
        _habit("diabetes_walk", "산책 20분"),
        _habit("heart_walk", "산책 20분"),  # 당뇨 습관과 라벨이 동일 -> 중복 제거 대상
        _habit("heart_low_salt", "저염식 식사하기"),
    ]
    habit_to_disease = {
        "diabetes_walk": Disease.DIABETES,
        "heart_walk": Disease.HEART_DISEASE,
        "heart_low_salt": Disease.HEART_DISEASE,
    }

    result = pick_recommendations(pool, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease)

    labels = [h.label for h in result]
    assert labels.count("산책 20분") == 1


def test_pick_recommendations_multi_disease_picks_at_least_one_per_disease():
    """질병이 여러 개면 각 질병에서 최소 1개씩은 추천에 포함돼야 한다."""
    pool = [
        _habit("diabetes_walk", "혈당 체크하기"),
        _habit("heart_low_salt", "저염식 식사하기"),
        _habit("cancer_rest", "충분한 휴식 취하기"),
    ]
    habit_to_disease = {
        "diabetes_walk": Disease.DIABETES,
        "heart_low_salt": Disease.HEART_DISEASE,
        "cancer_rest": Disease.CANCER,
    }

    result = pick_recommendations(pool, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease)

    keys = {h.key for h in result}
    assert {"diabetes_walk", "heart_low_salt", "cancer_rest"} <= keys


def test_pick_recommendations_caps_at_max_recommendations():
    """다중 질병이라도 최종 추천 개수는 MAX_RECOMMENDATIONS(5)를 넘지 않아야 한다."""
    pool = [_habit(f"d{i}_habit{j}", f"습관{i}-{j}") for i in range(3) for j in range(4)]
    habit_to_disease = {
        f"d{i}_habit{j}": [Disease.DIABETES, Disease.HEART_DISEASE, Disease.CANCER][i]
        for i in range(3)
        for j in range(4)
    }

    result = pick_recommendations(pool, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease)

    assert len(result) <= MAX_RECOMMENDATIONS


def test_generate_detailed_reason_differs_by_disease_for_same_habit_label():
    """같은 습관 라벨이라도 질병이 다르면 서로 다른 추천 이유 문구가 나와야 한다
    (질병×키워드별 세분화 로직의 핵심 동작)."""
    service = _build_service(FakeGateway())

    diabetes_reason = service._generate_detailed_reason(Disease.DIABETES, "산책 20분")
    liver_reason = service._generate_detailed_reason(Disease.LIVER_DISEASE, "산책 20분")

    assert diabetes_reason != liver_reason
    assert "당뇨" in diabetes_reason
    assert "간" in liver_reason


def test_generate_detailed_reason_has_fallback_for_unmatched_keyword():
    """습관 라벨이 질병별 키워드 사전에 없는 임의 문자열이어도 빈 문자열이 아닌 폴백 문구를
    반환해야 한다."""
    service = _build_service(FakeGateway())

    reason = service._generate_detailed_reason(Disease.OTHER, "전혀 매칭되지 않는 임의의 습관 이름")

    assert reason != ""
