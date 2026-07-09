"""
식약처 공공데이터포털 API 연동 — 의약품 낱알식별정보 조회서비스, 의약품제품 허가정보
조회서비스. `PUBLIC_DATA_API_KEY`가 설정되지 않으면 빈 리스트를 반환한다(로컬 개발 시
키 없이도 계속 동작). `docs/tasks/T-MED-4.md` 참고 — 이 모듈은 API 호출/파싱까지만
담당하고, `medications` 테이블 적재(동기화)는 별도 단계에서 이 모듈을 사용한다.
"""

import asyncio

import httpx

from app.core import config

PILL_IDENTIFICATION_URL = "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService02/getMdcinGrnIdntfcInfoList02"
DRUG_APPROVAL_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService06/getDrugPrdtPrmsnDtlInq05"
DRUG_SUMMARY_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
DUR_ITEM_INFO_URL = "https://apis.data.go.kr/1471000/DURPrdlstInfoService02/getUsjntTabooInfoList02"

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


async def fetch_drug_summary(
    item_name: str | None = None, num_of_rows: int = _DEFAULT_NUM_OF_ROWS, page_no: int = 1
) -> list[dict]:
    """e약은요(의약품개요정보) 조회서비스 — 효능효과/용법용량/주의사항 요약 텍스트 포함."""
    params: dict = {"numOfRows": num_of_rows, "pageNo": page_no}
    if item_name:
        params["item_name"] = item_name
    return await _fetch_items(DRUG_SUMMARY_URL, params)


async def fetch_dur_item_info(
    item_name: str | None = None, num_of_rows: int = _DEFAULT_NUM_OF_ROWS, page_no: int = 1
) -> list[dict]:
    """DUR 품목정보(병용금기 등) 조회서비스 — 품목 단위 병용금기/노인주의/임부금기 등 정보.
    이 서비스는 파라미터명이 `itemName`(카멜케이스)으로, 다른 세 API의 `item_name`(스네이크케이스)과
    다르다 — 공공데이터포털 서비스별로 파라미터 명명 규칙이 다른 것이 실제 스펙이다."""
    params: dict = {"numOfRows": num_of_rows, "pageNo": page_no}
    if item_name:
        params["itemName"] = item_name
    return await _fetch_items(DUR_ITEM_INFO_URL, params)


async def fetch_medication_master_data(item_name: str) -> dict | None:
    """네 API(낱알식별/허가정보/e약은요/DUR 품목정보)를 모두 조회해 `Medication` 컬럼에 바로
    대입할 수 있는 필드 딕셔너리로 병합한다. 실시간 매칭 폴백(Tier 3)과 배치 동기화 스크립트
    (Tier 2 적재) 양쪽에서 공용으로 쓴다. 낱알식별/허가정보/e약은요 모두 빈 응답이면 None."""
    pill_items, approval_items, summary_items, dur_items = await asyncio.gather(
        fetch_pill_identification(item_name=item_name),
        fetch_drug_approval_info(item_name=item_name),
        fetch_drug_summary(item_name=item_name),
        fetch_dur_item_info(item_name=item_name),
    )
    pill = pill_items[0] if pill_items else {}
    approval = approval_items[0] if approval_items else {}
    summary = summary_items[0] if summary_items else {}
    dur = dur_items[0] if dur_items else {}

    if not pill and not approval and not summary:
        return None

    item_seq = pill.get("ITEM_SEQ") or approval.get("ITEM_SEQ") or summary.get("ITEM_SEQ")
    return {
        "standard_code": f"PDP_{item_seq}" if item_seq else None,
        "dosage_guideline": approval.get("UD_DOC_DATA") or summary.get("UD_DOC_DATA"),
        "side_effects": dur.get("PROHBT_CONTENT") or approval.get("NB_DOC_DATA"),
        "storage_method": approval.get("STORAGE_METHOD"),
        "shape": pill.get("DRUG_SHAPE"),
        "color": pill.get("COLOR_CLASS1"),
        "letters": pill.get("PRINT_FRONT"),
    }
