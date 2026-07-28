import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.exercise_dto import (
    ExerciseLogCreateRequest,
    ExerciseLogItemResult,
    ExerciseRecentDayResult,
    ExerciseRecentResult,
    ExerciseSearchResult,
    ExerciseSearchResultItem,
    ExerciseTodayResult,
)
from app.models.profiles import Profile
from app.repositories.exercise_repository import ExerciseRepository

# 프로필에 몸무게가 없을 때 소모 칼로리 계산에 쓰는 성인 평균 체중 폴백
# (diet_service.py의 DIET_REFERENCE_KCAL과 같은 발상 - 개인화 데이터가 없어도 기능이 막히지 않게 함).
DEFAULT_WEIGHT_KG = Decimal(60)

# REQ-TRCK-003 홈 위젯의 운동 진행률 바 분모 - WHO 권장 하루 유산소 운동시간(30분).
# diet_service.py의 DIET_REFERENCE_KCAL과 같은 방식으로, 개인 목표가 없어도 비교 기준을 준다.
EXERCISE_REFERENCE_MINUTES = 30

# 줄넘기(count 모드)의 분당 횟수 가정 - 실제 속도는 사람마다 다르지만, 시간 입력 없이 개수만으로
# 소모 칼로리를 내려면 어떤 가정이든 필요하다. "보통 속도" 기준으로 통상 알려진 값을 썼다.
JUMP_ROPE_REPS_PER_MINUTE = Decimal(100)

_MET_SEED_PATH = Path(__file__).resolve().parent.parent / "database" / "exercise_met_seed.json"


def _load_met_seed() -> list[dict]:
    with _MET_SEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)["exercises"]


def _search_met_seed(query: str) -> list[ExerciseSearchResultItem]:
    query_lower = query.strip().lower()
    return [
        ExerciseSearchResultItem(
            exercise_name=item["exercise_name"], met_value=item["met_value"], input_mode=item["input_mode"]
        )
        for item in _load_met_seed()
        if query_lower in item["exercise_name"].lower()
    ]


def _find_seed_item(exercise_name: str) -> dict | None:
    return next((item for item in _load_met_seed() if item["exercise_name"] == exercise_name), None)


def _met_from_speed(exercise_name: str, speed_kmh: Decimal) -> Decimal:
    """ACSM 대사방정식 기반 추정치(레벨 지면 기준) - 속도(km/h)를 분당 미터(m/min)로 바꿔
    VO2 = 0.1×속도 + 3.5(걷기) 또는 0.2×속도 + 3.5(달리기) 공식에 대입한 뒤 MET = VO2/3.5로 환산.
    Compendium of Physical Activities의 실측 MET 표와 정확히 일치하진 않지만(특히 아주 느리거나
    빠른 속도에서 오차가 커짐), 임의의 속도값을 입력받아야 하는 이 기능엔 이 근사식이 적합하다."""
    meters_per_min = speed_kmh * Decimal("16.6667")
    if "걷기" in exercise_name:
        vo2 = Decimal("0.1") * meters_per_min + Decimal("3.5")
    else:
        vo2 = Decimal("0.2") * meters_per_min + Decimal("3.5")
    return vo2 / Decimal("3.5")


class ExerciseService:
    def __init__(self, repository: ExerciseRepository | None = None) -> None:
        self._repository = repository or ExerciseRepository()

    async def search_exercise(self, query: str) -> ExerciseSearchResult:
        """운동은 MET 값이 안정적인 공개 표준값이라 외부 API 없이 정적 시드만 사용한다
        (food_nutrition_open_api_client.py와 달리 라이브/폴백 분기가 없다)."""
        normalized = query.strip()
        if len(normalized) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어를 입력해주세요.")
        return ExerciseSearchResult(results=_search_met_seed(normalized))

    async def log_exercise(
        self, session: AsyncSession, profile: Profile, request: ExerciseLogCreateRequest
    ) -> ExerciseTodayResult:
        weight_kg = Decimal(str(profile.weight_kg)) if profile.weight_kg is not None else DEFAULT_WEIGHT_KG
        duration_minutes: Decimal
        distance_km: Decimal | None = None
        count: int | None = None

        if request.input_mode == "duration":
            if request.met_value is None or request.duration_minutes is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="duration 모드에는 met_value와 duration_minutes가 필요합니다.",
                )
            met_value = Decimal(str(request.met_value))
            duration_minutes = Decimal(str(request.duration_minutes))
        elif request.input_mode == "speed":
            if request.speed_kmh is None or request.duration_minutes is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="speed 모드에는 speed_kmh와 duration_minutes가 필요합니다.",
                )
            speed_kmh = Decimal(str(request.speed_kmh))
            duration_minutes = Decimal(str(request.duration_minutes))
            met_value = _met_from_speed(request.exercise_name, speed_kmh)
            distance_km = speed_kmh * duration_minutes / Decimal(60)
        elif request.input_mode == "count":
            if request.count is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="count 모드에는 count가 필요합니다."
                )
            seed_item = _find_seed_item(request.exercise_name)
            if seed_item is None or seed_item.get("met_value") is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="알 수 없는 운동이거나 count 모드를 지원하지 않습니다.",
                )
            met_value = Decimal(str(seed_item["met_value"]))
            count = request.count
            duration_minutes = Decimal(request.count) / JUMP_ROPE_REPS_PER_MINUTE
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="알 수 없는 input_mode입니다.")

        calorie_kcal = met_value * weight_kg * (duration_minutes / Decimal(60))

        await self._repository.create_log(
            session,
            profile_id=profile.id,
            log_date=date.today(),
            exercise_name=request.exercise_name,
            duration_minutes=duration_minutes,
            calorie_kcal=calorie_kcal,
            distance_km=distance_km,
            count=count,
        )
        return await self.get_today(session, profile)

    async def get_today(self, session: AsyncSession, profile: Profile) -> ExerciseTodayResult:
        logs = await self._repository.list_logs_for_date(session, profile.id, date.today())
        items = [
            ExerciseLogItemResult(
                id=log.id,
                exercise_name=log.exercise_name,
                duration_minutes=float(log.duration_minutes),
                distance_km=float(log.distance_km) if log.distance_km is not None else None,
                count=log.count,
                calorie_kcal=float(log.calorie_kcal),
                logged_at=log.created_at,
            )
            for log in logs
        ]
        return ExerciseTodayResult(
            logs=items,
            total_kcal=sum(i.calorie_kcal for i in items),
            total_duration_minutes=sum(i.duration_minutes for i in items),
            reference_minutes=EXERCISE_REFERENCE_MINUTES,
        )

    async def delete_log(self, session: AsyncSession, profile: Profile, log_id: int) -> ExerciseTodayResult:
        deleted = await self._repository.delete_log(session, profile.id, log_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 기록을 찾을 수 없습니다.")
        return await self.get_today(session, profile)

    async def get_recent(self, session: AsyncSession, profile: Profile) -> ExerciseRecentResult:
        end = date.today()
        start = end - timedelta(days=6)
        totals = dict(await self._repository.list_daily_totals(session, profile.id, start, end))
        days = [
            ExerciseRecentDayResult(log_date=day, total_kcal=float(totals.get(day, 0)))
            for day in (start + timedelta(days=offset) for offset in range(7))
        ]
        return ExerciseRecentResult(days=days)
