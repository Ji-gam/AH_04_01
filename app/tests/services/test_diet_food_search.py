from app.services import food_nutrition_open_api_client as client
from app.services.ai_worker_gateway import AIWorkerUnavailableError
from app.services.diet_service import AIFoodNutrition, DietService


def _raw(name: str, kcal: float = 100.0) -> client.RawFoodItem:
    return client.RawFoodItem(
        food_name=name,
        serving_size_g=100.0,
        calorie_kcal_per_100g=kcal,
        protein_g_per_100g=1.0,
        carb_g_per_100g=1.0,
        fat_g_per_100g=1.0,
    )


class FakeGateway:
    def __init__(self, result: AIFoodNutrition | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.call_count = 0

    async def call_structured(self, system_prompt: str, user_input: str, schema: type) -> AIFoodNutrition:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_sort_and_trim_puts_exact_match_first():
    """API는 관련성과 무관한 순서로 주므로, 정확히 일치하는 이름이 맨 앞에 와야 한다."""
    items = [_raw("김밥_돈가스"), _raw("김치찌개_어묵"), _raw("김"), _raw("김밥")]

    result = client.sort_and_trim(items, "김")

    assert [i.food_name for i in result][0] == "김"


def test_sort_and_trim_prefers_prefix_then_shorter_name():
    """'김'으로 시작하는 이름이 '김'을 품기만 한 이름보다 먼저, 같은 순위면 짧은 쪽이 먼저."""
    items = [_raw("삼각김밥_참치마요네즈"), _raw("김밥_돈가스"), _raw("김밥")]

    names = [i.food_name for i in client.sort_and_trim(items, "김")]

    assert names == ["김밥", "김밥_돈가스", "삼각김밥_참치마요네즈"]


def test_sort_and_trim_removes_duplicate_names():
    """'오이김치'처럼 제조사만 다르고 이름이 같은 항목이 여러 건 와도 화면엔 한 줄만."""
    items = [_raw("오이김치", 38.0), _raw("오이김치", 39.0), _raw("오이김치", 40.0)]

    result = client.sort_and_trim(items, "오이김치")

    assert len(result) == 1


def test_sort_and_trim_caps_result_count():
    items = [_raw(f"김밥{i}") for i in range(100)]

    assert len(client.sort_and_trim(items, "김")) == client._MAX_RESULTS


async def test_estimate_food_by_ai_returns_item_for_valid_values():
    gateway = FakeGateway(
        result=AIFoodNutrition(
            food_name="김",
            serving_size_g=5.0,
            calorie_kcal_per_100g=180.0,
            protein_g_per_100g=30.0,
            carb_g_per_100g=40.0,
            fat_g_per_100g=1.0,
        )
    )
    service = DietService(gateway=gateway)

    item = await service.estimate_food_by_ai("김")

    assert item is not None
    assert item.food_name == "김"
    assert item.calorie_kcal_per_100g == 180.0
    assert gateway.call_count == 1


async def test_estimate_food_by_ai_returns_none_when_gateway_fails():
    service = DietService(gateway=FakeGateway(error=AIWorkerUnavailableError("ai_worker 연결 실패")))

    assert await service.estimate_food_by_ai("김") is None


async def test_estimate_food_by_ai_rejects_impossible_calories():
    """100g당 900kcal(순수 지방)을 넘는 값은 환각으로 보고 버린다."""
    gateway = FakeGateway(
        result=AIFoodNutrition(
            food_name="김",
            serving_size_g=100.0,
            calorie_kcal_per_100g=99999.0,
            protein_g_per_100g=1.0,
            carb_g_per_100g=1.0,
            fat_g_per_100g=1.0,
        )
    )

    assert await DietService(gateway=gateway).estimate_food_by_ai("김") is None


async def test_estimate_food_by_ai_rejects_impossible_macro():
    """100g 안의 단백질이 100g을 넘을 수는 없다."""
    gateway = FakeGateway(
        result=AIFoodNutrition(
            food_name="김",
            serving_size_g=100.0,
            calorie_kcal_per_100g=180.0,
            protein_g_per_100g=500.0,
            carb_g_per_100g=1.0,
            fat_g_per_100g=1.0,
        )
    )

    assert await DietService(gateway=gateway).estimate_food_by_ai("김") is None


async def test_estimate_food_by_ai_falls_back_to_100g_for_bad_serving_size():
    """1회 제공량만 이상하면 그 값만 100g으로 되돌리고 나머지는 살린다."""
    gateway = FakeGateway(
        result=AIFoodNutrition(
            food_name="김",
            serving_size_g=0.0,
            calorie_kcal_per_100g=180.0,
            protein_g_per_100g=30.0,
            carb_g_per_100g=40.0,
            fat_g_per_100g=1.0,
        )
    )

    item = await DietService(gateway=gateway).estimate_food_by_ai("김")

    assert item is not None
    assert item.serving_size_g == 100.0
