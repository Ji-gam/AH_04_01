"""
T-LLM-2-drug-gateway: `DurDrugRepository.drug_data()` 캐스케이드의 3번째(외부 API) 단계
전용 식약처 공공데이터포털 e약은요(DrbEasyDrugInfoService) 클라이언트.

`app/services/medication_open_api_client.py`(medication 스쿼드 소유)와 일시적으로
중복된다 — 외부 데이터 연동을 게이트웨이 소유로 통합하기 위한 자체 클라이언트이며,
향후 공용부 이관 시 합칠 대상이다. 게이트웨이가 필요로 하는 e약은요 하나만 구현한다.

`drug_data()` 캐스케이드의 마지막 단계이므로, 호출 실패(네트워크 오류/비정상 응답)로
전체 조회가 죽으면 안 된다 — 실패는 예외를 던지지 않고 빈 리스트로 폴백한다.
"""

import httpx

from app.core import config

DRUG_SUMMARY_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"

_TIMEOUT = 10.0
_NUM_OF_ROWS = 20


def _normalize_items(items: list[dict] | dict | None) -> list[dict]:
    if items is None:
        return []
    if isinstance(items, dict):
        # 결과가 1건이면 items가 {"item": {...}} 형태로 온다(medication_open_api_client.py와 동일 스펙).
        item = items.get("item", items)
        return [item] if isinstance(item, dict) else list(item)
    return items


async def fetch_drug_summary(item_name: str) -> list[dict]:
    """e약은요(의약품개요정보) 조회서비스 — 효능효과(efcyQesitm)/용법용량(useMethodQesitm)/
    주의사항(atpnQesitm 등)/부작용(seQesitm) 요약 텍스트 포함."""
    if not config.PUBLIC_DATA_API_KEY:
        return []

    params: dict[str, str | int] = {
        "serviceKey": config.PUBLIC_DATA_API_KEY,
        "type": "json",
        "numOfRows": _NUM_OF_ROWS,
        "pageNo": 1,
        "itemName": item_name,
    }
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(DRUG_SUMMARY_URL, params=params, timeout=_TIMEOUT)

        if response.status_code != 200:
            return []

        payload = response.json()
        envelope = payload.get("response", payload)
        header = envelope.get("header", {})
        result_code = header.get("resultCode")
        if result_code is not None and result_code != "00":
            return []

        body = envelope.get("body", {})
        return _normalize_items(body.get("items"))
    except (httpx.HTTPError, ValueError):
        return []
