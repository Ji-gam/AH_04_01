"""
식약처 공공데이터포털 식품영양성분DB API 연동. `app/services/medication_open_api_client.py`와
같은 패턴(재사용 httpx.AsyncClient, serviceKey 주입, resultCode 확인)을 따른다.

이 API는 아직 실제 서비스키로 검증되지 않았다 - `_parse_food_item`의 필드명(DESC_KOR,
NUTR_CONT1~4, SERVING_SIZE 등)은 data.go.kr 문서 기준 추정치이며, 실제 키를 발급받아 호출해보면
필드명이 다를 수 있다(medication_open_api_client.py의 선례처럼 공공데이터포털은 서비스마다
명명 규칙이 제각각이다). 키가 없거나, 있어도 호출/파싱이 실패하면 전부
`app/database/food_nutrition_seed.json` 로컬 시드로 폴백한다 - 승인 대기 중에도 기능 자체는
막히지 않게 하려는 의도다(CLOVA OCR의 dummy_mode와 같은 발상).
"""

import json
import logging
from pathlib import Path

import httpx

from app.core import config

logger = logging.getLogger("app.food_nutrition_open_api_client")

FOOD_NUTRITION_URL = "https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo01/getFoodNtrItdntList1"

_TIMEOUT = 10.0
_DEFAULT_NUM_OF_ROWS = 20

_SEED_PATH = Path(__file__).resolve().parent.parent / "database" / "food_nutrition_seed.json"

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


async def close_http_client() -> None:
    """앱 종료(lifespan) 시 호출 - 재사용 중인 커넥션 풀을 정리한다."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


class RawFoodItem:
    """외부 API/시드 어느 쪽에서 왔든 동일한 모양으로 맞춘 중간 표현."""

    def __init__(
        self,
        food_name: str,
        serving_size_g: float,
        calorie_kcal_per_100g: float,
        protein_g_per_100g: float,
        carb_g_per_100g: float,
        fat_g_per_100g: float,
    ) -> None:
        self.food_name = food_name
        self.serving_size_g = serving_size_g
        self.calorie_kcal_per_100g = calorie_kcal_per_100g
        self.protein_g_per_100g = protein_g_per_100g
        self.carb_g_per_100g = carb_g_per_100g
        self.fat_g_per_100g = fat_g_per_100g


def _normalize_items(items: list[dict] | dict | None) -> list[dict]:
    if items is None:
        return []
    if isinstance(items, dict):
        item = items.get("item", items)
        return [item] if isinstance(item, dict) else list(item)
    return items


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _parse_food_item(raw: dict) -> RawFoodItem | None:
    food_name = raw.get("DESC_KOR") or raw.get("FOOD_NM_KR")
    if not food_name:
        return None
    return RawFoodItem(
        food_name=str(food_name).strip(),
        serving_size_g=_to_float(raw.get("SERVING_SIZE"), default=100.0) or 100.0,
        calorie_kcal_per_100g=_to_float(raw.get("NUTR_CONT1")),
        protein_g_per_100g=_to_float(raw.get("NUTR_CONT3")),
        fat_g_per_100g=_to_float(raw.get("NUTR_CONT4")),
        carb_g_per_100g=_to_float(raw.get("NUTR_CONT2")),
    )


async def _fetch_live(query: str) -> list[RawFoodItem]:
    api_key = config.FOOD_NUTRITION_API_KEY or config.PUBLIC_DATA_API_KEY
    if not api_key:
        return []

    params: dict = {
        "serviceKey": api_key,
        "type": "json",
        "numOfRows": _DEFAULT_NUM_OF_ROWS,
        "pageNo": 1,
        "FOOD_NM_KR": query,
    }
    http_client = _get_http_client()
    response = await http_client.get(FOOD_NUTRITION_URL, params=params, timeout=_TIMEOUT)
    response.raise_for_status()

    payload = response.json()
    envelope = payload.get("response", payload)
    header = envelope.get("header", {})
    result_code = header.get("resultCode")
    if result_code is not None and result_code != "00":
        raise ValueError(f"식품영양성분DB API 오류 응답: resultCode={result_code}, resultMsg={header.get('resultMsg')}")

    body = envelope.get("body", {})
    items = _normalize_items(body.get("items"))
    return [parsed for raw in items if (parsed := _parse_food_item(raw)) is not None]


def _search_seed(query: str) -> list[RawFoodItem]:
    with _SEED_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    query_lower = query.strip().lower()
    return [
        RawFoodItem(
            food_name=food["food_name"],
            serving_size_g=food["serving_size_g"],
            calorie_kcal_per_100g=food["calorie_kcal_per_100g"],
            protein_g_per_100g=food["protein_g_per_100g"],
            carb_g_per_100g=food["carb_g_per_100g"],
            fat_g_per_100g=food["fat_g_per_100g"],
        )
        for food in data["foods"]
        if query_lower in food["food_name"].lower()
    ]


async def search_food(query: str) -> list[RawFoodItem]:
    """식품명으로 영양성분을 검색한다. 라이브 API가 설정돼 있어도 호출/파싱이 실패하면
    (타임아웃, 5xx, 예상과 다른 응답 필드 등) 예외를 삼키고 시드 폴백으로 넘어간다 - API 승인이
    안 났거나 필드 매핑이 안 맞는 상태에서도 화면이 죽지 않게 하는 게 이 함수의 핵심 책임이다."""
    try:
        live_results = await _fetch_live(query)
        if live_results:
            return live_results
    except Exception:
        logger.warning("식품영양성분DB API 호출 실패, 로컬 시드로 폴백합니다 (query=%s)", query, exc_info=True)

    return _search_seed(query)
