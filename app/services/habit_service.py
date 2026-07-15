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

# 진단병력(Disease)에 등록된 질환마다 하나씩 추가되는 기본 맞춤 습관 - 세부 진단명(subtype)이
# 없거나, 있어도 LLM 생성이 실패했을 때의 폴백으로 쓰인다(2단계 이후에는 항상 이게 최종
# 폴백이라, 이 6개는 계속 유지한다).
DISEASE_HABITS: dict[Disease, HabitDef] = {
    Disease.DIABETES: HabitDef(key="diabetes_walk", label="식후 10분 걷기", icon="🍽️", unit="회", target=1),
    Disease.HEART_DISEASE: HabitDef(key="heart_low_salt", label="저염식 식사하기", icon="🧂", unit="회", target=1),
    Disease.CEREBROVASCULAR_DISEASE: HabitDef(
        key="cerebro_stretch", label="스트레칭 5분", icon="🧘", unit="회", target=1
    ),
    Disease.LIVER_DISEASE: HabitDef(key="liver_no_alcohol", label="금주 실천하기", icon="🚫", unit="회", target=1),
    Disease.CANCER: HabitDef(key="cancer_rest", label="충분한 휴식 취하기", icon="😴", unit="회", target=1),
    Disease.OTHER: HabitDef(key="other_condition_check", label="오늘 컨디션 체크하기", icon="📝", unit="회", target=1),
}


class SubtypeHabitSuggestion(BaseModel):
    """AIWorkerGateway.call_structured()가 채워야 하는 구조 - 진단명 하나에 습관 하나."""

    label: str
    icon: str
    unit: str
    target: int


_SUBTYPE_HABIT_SYSTEM_PROMPT = (
    "당신은 건강관리 앱의 습관 추천 도우미입니다. 주어진 진단명에 맞는 짧고 실천 가능한 "
    "하루 습관을 하나만 만드세요.\n"
    "- label: 10자 내외, 행동 중심 (예: '저염식 30분 식사하기')\n"
    "- icon: 이모지 1개\n"
    "- unit: '회'/'잔'/'분' 등 짧은 단위\n"
    "- target: 보통 1(하루 목표 횟수), 필요하면 다른 값도 가능\n"
    "위험하거나 의학적으로 부적절한 습관(예: 약 복용 중단, 자가진단, 자가치료)은 절대 "
    "추천하지 마세요."
)


def pick_recommendations(pool: list[HabitDef], profile_id: int, today: date) -> list[HabitDef]:
    """후보군이 MAX_RECOMMENDATIONS개 이하면 전부 추천하고, 그보다 많으면(진단명별 LLM 습관이
    늘어나는 경우) 날짜가 하루 지날 때마다 정확히 한 칸씩 미는 방식으로 MAX_RECOMMENDATIONS개를
    고른다. profile_id를 더해 계정마다 시작 위치가 달라지게 하되, 요일 간 회전 자체는 늘 +1이라
    "우연히 며칠 연속 같은 결과가 나오는" 문제(해시 나머지 방식의 알려진 결함)가 구조적으로
    없다."""
    if len(pool) <= MAX_RECOMMENDATIONS:
        return pool
    start = (today.toordinal() + profile_id) % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(MAX_RECOMMENDATIONS)]


class HabitService:
    def __init__(
        self,
        repository: HabitRepository | None = None,
        gateway: AIWorkerGateway | None = None,
    ) -> None:
        self._repository = repository or HabitRepository()
        self._gateway = gateway or AIWorkerGateway()

    async def build_full_pool(self, session: AsyncSession, profile: Profile) -> list[HabitDef]:
        """가능한 전체 습관 후보 = 기본 세트 + 등록된 진단마다 맞춤 습관 1개.
        세부 진단명(disease_subtype)이 있으면 AIWorkerGateway로 그 진단명 전용 습관을
        생성(또는 캐시에서 재사용)하고, 없거나 생성에 실패하면 6개 broad 카테고리 기본
        습관으로 폴백한다. 같은 세부 진단명이 여러 번 등록됐거나, 세부 진단명 없이 같은
        broad 카테고리가 중복 등록된 경우만 하나로 합친다(세부 진단명이 다르면 둘 다
        후보에 남는다 - 예: 심장질환 중 "협심증"과 "부정맥"은 서로 다른 습관을 받는다).
        [정규화] diagnosis_history(JSON) 대신 diagnosis_entries(1:N 관계형 테이블)에서 읽는다."""
        pool = list(BASE_HABITS)
        seen: set[int | Disease] = set()
        for entry in profile.diagnosis_entries or []:
            dedupe_key: int | Disease = entry.disease_subtype_id or entry.disease
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            habit_def = None
            if entry.disease_subtype is not None:
                habit_def = await self._get_subtype_habit(session, entry.disease_subtype)
            if habit_def is None:
                habit_def = DISEASE_HABITS.get(entry.disease)
            if habit_def:
                pool.append(habit_def)
        return pool

    async def _get_subtype_habit(self, session: AsyncSession, subtype: DiseaseSubtype) -> HabitDef | None:
        cached = await self._repository.get_subtype_suggestion(session, subtype.id)
        if cached is not None:
            return HabitDef(
                key=f"subtype_{cached.disease_subtype_id}",
                label=cached.label,
                icon=cached.icon,
                unit=cached.unit,
                target=cached.target,
            )

        try:
            raw_result = await self._gateway.call_structured(
                system_prompt=_SUBTYPE_HABIT_SYSTEM_PROMPT,
                user_input=f"진단명: {subtype.name}",
                schema=SubtypeHabitSuggestion,
            )
        except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
            logger.warning(f"진단명 '{subtype.name}' 습관 생성 실패, 기본 카테고리 습관으로 대체합니다: {e}")
            return None

        result = cast(SubtypeHabitSuggestion, raw_result)
        # LLM 출력은 형식이 안 맞을 수 있어 그대로 믿지 않고 방어적으로 다듬는다.
        label = result.label.strip()[:50] or "오늘 컨디션 체크하기"
        icon = (result.icon.strip() or "📝")[:10]
        unit = (result.unit.strip() or "회")[:20]
        target = max(1, result.target)

        saved = await self._repository.save_subtype_suggestion(session, subtype.id, label, icon, unit, target)
        return HabitDef(
            key=f"subtype_{saved.disease_subtype_id}",
            label=saved.label,
            icon=saved.icon,
            unit=saved.unit,
            target=saved.target,
        )

    async def get_recommendations(self, session: AsyncSession, profile: Profile) -> HabitRecommendationsResponse:
        today = date.today()
        pool = pick_recommendations(await self.build_full_pool(session, profile), profile.id, today)
        valid_keys = {h.key for h in pool}
        selected_keys = await self._repository.list_selected_keys(session, profile.id, today)
        return HabitRecommendationsResponse(
            habits=[
                HabitRecommendationItem(key=h.key, label=h.label, icon=h.icon, unit=h.unit, target=h.target)
                for h in pool
            ],
            # 세부 진단명이 새로 캐시되는 등 풀이 바뀌면 예전 선택 키가 오늘 풀엔 없을 수 있다
            # (예: cerebro_stretch로 선택해뒀는데 이후 subtype_20 습관으로 대체된 경우). 그런
            # 유령 키를 그대로 내려주면 프론트가 "선택됨"으로 상태를 만들고, 저장 시 그 키를
            # 그대로 다시 보내 select_habits()의 유효성 검사(400)에 걸린다 - 오늘 실제로 고를 수
            # 있는 키만 내려서 애초에 이 문제가 생기지 않게 한다.
            selected_keys=[key for key in selected_keys if key in valid_keys],
        )

    async def select_habits(
        self, session: AsyncSession, profile: Profile, habit_keys: list[str]
    ) -> HabitsTodayResponse:
        today = date.today()
        pool = pick_recommendations(await self.build_full_pool(session, profile), profile.id, today)
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

        await self._repository.increment_progress(session, profile.id, today, habit_key, cap=habit_def.target)

        logs = await self._repository.list_logs_for_date(session, profile.id, today)
        progress_by_key = {log.habit_key: log.progress for log in logs}
        return self._to_response(catalog, progress_by_key)

    async def _selected_catalog(self, session: AsyncSession, profile: Profile, today: date) -> list[HabitDef]:
        by_key = {h.key: h for h in await self.build_full_pool(session, profile)}
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
