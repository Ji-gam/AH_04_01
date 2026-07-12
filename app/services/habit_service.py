from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.habit import HabitItemResponse, HabitsTodayResponse
from app.models.profiles import Disease, Profile
from app.repositories.habit_repository import HabitRepository


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


def build_catalog(profile: Profile) -> list[HabitDef]:
    """오늘의 습관 세트 = 기본 세트 + 등록된 질환마다 맞춤 습관 1개(같은 질환 중복 등록은 1개로 합침)."""
    catalog = list(BASE_HABITS)
    seen: set[Disease] = set()
    for entry in profile.diagnosis_history or []:
        disease = Disease(entry["disease"])
        if disease in seen:
            continue
        seen.add(disease)
        habit_def = DISEASE_HABITS.get(disease)
        if habit_def:
            catalog.append(habit_def)
    return catalog


class HabitService:
    def __init__(self, repository: HabitRepository | None = None) -> None:
        self._repository = repository or HabitRepository()

    async def get_today(self, session: AsyncSession, profile: Profile) -> HabitsTodayResponse:
        today = date.today()
        catalog = build_catalog(profile)
        logs = await self._repository.list_logs_for_date(session, profile.id, today)
        progress_by_key = {log.habit_key: log.progress for log in logs}
        return self._to_response(catalog, progress_by_key)

    async def check_habit(self, session: AsyncSession, profile: Profile, habit_key: str) -> HabitsTodayResponse:
        today = date.today()
        catalog = build_catalog(profile)
        habit_def = next((h for h in catalog if h.key == habit_key), None)
        if habit_def is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="오늘의 습관 목록에 없는 항목입니다.")

        await self._repository.increment_progress(session, profile.id, today, habit_key, cap=habit_def.target)

        logs = await self._repository.list_logs_for_date(session, profile.id, today)
        progress_by_key = {log.habit_key: log.progress for log in logs}
        return self._to_response(catalog, progress_by_key)

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
        return HabitsTodayResponse(habits=items, all_completed=all(i.completed for i in items))
