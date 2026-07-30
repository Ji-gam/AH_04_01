import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.diet_dto import (
    DietLogCreateRequest,
    DietLogItemResult,
    DietRecentDayResult,
    DietRecentResult,
    DietTodayResult,
    FoodSearchResult,
    FoodSearchResultItem,
)
from app.models.health_profiles import HealthProfile
from app.models.profiles import Gender, Profile
from app.repositories.diet_repository import DietRepository
from app.services import food_nutrition_open_api_client
from app.services.age_calculator import resolve_display_age
from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)

logger = logging.getLogger("app.diet_service")

# 키/몸무게/나이/성별 중 하나라도 없어 개인화 계산이 불가능할 때 쓰는 일반 성인 권장 섭취량.
DIET_REFERENCE_KCAL = 2000

_KCAL_REASON_SYSTEM_PROMPT = (
    "당신은 헬스케어 앱 ReMedi의 영양 코치입니다. 사용자의 키/몸무게/나이/성별과 이미 계산된 "
    "하루 권장 섭취 칼로리를 보고, 왜 그 값이 이 사람에게 적절한지 한국어 한 문장(50자 이내)으로 "
    "설명하세요. 숫자를 자연스러운 문장 속에 녹여서 언급하고, 의학적 조언이나 진단은 하지 마세요."
)


class DietKcalReasonSummary(BaseModel):
    """AIWorkerGateway.call_structured()에는 자유텍스트 전용 메서드가 없어(스키마 필수),
    한 줄 이유만 담는 최소 스키마로 받는다 - weekly_report_service.py의
    WeeklyReportSummary와 같은 발상."""

    reason: str


def _compute_reference_kcal(health: HealthProfile | None) -> tuple[int, bool]:
    """키/몸무게/생년월일/성별이 모두 있으면 Mifflin-St Jeor 공식으로 기초대사량(BMR)을
    구하고 활동계수(가벼운 활동 기준 1.375)를 곱해 개인화된 하루 권장 섭취 칼로리를
    계산한다. 하나라도 없으면 일반 성인 권장량(DIET_REFERENCE_KCAL)으로 폴백한다.
    두 번째 반환값은 개인화 성공 여부(AI 이유 생성 문구 분기에 쓰인다)."""
    if health is None or health.height_cm is None or health.weight_kg is None or health.gender is None:
        return DIET_REFERENCE_KCAL, False
    age = resolve_display_age(health.birth_date)
    if age is None:
        return DIET_REFERENCE_KCAL, False

    height_cm = float(health.height_cm)
    weight_kg = float(health.weight_kg)
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age
    bmr += 5 if health.gender == Gender.MALE else -161
    reference_kcal = round(bmr * 1.375 / 50) * 50
    return max(1000, reference_kcal), True


def _fallback_kcal_reason(personalized: bool, reference_kcal: int, health: HealthProfile | None) -> str:
    """AI 호출이 실패하거나(ai_worker 다운 등) 애초에 개인화 계산이 불가능할 때도 한 줄
    이유는 항상 보여야 하므로 규칙 기반 폴백을 둔다 - weekly_report_service.py의
    _fallback_report()와 같은 패턴."""
    if not personalized or health is None:
        return f"키/몸무게 정보가 없어 일반 성인 기준 {reference_kcal}kcal을 보여드리고 있어요."
    return f"키 {health.height_cm}cm, 몸무게 {health.weight_kg}kg 기준으로 계산한 하루 권장 섭취량이에요."


def _raw_item_to_dto(item: food_nutrition_open_api_client.RawFoodItem) -> FoodSearchResultItem:
    return FoodSearchResultItem(
        food_name=item.food_name,
        serving_size_g=item.serving_size_g,
        calorie_kcal_per_100g=item.calorie_kcal_per_100g,
        protein_g_per_100g=item.protein_g_per_100g,
        carb_g_per_100g=item.carb_g_per_100g,
        fat_g_per_100g=item.fat_g_per_100g,
    )


class DietService:
    def __init__(self, repository: DietRepository | None = None, gateway: AIWorkerGateway | None = None) -> None:
        self._repository = repository or DietRepository()
        self._gateway = gateway or AIWorkerGateway()

    async def search_food(self, session: AsyncSession, query: str) -> FoodSearchResult:
        normalized = query.strip()
        if len(normalized) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어를 입력해주세요.")

        cached = await self._repository.get_cached_food(session, normalized)
        if cached is not None:
            return FoodSearchResult(results=[FoodSearchResultItem(**row) for row in cached.results])

        raw_items = await food_nutrition_open_api_client.search_food(normalized)
        items = [_raw_item_to_dto(raw) for raw in raw_items]
        if items:
            await self._repository.save_cached_food(session, normalized, [item.model_dump() for item in items])
        return FoodSearchResult(results=items)

    async def log_food(self, session: AsyncSession, profile: Profile, request: DietLogCreateRequest) -> DietTodayResult:
        multiplier = Decimal(str(request.serving_multiplier))
        serving_grams = Decimal(str(request.serving_size_g)) * multiplier
        ratio = serving_grams / Decimal(100)

        await self._repository.create_log(
            session,
            profile_id=profile.id,
            log_date=date.today(),
            food_name=request.food_name,
            serving_multiplier=multiplier,
            serving_grams=serving_grams,
            calorie_kcal=Decimal(str(request.calorie_kcal_per_100g)) * ratio,
            protein_g=Decimal(str(request.protein_g_per_100g)) * ratio,
            carb_g=Decimal(str(request.carb_g_per_100g)) * ratio,
            fat_g=Decimal(str(request.fat_g_per_100g)) * ratio,
        )
        return await self.get_today(session, profile)

    async def _get_kcal_reason(
        self,
        session: AsyncSession,
        profile_id: int,
        health: HealthProfile | None,
        reference_kcal: int,
        personalized: bool,
    ) -> str:
        """오늘 하루 기준 (profile_id, 날짜)로 캐시해 재조회(페이지 새로고침, 식단 기록
        추가 등)마다 ai_worker를 다시 부르지 않는다 - 캐시된 reference_kcal이 지금 값과
        다르면(그날 안에 키/몸무게를 바꾼 경우) 다시 생성한다."""
        today = date.today()
        cached = await self._repository.get_kcal_reason(session, profile_id, today)
        if cached is not None and cached.reference_kcal == reference_kcal:
            return cached.reason

        fallback = _fallback_kcal_reason(personalized, reference_kcal, health)
        if not personalized or health is None:
            reason = fallback
        else:
            gender_label = "남성" if health.gender == Gender.MALE else "여성"
            user_input = (
                f"키 {health.height_cm}cm, 몸무게 {health.weight_kg}kg, "
                f"나이 {resolve_display_age(health.birth_date)}세, 성별 {gender_label}, "
                f"하루 권장 섭취 칼로리 {reference_kcal}kcal"
            )
            try:
                result = await self._gateway.call_structured(
                    system_prompt=_KCAL_REASON_SYSTEM_PROMPT,
                    user_input=user_input,
                    schema=DietKcalReasonSummary,
                )
                reason = cast(DietKcalReasonSummary, result).reason
            except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
                logger.warning(
                    "식단 기준 칼로리 이유 AI 생성 실패, 폴백 문구로 대체합니다 (profile_id=%s): %s", profile_id, e
                )
                reason = fallback

        await self._repository.save_kcal_reason(session, profile_id, today, reference_kcal, reason)
        return reason

    async def get_today(self, session: AsyncSession, profile: Profile) -> DietTodayResult:
        logs = await self._repository.list_logs_for_date(session, profile.id, date.today())
        items = [
            DietLogItemResult(
                id=log.id,
                food_name=log.food_name,
                serving_grams=float(log.serving_grams),
                calorie_kcal=float(log.calorie_kcal),
                protein_g=float(log.protein_g),
                carb_g=float(log.carb_g),
                fat_g=float(log.fat_g),
                logged_at=log.created_at,
            )
            for log in logs
        ]
        reference_kcal, personalized = _compute_reference_kcal(profile.health_profile)
        reference_kcal_reason = await self._get_kcal_reason(
            session, profile.id, profile.health_profile, reference_kcal, personalized
        )
        return DietTodayResult(
            logs=items,
            total_kcal=sum(i.calorie_kcal for i in items),
            total_protein_g=sum(i.protein_g for i in items),
            total_carb_g=sum(i.carb_g for i in items),
            total_fat_g=sum(i.fat_g for i in items),
            reference_kcal=reference_kcal,
            reference_kcal_reason=reference_kcal_reason,
        )

    async def delete_log(self, session: AsyncSession, profile: Profile, log_id: int) -> DietTodayResult:
        deleted = await self._repository.delete_log(session, profile.id, log_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 기록을 찾을 수 없습니다.")
        return await self.get_today(session, profile)

    async def get_recent(self, session: AsyncSession, profile: Profile) -> DietRecentResult:
        end = date.today()
        start = end - timedelta(days=6)
        totals = dict(await self._repository.list_daily_totals(session, profile.id, start, end))
        days = [
            DietRecentDayResult(log_date=day, total_kcal=float(totals.get(day, 0)))
            for day in (start + timedelta(days=offset) for offset in range(7))
        ]
        return DietRecentResult(days=days)
