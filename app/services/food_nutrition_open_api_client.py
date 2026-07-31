"""
식약처 공공데이터포털 식품영양성분DB API 연동. `app/services/medication_open_api_client.py`와
같은 패턴(재사용 httpx.AsyncClient, serviceKey 주입, resultCode 확인)을 따른다.

엔드포인트(FOOD_NUTRITION_URL)는 data.go.kr 마이페이지 > 개발계정 상세보기에서 확인한 실제
End Point("FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02")다 - 처음엔 문서 없이 추정한 값
(FoodNtrCpntDbInfo01/getFoodNtrItdntList1)을 넣어놨었는데 그건 존재하지 않는 경로였다(500
에러로 확인). 활용신청 승인 직후엔 게이트웨이 반영 전이라 401이 났는데, 몇 시간 뒤 재시도하니
정상 호출됐다(2026-07-25, 실제 서비스키로 검증) - data.go.kr 승인~실제 반영 사이 지연은
흔한 일이니 새로 승인받은 API가 401이면 좀 기다렸다 재시도할 것.
`_parse_food_item`의 필드 매핑도 이때 실제 응답으로 확인했다: 식품명은 `FOOD_NM_KR`,
1회 제공량은 `SERVING_SIZE`("100g"처럼 단위가 붙은 문자열이라 숫자만 추출), 영양성분은
`AMT_NUM1`~`AMT_NUM7`(식약처 표준 항목 순서: 1=에너지, 2=수분, 3=단백질, 4=지방, 5=회분,
6=탄수화물, 7=당류) 중 1/3/4/6번만 쓴다. 값이 빈 문자열이면(해당 성분 데이터 없음) 0으로
처리한다. 키가 없거나, 있어도 호출/파싱이 실패하면 전부 `app/database/food_nutrition_seed.json`
로컬 시드로 폴백한다 - 앱 기능 자체가 API 상태에 좌우되지 않게 하려는 의도다(CLOVA OCR의
dummy_mode와 같은 발상).
"""

import json
import logging
import re
from pathlib import Path

import httpx

from app.core import config

logger = logging.getLogger("app.food_nutrition_open_api_client")

FOOD_NUTRITION_URL = "https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02"

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


_SERVING_SIZE_NUMBER_RE = re.compile(r"[\d.]+")


def _parse_serving_size_g(raw_value: object) -> float:
    """`SERVING_SIZE`는 "100g"처럼 단위가 붙은 문자열로 온다 - 앞의 숫자만 뽑는다."""
    match = _SERVING_SIZE_NUMBER_RE.search(str(raw_value or ""))
    return float(match.group()) if match else 100.0


def _parse_food_item(raw: dict) -> RawFoodItem | None:
    """실제 서비스키로 호출해 확인한 응답 스펙(2026-07-25) 기준 파싱. 영양성분은
    AMT_NUM1~7 순서로 온다(식약처 식품영양성분DB 표준 항목 순서: 1=에너지, 2=수분, 3=단백질,
    4=지방, 5=회분, 6=탄수화물, 7=당류) - 별도 참고문서 없이 실제 응답값(예: 100g당
    에너지 145kcal/단백질 1.91g/지방 0.29g/탄수화물 33.81g인 즉석밥류)으로 이 순서를
    확인했다. 값이 비어있으면(해당 성분 데이터 없음) 0으로 처리."""
    food_name = raw.get("FOOD_NM_KR")
    if not food_name:
        return None
    return RawFoodItem(
        food_name=str(food_name).strip(),
        serving_size_g=_parse_serving_size_g(raw.get("SERVING_SIZE")),
        calorie_kcal_per_100g=_to_float(raw.get("AMT_NUM1")),
        protein_g_per_100g=_to_float(raw.get("AMT_NUM3")),
        fat_g_per_100g=_to_float(raw.get("AMT_NUM4")),
        carb_g_per_100g=_to_float(raw.get("AMT_NUM6")),
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
