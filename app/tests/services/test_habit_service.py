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


@dataclass
class FakeEntrySuggestionRow:
    diagnosis_entry_id: int
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
        self._entry_suggestions: dict[int, list[FakeEntrySuggestionRow]] = {}

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

    async def list_entry_suggestions(self, session: Any, diagnosis_entry_id: int) -> list[FakeEntrySuggestionRow]:
        return self._entry_suggestions.get(diagnosis_entry_id, [])

    async def save_entry_suggestions(
        self, diagnosis_entry_id: int, suggestions: list[dict]
    ) -> list[FakeEntrySuggestionRow]:
        rows = [
            FakeEntrySuggestionRow(diagnosis_entry_id=diagnosis_entry_id, slot=slot, **suggestion)
            for slot, suggestion in enumerate(suggestions)
        ]
        self._entry_suggestions[diagnosis_entry_id] = rows
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
    fallback_keys = {h.key for h in DISEASE_HABITS[Disease.HEART_DISEASE]}
    assert fallback_keys.isdisjoint({h.key for h in pool})


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
    """LLM 호출이 (세부진단명/자유텍스트 경로 둘 다) 실패하면 카테고리 폴백 습관 5개로
    대체돼야 한다(질병 1개 등록 시 "습관 3개(랜덤)"를 뽑을 수 있으려면 이 폴백도 5개는
    있어야 한다)."""
    subtype = FakeDiseaseSubtype(id=303, name="부정맥")
    entry = FakeDiagnosisEntry(disease=Disease.HEART_DISEASE, disease_subtype_id=303, disease_subtype=subtype)
    profile = FakeProfile(id=3, diagnosis_entries=[entry])
    gateway = FakeGateway(error=AIWorkerUnavailableError("ai_worker 연결 실패"))
    service = _build_service(gateway)

    pool, _ = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    keys = [h.key for h in pool]
    assert len(DISEASE_HABITS[Disease.HEART_DISEASE]) == 5
    assert all(h.key in keys for h in DISEASE_HABITS[Disease.HEART_DISEASE])
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


async def test_freetext_entry_without_subtype_uses_llm_generated_habits():
    """세부 진단명이 없어도(자유텍스트 detail만 있어도) LLM이 생성한 습관이 들어가야 한다."""
    entry = FakeDiagnosisEntry(disease=Disease.DIABETES, id=701, detail="가족력 있음, 최근 혈당 불안정")
    profile = FakeProfile(id=8, diagnosis_entries=[entry])
    gateway = FakeGateway(
        result=_habits_batch(
            ("혈당 체크하기", "🩸", "회", 1),
            ("당분 줄이기", "🍬", "회", 1),
            ("가벼운 운동하기", "🚶", "분", 20),
            ("규칙적 식사", "🍚", "회", 3),
            ("스트레스 관리", "🧘", "회", 1),
        )
    )
    service = _build_service(gateway)

    pool, habit_to_disease = await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    generated_keys = [h.key for h in pool if h.key.startswith("detail_701_")]
    assert len(generated_keys) == 5
    first = next(h for h in pool if h.key == "detail_701_0")
    assert first.label == "혈당 체크하기"
    assert habit_to_disease["detail_701_0"] == Disease.DIABETES


async def test_freetext_entry_habits_are_cached_after_first_generation():
    """세부 진단명 없는 자유텍스트 진단도 두 번 호출하면 LLM은 한 번만 불러야 한다(캐시 재사용).

    캐싱이 없으면 매 요청(오늘의 추천 조회/습관 선택/체크)마다 LLM을 다시 불러서, 방금 선택한
    습관이 다음 조회에서 사라지거나 키가 바뀔 수 있다(2026-08-05 발견한 버그의 회귀 테스트)."""
    entry = FakeDiagnosisEntry(disease=Disease.OTHER, id=702, detail="회복 중")
    profile = FakeProfile(id=9, diagnosis_entries=[entry])
    gateway = FakeGateway(result=_habits_batch(("컨디션 기록하기", "📝", "회", 1)))
    repository = FakeHabitRepository()
    service = _build_service(gateway, repository)

    await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))
    await service.build_full_pool(cast(AsyncSession, None), cast(Profile, profile))

    assert gateway.call_count == 1


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


def test_pick_recommendations_no_disease_rotates_base_habits():
    """질병이 없으면(habit_to_disease가 비어있으면) BASE_HABITS만 매일 회전해서 5개 나와야 한다."""
    result = pick_recommendations(list(BASE_HABITS), profile_id=1, today=date(2026, 1, 1), habit_to_disease={})

    assert len(result) == MAX_RECOMMENDATIONS
    assert all(h in BASE_HABITS for h in result)


def test_pick_recommendations_single_disease_mixes_three_disease_and_two_base():
    """질병이 1개면 등록된 습관 중 3개 + 기본 습관(BASE_HABITS) 2개로 구성돼야 한다."""
    disease_habits = [_habit(f"diabetes_h{i}", f"당뇨습관{i}") for i in range(5)]
    habit_to_disease = {h.key: Disease.DIABETES for h in disease_habits}

    result = pick_recommendations(
        disease_habits, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease
    )

    assert len(result) == MAX_RECOMMENDATIONS
    from_disease = [h for h in result if h.key.startswith("diabetes_h")]
    from_base = [h for h in result if h in BASE_HABITS]
    assert len(from_disease) == 3
    assert len(from_base) == 2


def test_pick_recommendations_single_disease_is_deterministic_per_profile_and_day():
    """같은 (profile_id, 날짜)로 여러 번 호출해도 항상 같은 5개가 나와야 한다 - 그렇지 않으면
    추천 조회(GET) 이후 선택 검증(POST)에서 방금 본 습관이 유효하지 않다고 튕겨날 수 있다."""
    disease_habits = [_habit(f"diabetes_h{i}", f"당뇨습관{i}") for i in range(5)]
    habit_to_disease = {h.key: Disease.DIABETES for h in disease_habits}

    first = pick_recommendations(
        disease_habits, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease
    )
    second = pick_recommendations(
        disease_habits, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease
    )

    assert [h.key for h in first] == [h.key for h in second]


def test_pick_recommendations_multi_disease_excludes_base_habits():
    """질병이 2개 이상이면 BASE_HABITS는 섞이지 않고 등록된 질병 습관만으로 5개가 나와야 한다."""
    pool = [_habit(f"d{i}_h{j}", f"습관{i}-{j}") for i in range(2) for j in range(5)]
    habit_to_disease = {f"d{i}_h{j}": [Disease.DIABETES, Disease.HEART_DISEASE][i] for i in range(2) for j in range(5)}

    result = pick_recommendations(pool, profile_id=1, today=date(2026, 1, 1), habit_to_disease=habit_to_disease)

    assert len(result) == MAX_RECOMMENDATIONS
    assert not any(h in BASE_HABITS for h in result)


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
