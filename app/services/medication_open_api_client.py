"""
식약처 공공데이터포털 API 연동 — 의약품 낱알식별정보 조회서비스, 의약품제품 허가정보
조회서비스. `PUBLIC_DATA_API_KEY`가 설정되지 않으면 빈 리스트를 반환한다(로컬 개발 시
키 없이도 계속 동작). `docs/tasks/T-MED-4.md` 참고 — 이 모듈은 API 호출/파싱까지만
담당하고, `medications` 테이블 적재(동기화)는 별도 단계에서 이 모듈을 사용한다.
"""

import httpx

from app.core import config

PILL_IDENTIFICATION_URL = "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService02/getMdcinGrnIdntfcInfoList02"
DRUG_APPROVAL_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService06/getDrugPrdtPrmsnDtlInq05"

_TIMEOUT = 10.0
_DEFAULT_NUM_OF_ROWS = 100


class PublicDataApiError(Exception):
    """공공데이터포털 API가 정상 응답(HTTP 200 & resultCode 00)하지 않았을 때 발생."""


def _normalize_items(items: list[dict] | dict | None) -> list[dict]:
    if items is None:
        return []
    if isinstance(items, dict):
        # 공공데이터포털 API는 결과가 1건이면 items가 {"item": {...}} 형태로 온다.
        item = items.get("item", items)
        return [item] if isinstance(item, dict) else list(item)
    return items


async def _fetch_items(url: str, params: dict) -> list[dict]:
    if not config.PUBLIC_DATA_API_KEY:
        return []

    request_params = {"serviceKey": config.PUBLIC_DATA_API_KEY, "type": "json", **params}

    async with httpx.AsyncClient() as http_client:
        response = await http_client.get(url, params=request_params, timeout=_TIMEOUT)

    if response.status_code != 200:
        raise PublicDataApiError(f"공공데이터포털 API 호출 실패: status={response.status_code}, url={url}")

    payload = response.json()
    envelope = payload.get("response", payload)
    header = envelope.get("header", {})
    result_code = header.get("resultCode")
    if result_code is not None and result_code != "00":
        raise PublicDataApiError(
            f"공공데이터포털 API 오류 응답: resultCode={result_code}, resultMsg={header.get('resultMsg')}, url={url}"
        )

    body = envelope.get("body", {})
    return _normalize_items(body.get("items"))


async def fetch_pill_identification(
    item_name: str | None = None, num_of_rows: int = _DEFAULT_NUM_OF_ROWS, page_no: int = 1
) -> list[dict]:
    """의약품 낱알식별정보 조회서비스 — 알약 모양/색깔/각인 등 외형 정보 포함."""
    params: dict = {"numOfRows": num_of_rows, "pageNo": page_no}
    if item_name:
        params["item_name"] = item_name
    return await _fetch_items(PILL_IDENTIFICATION_URL, params)


async def fetch_drug_approval_info(
    item_name: str | None = None, num_of_rows: int = _DEFAULT_NUM_OF_ROWS, page_no: int = 1
) -> list[dict]:
    """의약품제품 허가정보 조회서비스 — 효능/용법용량/주의사항 등 상세 정보 포함."""
    params: dict = {"numOfRows": num_of_rows, "pageNo": page_no}
    if item_name:
        params["item_name"] = item_name
    return await _fetch_items(DRUG_APPROVAL_URL, params)
