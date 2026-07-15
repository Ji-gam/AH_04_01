from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.habit import (
    HabitItemResponse,
    HabitRecommendationItem,
    HabitRecommendationsResponse,
    HabitsTodayResponse,
)
from app.models.profiles import Disease, Profile
from app.repositories.habit_repository import HabitRepository

# 몇 개까지 고를 수 있는지는 app/dtos/habit.py의 HabitSelectionRequest.habit_keys(max_length=5)가
# 강제한다 - 여기서는 "추천을 몇 개까지 보여줄지"만 다룬다.
MAX_RECOMMENDATIONS = 10


@dataclass(frozen=True)
class HabitDef:
    key: str
    label: str
    icon: str
    unit: str
    target: int


# 등록 여부와 무관하게 누구에게나 뜨는 기본 세트. 걸음수는 브라우저에서 측정할 수 없어
# "산책 다녀왔어요" 완료 체크(target=1)로 대체한다(팀 논의 반영).
BASE_HABITS: list[HabitDef] = [
    HabitDef(key="water", label="물 마시기", icon="🥤", unit="잔", target=5),
    HabitDef(key="walk", label="산책하기", icon="🚶", unit="회", target=1),
]

# 진단병력(Disease)에 등록된 질환마다 하나씩 추가되는 맞춤 습관.
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


def build_full_pool(profile: Profile) -> list[HabitDef]:
    """가능한 전체 습관 후보 = 기본 세트 + 등록된 질환마다 맞춤 습관 1개(중복 질환은 1개로 합침).
    오늘의 추천 목록(최대 10개)은 이 후보군에서 pick_recommendations()가 골라낸다.
    [정규화] diagnosis_history(JSON) 대신 diagnosis_entries(1:N 관계형 테이블)에서 읽는다 -
    각 항목이 이미 Disease enum 객체(entry.disease)라 문자열 변환 불필요."""
    pool = list(BASE_HABITS)
    seen: set[Disease] = set()
    for entry in profile.diagnosis_entries or []:
        disease = entry.disease
        if disease in seen:
            continue
        seen.add(disease)
        habit_def = DISEASE_HABITS.get(disease)
        if habit_def:
            pool.append(habit_def)
    return pool


def pick_recommendations(pool: list[HabitDef], profile_id: int, today: date) -> list[HabitDef]:
    """후보군이 MAX_RECOMMENDATIONS개 이하면 전부 추천하고, 그보다 많으면(2단계: LLM이 후보를
    늘리는 경우) 날짜가 하루 지날 때마다 정확히 한 칸씩 미는 방식으로 MAX_RECOMMENDATIONS개를
    고른다. profile_id를 더해 계정마다 시작 위치가 달라지게 하되, 요일 간 회전 자체는 늘 +1이라
    "우연히 며칠 연속 같은 결과가 나오는" 문제(해시 나머지 방식의 알려진 결함)가 구조적으로
    없다."""
    if len(pool) <= MAX_RECOMMENDATIONS:
        return pool
    start = (today.toordinal() + profile_id) % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(MAX_RECOMMENDATIONS)]


class HabitService:
    def __init__(self, repository: HabitRepository | None = None) -> None:
        self._repository = repository or HabitRepository()

    async def get_recommendations(self, session: AsyncSession, profile: Profile) -> HabitRecommendationsResponse:
        today = date.today()
        pool = pick_recommendations(build_full_pool(profile), profile.id, today)
        selected_keys = await self._repository.list_selected_keys(session, profile.id, today)
        return HabitRecommendationsResponse(
            habits=[
                HabitRecommendationItem(key=h.key, label=h.label, icon=h.icon, unit=h.unit, target=h.target)
                for h in pool
            ],
            selected_keys=selected_keys,
        )

    async def select_habits(
        self, session: AsyncSession, profile: Profile, habit_keys: list[str]
    ) -> HabitsTodayResponse:
        today = date.today()
        pool = pick_recommendations(build_full_pool(profile), profile.id, today)
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="오늘 선택한 습관 목록에 없는 항목입니다.")

        await self._repository.increment_progress(session, profile.id, today, habit_key, cap=habit_def.target)

        logs = await self._repository.list_logs_for_date(session, profile.id, today)
        progress_by_key = {log.habit_key: log.progress for log in logs}
        return self._to_response(catalog, progress_by_key)

    async def _selected_catalog(self, session: AsyncSession, profile: Profile, today: date) -> list[HabitDef]:
        by_key = {h.key: h for h in build_full_pool(profile)}
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
