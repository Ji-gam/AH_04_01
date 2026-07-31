import logging
from dataclasses import dataclass
from datetime import date
from typing import cast

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.habit import (
    HabitItemResponse,
    HabitRecommendationItem,
    HabitRecommendationsResponse,
    HabitsTodayResponse,
)
from app.models.disease_entries import DiseaseSubtype
from app.models.profiles import Disease, Profile
from app.repositories.habit_repository import HabitRepository
from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.push_service import PushService

logger = logging.getLogger("app.habit_service")

# 몇 개까지 고를 수 있는지는 app/dtos/habit.py의 HabitSelectionRequest.habit_keys(max_length=5)가
# 강제한다 - 여기서는 "추천을 몇 개까지 보여줄지"만 다룬다. 팀 논의로 선택 가능 개수와 맞춰
# 5개로 통일(전에는 10개 중 5개 선택 - "왜 10개나 보여주고 5개만 고르게 하냐"는 피드백 반영).
MAX_RECOMMENDATIONS = 5


@dataclass(frozen=True)
class HabitDef:
    key: str
    label: str
    icon: str
    unit: str
    target: int
    # 진단병력에서 나온 맞춤 습관인지 - pick_recommendations()가 이 값으로 질병 관련 습관을
    # 우선 채운다(일반 라이프스타일 습관보다 먼저 보여줘야 한다는 요청, 2026-07-29).
    is_disease_related: bool = False


# 등록 여부와 무관하게 누구에게나 뜨는 기본 세트(디자인 시안 반영, 8개). 진단명을 적게(또는
# 하나도) 등록하지 않은 사람도 항상 MAX_RECOMMENDATIONS(5)개를 채울 수 있게 하려고, 질환 유무와
# 무관한 일반 라이프스타일 습관을 넉넉히 둔다 - 예전엔 기본 2개뿐이라 진단을 1개만 등록하면
# 추천이 2~3개밖에 안 뜨는 문제가 있었다.
BASE_HABITS: list[HabitDef] = [
    HabitDef(key="water", label="물 2L 마시기", icon="🥤", unit="잔", target=8),
    HabitDef(key="walk", label="산책 20분", icon="🚶", unit="분", target=20),
    HabitDef(key="reading", label="10분 독서하기", icon="📖", unit="분", target=10),
    HabitDef(key="morning_stretch", label="아침 스트레칭", icon="🧘", unit="회", target=1),
    HabitDef(key="early_sleep", label="일찍 자기 (11시 전)", icon="🌙", unit="회", target=1),
    HabitDef(key="gratitude_journal", label="감사일기 쓰기", icon="✍️", unit="회", target=1),
    HabitDef(key="phone_free_meal", label="핸드폰 없이 식사하기", icon="📵", unit="회", target=1),
    HabitDef(key="three_meals", label="하루 3끼 챙겨먹기", icon="🍚", unit="회", target=1),
]

# 질병별 커스텀 기본 습관 - 질병이 등록되면 일반 BASE_HABITS 대신 질병별 습관을 사용
DISEASE_BASE_HABITS: dict[Disease, list[HabitDef]] = {
    Disease.DIABETES: [
        HabitDef(key="water", label="물 2L 마시기", icon="🥤", unit="잔", target=8),
        HabitDef(key="walk", label="산책 20분", icon="🚶", unit="분", target=20),
        HabitDef(key="early_sleep", label="일찍 자기 (11시 전)", icon="🌙", unit="회", target=1),
        HabitDef(key="three_meals", label="하루 3끼 챙겨먹기", icon="🍚", unit="회", target=1),
    ],
    Disease.HEART_DISEASE: [
        HabitDef(key="walk", label="산책 20분", icon="🚶", unit="분", target=20),
        HabitDef(key="early_sleep", label="일찍 자기 (11시 전)", icon="🌙", unit="회", target=1),
        HabitDef(key="gratitude_journal", label="감사일기 쓰기", icon="✍️", unit="회", target=1),
        HabitDef(key="phone_free_meal", label="핸드폰 없이 식사하기", icon="📵", unit="회", target=1),
    ],
    Disease.CEREBROVASCULAR_DISEASE: [
        HabitDef(key="walk", label="산책 20분", icon="🚶", unit="분", target=20),
        HabitDef(key="morning_stretch", label="아침 스트레칭", icon="🧘", unit="회", target=1),
        HabitDef(key="reading", label="10분 독서하기", icon="📖", unit="분", target=10),
        HabitDef(key="early_sleep", label="일찍 자기 (11시 전)", icon="🌙", unit="회", target=1),
    ],
    Disease.LIVER_DISEASE: [
        HabitDef(key="water", label="물 2L 마시기", icon="🥤", unit="잔", target=8),
        HabitDef(key="gratitude_journal", label="감사일기 쓰기", icon="✍️", unit="회", target=1),
        HabitDef(key="early_sleep", label="일찍 자기 (11시 전)", icon="🌙", unit="회", target=1),
        HabitDef(key="three_meals", label="하루 3끼 챙겨먹기", icon="🍚", unit="회", target=1),
    ],
    Disease.CANCER: [
        HabitDef(key="early_sleep", label="일찍 자기 (11시 전)", icon="🌙", unit="회", target=1),
        HabitDef(key="gratitude_journal", label="감사일기 쓰기", icon="✍️", unit="회", target=1),
        HabitDef(key="morning_stretch", label="아침 스트레칭", icon="🧘", unit="회", target=1),
    ],
}

# 진단병력(Disease)에 등록된 질환마다 하나씩 추가되는 기본 맞춤 습관 - 세부 진단명(subtype)이
# 없거나, 있어도 LLM 생성이 실패했을 때의 폴백으로 쓰인다(2단계 이후에는 항상 이게 최종
# 폴백이라, 이 6개는 계속 유지한다).
DISEASE_HABITS: dict[Disease, HabitDef] = {
    Disease.DIABETES: HabitDef(
        key="diabetes_walk", label="식후 10분 걷기", icon="🍽️", unit="회", target=1, is_disease_related=True
    ),
    Disease.HEART_DISEASE: HabitDef(
        key="heart_low_salt", label="저염식 식사하기", icon="🧂", unit="회", target=1, is_disease_related=True
    ),
    Disease.CEREBROVASCULAR_DISEASE: HabitDef(
        key="cerebro_stretch", label="스트레칭 5분", icon="🧘", unit="회", target=1, is_disease_related=True
    ),
    Disease.LIVER_DISEASE: HabitDef(
        key="liver_no_alcohol", label="금주 실천하기", icon="🚫", unit="회", target=1, is_disease_related=True
    ),
    Disease.CANCER: HabitDef(
        key="cancer_rest", label="충분한 휴식 취하기", icon="😴", unit="회", target=1, is_disease_related=True
    ),
    Disease.OTHER: HabitDef(
        key="other_condition_check",
        label="오늘 컨디션 체크하기",
        icon="📝",
        unit="회",
        target=1,
        is_disease_related=True,
    ),
}


class SubtypeHabitSuggestion(BaseModel):
    """습관 하나의 구조."""

    label: str
    icon: str
    unit: str
    target: int


class SubtypeHabitSuggestionBatch(BaseModel):
    """AIWorkerGateway.call_structured()가 채워야 하는 구조 - 진단명 하나에 습관 여러 개(최대 5개).
    진단이 1개뿐이어도 그 질환 관련 습관으로 오늘의 추천(MAX_RECOMMENDATIONS=5)을 채울 수 있게
    하려고 한 번에 5개를 생성한다(팀 피드백: "질병 하나만 등록해도 그 질병 관련으로 5개
    채워주면 좋겠다")."""

    habits: list[SubtypeHabitSuggestion]


_SUBTYPE_HABITS_PER_DIAGNOSIS = 5

_SUBTYPE_HABIT_SYSTEM_PROMPT = (
    "당신은 건강관리 앱의 습관 추천 도우미입니다. 주어진 진단명에 맞는 짧고 실천 가능한 "
    f"하루 습관을 서로 다른 {_SUBTYPE_HABITS_PER_DIAGNOSIS}개 만드세요.\n"
    "- label: 10자 내외, 행동 중심 (예: '저염식 30분 식사하기')\n"
    "- icon: 이모지 1개\n"
    "- unit: '회'/'잔'/'분' 등 짧은 단위\n"
    "- target: 보통 1(하루 목표 횟수), 필요하면 다른 값도 가능\n"
    f"{_SUBTYPE_HABITS_PER_DIAGNOSIS}개는 서로 겹치지 않는 다른 행동이어야 합니다. "
    "위험하거나 의학적으로 부적절한 습관(예: 약 복용 중단, 자가진단, 자가치료)은 절대 "
    "추천하지 마세요."
)

# 각 습관과 질병별 추천 이유 매핑
_HABIT_DISEASE_EXPLANATIONS: dict[str, dict[Disease, str]] = {
    "water": {
        Disease.DIABETES: "당뇨병 관리를 위해 수분 섭취가 중요합니다",
        Disease.HEART_DISEASE: "심장 건강 유지를 위해 규칙적인 수분 섭취가 중요합니다",
    },
    "walk": {
        Disease.DIABETES: "당뇨병 혈당 조절에 효과적한 유산소 운동입니다",
        Disease.HEART_DISEASE: "심장 건강 개선을 위한 가벼운 운동입니다",
        Disease.CEREBROVASCULAR_DISEASE: "뇌혈관 건강을 위한 혈류 개선 운동입니다",
    },
    "reading": {
        Disease.CEREBROVASCULAR_DISEASE: "뇌 건강과 집중력 향상에 도움이 됩니다",
    },
    "morning_stretch": {
        Disease.DIABETES: "당뇨병 관리를 위해 스트레스 감소가 중요합니다",
        Disease.CEREBROVASCULAR_DISEASE: "혈류 개선과 근육 유연성 향상에 도움이 됩니다",
    },
    "early_sleep": {
        Disease.DIABETES: "당뇨병 관리를 위해 충분한 수면이 필수입니다",
        Disease.HEART_DISEASE: "심장 부하 감소를 위해 규칙적인 수면이 중요합니다",
    },
    "gratitude_journal": {
        Disease.DIABETES: "당뇨병 관리를 위해 스트레스 관리가 필수입니다",
        Disease.CEREBROVASCULAR_DISEASE: "정신 건강 개선으로 혈압 안정화에 도움이 됩니다",
    },
    "phone_free_meal": {
        Disease.DIABETES: "당뇨병 관리를 위해 정신 집중과 천천한 식사가 중요합니다",
    },
    "three_meals": {
        Disease.DIABETES: "당뇨병 관리를 위해 규칙적인 식사 시간이 필수입니다",
    },
    "diabetes_walk": {
        Disease.DIABETES: "식후 혈당 상승 억제에 가장 효과적한 운동입니다",
    },
    "heart_low_salt": {
        Disease.HEART_DISEASE: "심장질환 관리의 핵심 요소입니다",
    },
    "cerebro_stretch": {
        Disease.CEREBROVASCULAR_DISEASE: "혈류 개선과 뇌졸중 예방에 도움이 됩니다",
    },
    "liver_no_alcohol": {
        Disease.LIVER_DISEASE: "간질환 관리의 필수 요소입니다",
    },
    "cancer_rest": {
        Disease.CANCER: "암 치료 중 회복과 면역력 강화에 중요합니다",
    },
    "other_condition_check": {
        Disease.OTHER: "건강 변화를 정기적으로 모니터링하세요",
    },
}


def _rotate(items: list[HabitDef], profile_id: int, today: date, count: int) -> list[HabitDef]:
    """items에서 count개를, 날짜가 하루 지날 때마다 정확히 한 칸씩 미는 방식으로 고른다.
    profile_id를 더해 계정마다 시작 위치가 달라지되, 요일 간 회전 자체는 늘 +1이라 "우연히
    며칠 연속 같은 결과가 나오는" 문제(해시 나머지 방식의 알려진 결함)가 구조적으로 없다."""
    if not items:
        return []
    start = (today.toordinal() + profile_id) % len(items)
    return [items[(start + i) % len(items)] for i in range(count)]


def pick_recommendations(
    pool: list[HabitDef], profile_id: int, today: date, habit_to_disease: dict[str, Disease] | None = None
) -> list[HabitDef]:
    """진단병력 기반 맞춤 습관(is_disease_related)을 일반 라이프스타일 습관보다 항상 먼저
    채운다("습관 리스트는 질병 관련부터 보여줘야 한다", 2026-07-29).

    질병이 여러 개일 경우 각 질병에서 최소 1개씩 선택하도록 개선됨(2026-07-31).
    질병 관련 습관만으로 MAX_RECOMMENDATIONS를 못 채우면 남는 자리만 일반 습관으로(날짜별 로테이션) 메운다.
    """
    disease_habits = [h for h in pool if h.is_disease_related]
    base_habits = [h for h in pool if not h.is_disease_related]

    # habit_to_disease가 제공되지 않으면 기존 로직 사용
    if habit_to_disease is None or not disease_habits:
        if len(pool) <= MAX_RECOMMENDATIONS:
            return disease_habits + base_habits

        if len(disease_habits) >= MAX_RECOMMENDATIONS:
            return _rotate(disease_habits, profile_id, today, MAX_RECOMMENDATIONS)

        remaining = MAX_RECOMMENDATIONS - len(disease_habits)
        return disease_habits + _rotate(base_habits, profile_id, today, remaining)

    # 질병별로 습관 분류
    habits_by_disease: dict[Disease, list[HabitDef]] = {}
    for h in disease_habits:
        if h.key in habit_to_disease:
            disease = habit_to_disease[h.key]
            if disease not in habits_by_disease:
                habits_by_disease[disease] = []
            habits_by_disease[disease].append(h)

    # 질병이 여러 개인 경우: 각 질병에서 최소 1개씩 선택
    result = []
    selected_labels: set[str] = set()  # 이미 선택된 습관 라벨(이름) 추적 - AI 생성 습관은 키가 다르므로 라벨로 중복 제거
    if len(habits_by_disease) > 1:
        for disease, disease_habits_list in habits_by_disease.items():
            selected = _rotate(disease_habits_list, profile_id, today, 1)
            result.extend(selected)
            for h in selected:
                selected_labels.add(h.label)

        # 남은 자리 채우기 - 중복된 습관 라벨은 제외
        remaining = MAX_RECOMMENDATIONS - len(result)
        if remaining > 0:
            all_disease_habits = [h for dh_list in habits_by_disease.values() for h in dh_list]
            # 이미 선택된 라벨을 제외한 후보들만 사용 (같은 이름의 습관 중복 방지)
            all_candidates = [h for h in all_disease_habits if h.label not in selected_labels]
            if all_candidates:
                extra = _rotate(all_candidates, profile_id, today, remaining)
                result.extend(extra)
                for h in extra:
                    selected_labels.add(h.label)
    else:
        # 질병이 1개인 경우: 기존 로직 - 질병이 있으면 기본 습관은 제외
        if len(disease_habits) >= MAX_RECOMMENDATIONS:
            return _rotate(disease_habits, profile_id, today, MAX_RECOMMENDATIONS)

        # 질병 관련 습관만으로 pool을 채운다 (기본 습관 제외)
        return disease_habits[:MAX_RECOMMENDATIONS]

    # 라벨 기준 중복 제거하되, 최종 5개가 되도록 유지
    seen_labels: set[str] = set()
    deduped_result = []

    # result에서 라벨 중복 제거
    for h in result:
        if h.label not in seen_labels:
            deduped_result.append(h)
            seen_labels.add(h.label)

    # 중복 제거 후 5개보다 부족하면 추가 습관으로 채우기
    if len(deduped_result) < MAX_RECOMMENDATIONS:
        remaining_needed = MAX_RECOMMENDATIONS - len(deduped_result)

        # 아직 선택되지 않은 습관들 중 라벨이 중복되지 않은 것들 가져오기
        if len(habits_by_disease) > 1:
            # result에 포함된 라벨들
            result_labels = {h.label for h in result}

            # 모든 질병의 습관들 중 아직 사용되지 않은 것들
            unused_habits = []
            for h in [h for dh_list in habits_by_disease.values() for h in dh_list]:
                if h.label not in seen_labels:
                    unused_habits.append(h)

            # 미사용 습관들 중에서 추가로 선택 (라벨 중복 피함)
            for h in unused_habits:
                if len(deduped_result) >= MAX_RECOMMENDATIONS:
                    break
                if h.label not in seen_labels:
                    deduped_result.append(h)
                    seen_labels.add(h.label)

    return deduped_result[:MAX_RECOMMENDATIONS]


class HabitService:
    def __init__(
        self,
        repository: HabitRepository | None = None,
        gateway: AIWorkerGateway | None = None,
        push_service: PushService | None = None,
    ) -> None:
        self._repository = repository or HabitRepository()
        self._gateway = gateway or AIWorkerGateway()
        self._push_service = push_service or PushService()

    async def build_full_pool(self, session: AsyncSession, profile: Profile) -> tuple[list[HabitDef], dict[str, Disease]]:
        """가능한 전체 습관 후보 생성 로직.

        [설계]
        1. 질병 미등록: BASE_HABITS만 반환
        2. 질병 등록: 기본 습관은 제외하고, AI가 등록된 모든 질병 정보를 기반으로 생성한 습관만 반환
           - 각 진단에서 모든 정보(질환명, 상세메모, 경과년수, 조절상태, 약물치료) 수집
           - AI에 이 모든 정보를 전달해서 맞춤 습관 생성
        3. 여러 질병: 모든 질병의 AI 생성 습관을 함께 pool에 포함

        Returns: (pool, habit_to_disease) - 습관 목록과 각 습관이 어떤 질병에 해당하는지의 매핑
        """
        habit_to_disease: dict[str, Disease] = {}

        # 질병이 없으면 기본 추천만
        if not profile.diagnosis_entries:
            return list(BASE_HABITS), habit_to_disease

        # 질병이 있으면 기본 습관은 제외, 각 질병별 AI 생성 습관만 pool에 추가
        pool: list[HabitDef] = []
        seen: set[int | Disease] = set()

        for entry in profile.diagnosis_entries:
            dedupe_key: int | Disease = entry.disease_subtype_id or entry.disease
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            habit_defs: list[HabitDef] = []

            # 1단계: 세부 진단명이 있으면 그것을 사용
            if entry.disease_subtype is not None:
                habit_defs = await self._get_subtype_habits(session, entry.disease_subtype)

            # 2단계: 세부 진단명이 없으면 상세 메모(detail)와 모든 정보를 함께 AI에 전송
            if not habit_defs:
                habit_defs = await self._generate_habits_from_diagnosis_entry(entry)

            # 3단계: 위 모두 실패하면 기본 카테고리 폴백 습관 사용
            if not habit_defs:
                fallback = DISEASE_HABITS.get(entry.disease)
                habit_defs = [fallback] if fallback else []

            # 각 습관과 질병의 관계를 기록
            for h in habit_defs:
                habit_to_disease[h.key] = entry.disease

            pool.extend(habit_defs)

        return pool, habit_to_disease

    async def _generate_habits_from_diagnosis_entry(self, entry) -> list[HabitDef]:
        """진단 항목의 모든 정보(질환명, 상세메모, 경과, 조절상태, 약물치료)를 기반으로 AI 습관 생성."""
        try:
            # 진단 정보를 모두 포함한 프롬프트 작성
            diagnosis_info = self._format_diagnosis_info(entry)

            raw_result = await self._gateway.call_structured(
                system_prompt=_SUBTYPE_HABIT_SYSTEM_PROMPT,
                user_input=diagnosis_info,
                schema=SubtypeHabitSuggestionBatch,
            )
            result = cast(SubtypeHabitSuggestionBatch, raw_result)
            sanitized = [
                {
                    "label": habit.label.strip()[:50] or "오늘 컨디션 체크하기",
                    "icon": (habit.icon.strip() or "📝")[:10],
                    "unit": (habit.unit.strip() or "회")[:20],
                    "target": max(1, habit.target),
                }
                for habit in result.habits[:_SUBTYPE_HABITS_PER_DIAGNOSIS]
            ]
            if sanitized:
                return [
                    HabitDef(
                        key=f"detail_{entry.id}_{idx}",
                        label=h_dict["label"],
                        icon=h_dict["icon"],
                        unit=h_dict["unit"],
                        target=h_dict["target"],
                        is_disease_related=True,
                    )
                    for idx, h_dict in enumerate(sanitized)
                ]
        except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError):
            pass

        return []

    def _format_diagnosis_info(self, entry) -> str:
        """진단 정보를 AI가 이해하기 쉬운 형식으로 포맷."""
        info_parts = []

        # 질병 정보
        if entry.disease_subtype:
            info_parts.append(f"진단명: {entry.disease_subtype.name}")
        else:
            info_parts.append(f"질병 대분류: {entry.disease.value}")

        # 상세 메모
        if entry.detail:
            info_parts.append(f"상세정보: {entry.detail}")

        # 진단 후 경과
        if entry.diagnosed_years_ago is not None:
            info_parts.append(f"진단 후 경과: {entry.diagnosed_years_ago}년")

        # 조절 상태
        if entry.status:
            status_text = {
                "WELL_CONTROLLED": "잘 조절됨",
                "MODERATE": "보통",
                "UNCONTROLLED": "조절 안됨",
                "CURED": "완치",
            }.get(entry.status.value, entry.status.value)
            info_parts.append(f"조절상태: {status_text}")

        # 약물 치료
        if entry.on_medication is not None:
            med_text = "약물 치료 중" if entry.on_medication else "약물 치료 안함"
            info_parts.append(med_text)

        return "\n".join(info_parts)

    async def _get_subtype_habits(self, session: AsyncSession, subtype: DiseaseSubtype) -> list[HabitDef]:
        cached = await self._repository.list_subtype_suggestions(session, subtype.id)
        if cached:
            return [
                HabitDef(
                    key=f"subtype_{row.disease_subtype_id}_{row.slot}",
                    label=row.label,
                    icon=row.icon,
                    unit=row.unit,
                    target=row.target,
                    is_disease_related=True,
                )
                for row in cached
            ]

        try:
            raw_result = await self._gateway.call_structured(
                system_prompt=_SUBTYPE_HABIT_SYSTEM_PROMPT,
                user_input=f"진단명: {subtype.name}",
                schema=SubtypeHabitSuggestionBatch,
            )
        except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
            logger.warning(f"진단명 '{subtype.name}' 습관 생성 실패, 기본 카테고리 습관으로 대체합니다: {e}")
            return []

        result = cast(SubtypeHabitSuggestionBatch, raw_result)
        # LLM 출력은 형식/개수가 기대와 다를 수 있어 그대로 믿지 않고 방어적으로 다듬는다.
        sanitized = [
            {
                "label": habit.label.strip()[:50] or "오늘 컨디션 체크하기",
                "icon": (habit.icon.strip() or "📝")[:10],
                "unit": (habit.unit.strip() or "회")[:20],
                "target": max(1, habit.target),
            }
            for habit in result.habits[:_SUBTYPE_HABITS_PER_DIAGNOSIS]
        ]
        if not sanitized:
            return []

        saved = await self._repository.save_subtype_suggestions(subtype.id, sanitized)
        return [
            HabitDef(
                key=f"subtype_{row.disease_subtype_id}_{row.slot}",
                label=row.label,
                icon=row.icon,
                unit=row.unit,
                target=row.target,
                is_disease_related=True,
            )
            for row in saved
        ]

    async def get_recommendations(self, session: AsyncSession, profile: Profile) -> HabitRecommendationsResponse:
        today = date.today()

        # DEBUG: 진단 정보 로깅
        if profile.diagnosis_entries:
            print(f"\n=== 진단 정보 (프로필 {profile.id}) ===")
            for entry in profile.diagnosis_entries:
                print(f"- 질병: {entry.disease.value}, 세부: {entry.disease_subtype.name if entry.disease_subtype else 'None'}, 상세: {entry.detail}")
            print(f"총 {len(profile.diagnosis_entries)}개 진단\n")

        full_pool, habit_to_disease = await self.build_full_pool(session, profile)
        pool = pick_recommendations(full_pool, profile.id, today, habit_to_disease)
        valid_keys = {h.key for h in pool}
        selected_keys = await self._repository.list_selected_keys(session, profile.id, today)

        # DEBUG: 추천 습관 로깅
        print(f"\n=== 추천 습관 ({len(pool)}개) ===")
        for i, h in enumerate(pool, 1):
            disease = habit_to_disease.get(h.key, "None")
            print(f"{i}. {h.label} (키: {h.key}, 질병: {disease}, is_disease_related: {h.is_disease_related})")
        print()

        # 사용자의 진단 정보 수집
        user_diseases = {entry.disease for entry in (profile.diagnosis_entries or [])}
        subtypes_by_id = {
            entry.disease_subtype_id: entry.disease_subtype
            for entry in (profile.diagnosis_entries or [])
            if entry.disease_subtype_id
        }
        subtype_id_to_disease = {
            entry.disease_subtype_id: entry.disease
            for entry in (profile.diagnosis_entries or [])
            if entry.disease_subtype_id
        }

        # 각 습관별 추천 이유 생성
        habits_with_reasons = []
        for h in pool:
            reason = None
            if h.is_disease_related:
                reason = self._generate_habit_reason(
                    h.key, user_diseases, subtype_id_to_disease, h.label, habit_to_disease
                )

            habits_with_reasons.append(
                HabitRecommendationItem(
                    key=h.key, label=h.label, icon=h.icon, unit=h.unit, target=h.target, reason=reason
                )
            )

        return HabitRecommendationsResponse(
            habits=habits_with_reasons,
            # 세부 진단명이 새로 캐시되는 등 풀이 바뀌면 예전 선택 키가 오늘 풀엔 없을 수 있다
            # (예: cerebro_stretch로 선택해뒀는데 이후 subtype_20 습관으로 대체된 경우). 그런
            # 유령 키를 그대로 내려주면 프론트가 "선택됨"으로 상태를 만들고, 저장 시 그 키를
            # 그대로 다시 보내 select_habits()의 유효성 검사(400)에 걸린다 - 오늘 실제로 고를 수
            # 있는 키만 내려서 애초에 이 문제가 생기지 않게 한다.
            selected_keys=[key for key in selected_keys if key in valid_keys],
        )

    def _generate_habit_reason(
        self, habit_key: str, user_diseases: set[Disease], subtype_id_to_disease: dict[int, Disease],
        habit_label: str = "", habit_to_disease: dict[str, Disease] | None = None
    ) -> str | None:
        """습관 키와 사용자의 질병을 바탕으로 추천 이유 생성."""
        explanations = _HABIT_DISEASE_EXPLANATIONS.get(habit_key, {})

        # 사용자의 진단명 중 이 습관에 해당하는 설명이 있는지 확인
        for disease in user_diseases:
            if disease in explanations:
                return explanations[disease]

        # 세부 진단명 기반 습관의 경우 (subtype_*_* 형식)
        if habit_key.startswith("subtype_"):
            parts = habit_key.split("_")
            if len(parts) >= 2:
                try:
                    subtype_id = int(parts[1])
                    disease = subtype_id_to_disease.get(subtype_id)
                    if disease:
                        return self._generate_detailed_reason(disease, habit_label)
                except (ValueError, IndexError):
                    pass

        # AI 생성 습관의 경우 (detail_*_* 또는 다른 AI 생성 습관)
        if habit_to_disease and habit_key in habit_to_disease:
            disease = habit_to_disease[habit_key]
            return self._generate_detailed_reason(disease, habit_label)

        return None

    def _generate_detailed_reason(self, disease: Disease, habit_label: str) -> str:
        """습관 레이블과 질병을 기반으로 구체적인 추천 이유를 생성."""
        disease_names = {
            Disease.DIABETES: "당뇨병",
            Disease.HEART_DISEASE: "심장질환",
            Disease.CEREBROVASCULAR_DISEASE: "뇌혈관질환",
            Disease.LIVER_DISEASE: "간질환",
            Disease.CANCER: "암",
            Disease.OTHER: "질환",
        }
        disease_name = disease_names.get(disease, str(disease))

        # 습관 레이블 키워드에 따른 구체적 설명
        label_lower = habit_label.lower()

        if disease == Disease.DIABETES:
            if any(k in label_lower for k in ["명상", "스트레칭", "요가"]):
                return "당뇨병 관리를 위해 스트레스 감소가 중요합니다"
            elif any(k in label_lower for k in ["걷기", "산책", "운동", "조깅"]):
                return "당뇨병 혈당 조절에 효과적한 유산소 운동입니다"
            elif any(k in label_lower for k in ["식사", "먹기", "밥"]):
                return "당뇨병 관리를 위해 규칙적인 식사 시간이 필수입니다"
            elif any(k in label_lower for k in ["물", "음료", "마시기"]):
                return "당뇨병 관리를 위해 수분 섭취가 중요합니다"
            elif any(k in label_lower for k in ["과일", "야채", "신선"]):
                return "당뇨병 관리를 위해 신선한 음식 섭취가 중요합니다"
            elif any(k in label_lower for k in ["수면", "잠", "자기"]):
                return "당뇨병 관리를 위해 충분한 수면이 필수입니다"
            else:
                return f"{disease_name} 관리에 도움이 됩니다"

        elif disease == Disease.LIVER_DISEASE:
            if any(k in label_lower for k in ["명상", "스트레칭", "요가"]):
                return "간질환 관리를 위해 스트레스 감소가 중요합니다"
            elif any(k in label_lower for k in ["걷기", "산책", "운동"]):
                return "간질환 관리에 효과적한 가벼운 운동입니다"
            elif any(k in label_lower for k in ["식사", "먹기", "밥"]):
                return "간질환 관리를 위해 규칙적인 식사 시간이 필수입니다"
            elif any(k in label_lower for k in ["물", "음료", "마시기"]):
                return "간질환 관리를 위해 수분 섭취가 중요합니다"
            elif any(k in label_lower for k in ["과일", "야채", "신선"]):
                return "간 건강을 위해 신선한 음식 섭취가 도움이 됩니다"
            elif any(k in label_lower for k in ["금주", "주류", "술"]):
                return "간질환 관리의 필수 요소입니다"
            elif any(k in label_lower for k in ["수면", "잠", "자기"]):
                return "간질환 관리를 위해 충분한 수면이 필수입니다"
            else:
                return f"{disease_name} 관리에 도움이 됩니다"

        elif disease == Disease.HEART_DISEASE:
            if any(k in label_lower for k in ["명상", "스트레칭", "요가"]):
                return "심장질환 관리를 위해 스트레스 감소가 중요합니다"
            elif any(k in label_lower for k in ["걷기", "산책", "운동"]):
                return "심장 건강 개선을 위한 가벼운 운동입니다"
            elif any(k in label_lower for k in ["식사", "먹기", "밥"]):
                return "심장질환 관리를 위해 규칙적인 식사가 중요합니다"
            elif any(k in label_lower for k in ["염", "소금"]):
                return "심장질환 관리의 핵심 요소입니다"
            elif any(k in label_lower for k in ["수면", "잠", "자기"]):
                return "심장 부하 감소를 위해 규칙적인 수면이 중요합니다"
            else:
                return f"{disease_name} 관리에 도움이 됩니다"

        elif disease == Disease.CEREBROVASCULAR_DISEASE:
            if any(k in label_lower for k in ["명상", "스트레칭", "요가"]):
                return "뇌혈관 건강을 위해 스트레스 감소가 중요합니다"
            elif any(k in label_lower for k in ["걷기", "산책", "운동"]):
                return "뇌혈관 건강을 위한 혈류 개선 운동입니다"
            elif any(k in label_lower for k in ["독서"]):
                return "뇌 건강과 집중력 향상에 도움이 됩니다"
            elif any(k in label_lower for k in ["수면", "잠", "자기"]):
                return "뇌혈관 건강을 위해 충분한 수면이 중요합니다"
            else:
                return f"{disease_name} 관리에 도움이 됩니다"

        elif disease == Disease.CANCER:
            if any(k in label_lower for k in ["휴식", "수면", "잠", "자기"]):
                return "암 치료 중 회복과 면역력 강화에 중요합니다"
            elif any(k in label_lower for k in ["명상", "스트레칭", "요가"]):
                return "암 관리를 위해 스트레스 감소가 중요합니다"
            elif any(k in label_lower for k in ["과일", "야채", "신선"]):
                return "암 관리를 위해 영양가 있는 음식 섭취가 중요합니다"
            else:
                return f"{disease_name} 관리에 도움이 됩니다"

        elif disease == Disease.OTHER:
            # 기타 질환 (골절, 염좌, 충수염, 장염 등)의 습관별 맞춤 설명
            if any(k in label_lower for k in ["부목", "붕대", "고정", "압박"]):
                return "부상 회복을 위해 고정과 안정화가 필수입니다"
            elif any(k in label_lower for k in ["찜질", "온찜질", "냉찜질", "냉기", "차가운"]):
                return "부상 부위 부종 감소와 통증 완화에 효과적입니다"
            elif any(k in label_lower for k in ["통증", "체크", "모니터링", "확인"]):
                return "증상과 통증을 정기적으로 체크하여 악화를 예방하세요"
            elif any(k in label_lower for k in ["스트레칭", "운동", "재활", "근력"]):
                return "회복 단계에 맞춘 재활 운동이 중요합니다"
            elif any(k in label_lower for k in ["수면", "잠", "휴식", "자기"]):
                return "회복을 위해 충분한 휴식이 필수입니다"
            elif any(k in label_lower for k in ["영양", "과일", "야채", "단백질", "음식", "식단"]):
                return "회복을 위해 충분한 영양 섭취가 중요합니다"
            elif any(k in label_lower for k in ["소화", "장", "복부", "자극", "자극적"]):
                return "소화 기능 회복을 위해 자극이 적은 음식을 섭취하세요"
            elif any(k in label_lower for k in ["수분", "수액", "물", "마시"]):
                return "수분과 전해질 보충이 회복에 필수적입니다"
            elif any(k in label_lower for k in ["스트레스", "명상", "이완"]):
                return "정신적 스트레스 감소로 회복 속도를 높이세요"
            else:
                return "건강 회복을 위한 생활습관입니다"

        else:
            return f"{disease_name} 관리에 도움이 됩니다"

    async def select_habits(
        self, session: AsyncSession, profile: Profile, habit_keys: list[str]
    ) -> HabitsTodayResponse:
        today = date.today()
        full_pool, habit_to_disease = await self.build_full_pool(session, profile)
        pool = pick_recommendations(full_pool, profile.id, today, habit_to_disease)
        valid_keys = {h.key for h in pool}
        invalid_keys = [k for k in habit_keys if k not in valid_keys]
        if invalid_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"오늘의 추천 목록에 없는 습관입니다: {', '.join(invalid_keys)}",
            )
        await self._repository.replace_selection(session, profile.id, today, habit_keys)
        return await self.get_today(session, profile)

    async def get_today(self, session: AsyncSession, profile: Profile) -> HabitsTodayResponse:
        today = date.today()
        catalog = await self._selected_catalog(session, profile, today)
        logs = await self._repository.list_logs_for_date(session, profile.id, today)
        progress_by_key = {log.habit_key: log.progress for log in logs}
        return self._to_response(catalog, progress_by_key)

    async def check_habit(self, session: AsyncSession, profile: Profile, habit_key: str) -> HabitsTodayResponse:
        today = date.today()
        catalog = await self._selected_catalog(session, profile, today)
        habit_def = next((h for h in catalog if h.key == habit_key), None)
        if habit_def is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="오늘 선택한 습관 목록에 없는 항목입니다."
            )

        # 이번 체크로 "방금 막" 오늘의 습관을 전부 완료했을 때만(이미 완료된 상태에서 다시
        # 체크 API를 호출하는 경우는 제외) 목표달성 알림을 보낸다 - 그래서 증가시키기 전의
        # 완료 상태를 먼저 계산해둔다.
        logs_before = await self._repository.list_logs_for_date(session, profile.id, today)
        was_all_completed = self._to_response(
            catalog, {log.habit_key: log.progress for log in logs_before}
        ).all_completed

        await self._repository.increment_progress(session, profile.id, today, habit_key, cap=habit_def.target)

        logs = await self._repository.list_logs_for_date(session, profile.id, today)
        progress_by_key = {log.habit_key: log.progress for log in logs}
        response = self._to_response(catalog, progress_by_key)

        if not was_all_completed and response.all_completed:
            try:
                await self._push_service.send_to_profile(
                    session,
                    profile.id,
                    "🎉 오늘의 습관 목표 달성!",
                    "오늘 고른 습관을 모두 완료했어요. 정말 잘하고 있어요!",
                    link_url="/habit-selection",
                )
            except Exception:
                # 알림은 부가 기능이라, 발송 실패가 습관 체크 자체(핵심 기능)를 막으면 안 된다.
                logger.exception("습관 목표달성 알림 발송 실패 (profile_id=%s)", profile.id)

        return response

    async def _selected_catalog(self, session: AsyncSession, profile: Profile, today: date) -> list[HabitDef]:
        full_pool, _ = await self.build_full_pool(session, profile)
        by_key = {h.key: h for h in full_pool}
        selected_keys = await self._repository.list_selected_keys(session, profile.id, today)
        return [by_key[key] for key in selected_keys if key in by_key]

    def _to_response(self, catalog: list[HabitDef], progress_by_key: dict[str, int]) -> HabitsTodayResponse:
        items = [
            HabitItemResponse(
                key=h.key,
                label=h.label,
                icon=h.icon,
                unit=h.unit,
                target=h.target,
                progress=progress_by_key.get(h.key, 0),
                completed=progress_by_key.get(h.key, 0) >= h.target,
            )
            for h in catalog
        ]
        # 선택한 습관이 하나도 없으면(0개 선택) 공허 참으로 True가 되어버리지 않게 막는다 -
        # 그렇지 않으면 아직 아무것도 안 골랐을 때 칭찬 화면이 잘못 뜬다.
        all_completed = bool(items) and all(i.completed for i in items)
        return HabitsTodayResponse(habits=items, all_completed=all_completed)
