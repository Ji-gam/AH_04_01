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


_AI_FOOD_SYSTEM_PROMPT = (
    "당신은 영양학 전문가입니다. 사용자가 입력한 음식 이름을 보고 100g당 영양성분과 "
    "1회 제공량을 추정하세요. 한국에서 통상적으로 먹는 형태를 기준으로 하고, "
    "food_name은 입력한 이름을 그대로 쓰되 필요하면 조리 형태만 짧게 덧붙이세요. "
    "calorie_kcal_per_100g는 100g당 칼로리(kcal), protein/carb/fat_g_per_100g는 100g당 "
    "그램(g), serving_size_g는 1회 제공량(g)입니다. 숫자만 정확히 채우세요."
)

# AI가 환각으로 말도 안 되는 값을 줬을 때 거르는 상한 - 순수 지방이 100g당 900kcal이라
# 그보다 큰 값은 불가능하고, 100g 안의 단백질/탄수/지방도 각각 100g을 넘을 수 없다.
_MAX_KCAL_PER_100G = 900.0
_MAX_MACRO_G_PER_100G = 100.0
_MAX_SERVING_SIZE_G = 2000.0


class AIFoodNutrition(BaseModel):
    """AIWorkerGateway.call_structured()가 채워야 하는 구조 - 목록에서 못 찾은 음식을
    AI가 추정할 때 쓴다(DietKcalReasonSummary와 같은 발상)."""

    food_name: str
    serving_size_g: float
    calorie_kcal_per_100g: float
    protein_g_per_100g: float
    carb_g_per_100g: float
    fat_g_per_100g: float


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

    async def estimate_food_by_ai(self, food_name: str) -> FoodSearchResultItem | None:
        """식약처 API에서 못 찾은 음식을 AI가 추정한다. 실패하거나 값이 비상식적이면
        None을 돌려준다(exercise_service.estimate_met의 MET 범위 검증과 같은 발상)."""
        normalized = food_name.strip()
        if not normalized:
            return None
        try:
            raw_result = await self._gateway.call_structured(
                system_prompt=_AI_FOOD_SYSTEM_PROMPT,
                user_input=normalized,
                schema=AIFoodNutrition,
            )
        except (AIWorkerUnavailableError, AIWorkerInvalidRequestError, AIWorkerProcessingError) as e:
            logger.warning("음식 '%s' AI 영양성분 추정 실패: %s", normalized, e)
            return None

        result = cast(AIFoodNutrition, raw_result)
        macros = (result.protein_g_per_100g, result.carb_g_per_100g, result.fat_g_per_100g)
        if not (0 <= result.calorie_kcal_per_100g <= _MAX_KCAL_PER_100G):
            logger.warning("음식 '%s' AI 추정 칼로리가 범위를 벗어나 버립니다: %s", normalized, result)
            return None
        if any(not (0 <= macro <= _MAX_MACRO_G_PER_100G) for macro in macros):
            logger.warning("음식 '%s' AI 추정 영양성분이 범위를 벗어나 버립니다: %s", normalized, result)
            return None
        serving = result.serving_size_g if 0 < result.serving_size_g <= _MAX_SERVING_SIZE_G else 100.0

        return FoodSearchResultItem(
            food_name=(result.food_name.strip() or normalized)[:100],
            serving_size_g=serving,
            calorie_kcal_per_100g=result.calorie_kcal_per_100g,
            protein_g_per_100g=result.protein_g_per_100g,
            carb_g_per_100g=result.carb_g_per_100g,
            fat_g_per_100g=result.fat_g_per_100g,
        )

    async def search_food(self, session: AsyncSession, query: str) -> FoodSearchResult:
        """식약처 API → (죽었거나 0건이면) AI 추정 → (그것도 실패하면) 로컬 시드 순으로 찾는다.

        시드 결과는 캐시하지 않는다 - 예전엔 API가 안 되던 시절의 시드 결과(1~2건)가 캐시에
        영구히 남아, API가 정상으로 돌아온 뒤에도 계속 그 빈약한 결과만 나왔다(2026-08-03 발견)."""
        normalized = query.strip()
        if len(normalized) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="검색어를 입력해주세요.")

        cached = await self._repository.get_cached_food(session, normalized)
        if cached is not None:
            return FoodSearchResult(results=[FoodSearchResultItem(**row) for row in cached.results])

        items: list[FoodSearchResultItem] = []
        try:
            live_items = await food_nutrition_open_api_client.fetch_live(normalized)
            items = [
                _raw_item_to_dto(raw) for raw in food_nutrition_open_api_client.sort_and_trim(live_items, normalized)
            ]
        except Exception:
            logger.warning("식품영양성분DB API 호출 실패, AI 추정으로 넘어갑니다 (query=%s)", normalized, exc_info=True)

        if not items:
            ai_item = await self.estimate_food_by_ai(normalized)
            if ai_item is not None:
                items = [ai_item]

        if items:
            await self._repository.save_cached_food(session, normalized, [item.model_dump() for item in items])
            return FoodSearchResult(results=items)

        seed_items = food_nutrition_open_api_client.sort_and_trim(
            food_nutrition_open_api_client.search_seed(normalized), normalized
        )
        return FoodSearchResult(results=[_raw_item_to_dto(raw) for raw in seed_items])

    async def find_food_by_ai(self, session: AsyncSession, food_name: str) -> FoodSearchResult:
        """ "찾는 음식이 없나요? AI로 찾기" 버튼용 - 검색 결과가 있어도 사용자가 원하는 게
        없을 때(예: "김"을 치면 김밥·김치 요리만 20건 나옴) 강제로 AI에게 물어본다.

        결과는 그 검색어의 기존 캐시 맨 앞에 끼워 넣어, 다음에 같은 검색어로 찾으면 AI가
        찾아준 항목이 목록 맨 위에 함께 보이게 한다."""
        normalized = food_name.strip()
        if len(normalized) < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="음식 이름을 입력해주세요.")

        ai_item = await self.estimate_food_by_ai(normalized)
        if ai_item is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI가 이 음식의 영양성분을 찾지 못했어요. 잠시 후 다시 시도해주세요.",
            )

        cached = await self._repository.get_cached_food(session, normalized)
        previous = [FoodSearchResultItem(**row) for row in cached.results] if cached is not None else []
        merged = [ai_item] + [item for item in previous if item.food_name != ai_item.food_name]
        await self._repository.save_cached_food(session, normalized, [item.model_dump() for item in merged])

        return FoodSearchResult(results=[ai_item])

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
