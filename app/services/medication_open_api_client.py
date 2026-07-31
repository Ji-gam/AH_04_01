"""
식약처 공공데이터포털 API 연동 — 의약품 낱알식별정보 조회서비스, 의약품제품 허가정보
조회서비스. `PUBLIC_DATA_API_KEY`가 설정되지 않으면 빈 리스트를 반환한다(로컬 개발 시
키 없이도 계속 동작). `docs/tasks/T-MED-4.md` 참고 — 이 모듈은 API 호출/파싱까지만
담당하고, `medications` 테이블 적재(동기화)는 별도 단계에서 이 모듈을 사용한다.
"""

import asyncio

import httpx

from app.core import config

# 아래 4개 URL/파라미터명은 실제 발급받은 서비스키로 호출해 검증한 값이다(2026-07-08).
# 공공데이터포털은 서비스 버전이 사전 공지 없이 올라가고(예: 01→02→03) 예전 버전은 404/500으로
# 죽는 경우가 흔하므로, 나중에 호출이 갑자기 실패하면 가장 먼저 버전 번호를 의심할 것.
PILL_IDENTIFICATION_URL = "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03"
DRUG_APPROVAL_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnInq07"
DRUG_SUMMARY_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
DUR_ITEM_INFO_URL = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03/getUsjntTabooInfoList03"

_TIMEOUT = 10.0
_DEFAULT_NUM_OF_ROWS = 100

# (#195) 확정등록/음식탭 조회가 약품 개수만큼 이 클라이언트를 호출하는데, 매번 새
# httpx.AsyncClient()를 만들면 매 호출마다 커넥션을 새로 맺어 그만큼 느려진다. 프로세스
# 수명 동안 하나만 만들어 재사용한다(연결 풀 유지) — 앱 종료 시 close_http_client()로 정리.
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


async def close_http_client() -> None:
    """앱 종료(lifespan) 시 호출 — 재사용 중인 커넥션 풀을 정리한다."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


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

    http_client = _get_http_client()
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
    """e약은요(의약품개요정보) 조회서비스 — 효능효과(efcyQesitm)/용법용량(useMethodQesitm)/
    부작용(seQesitm)/보관법(depositMethodQesitm) 등 요약 텍스트 포함. 응답 필드가 다른 세 API와
    달리 camelCase다. 이 서비스는 파라미터명도 `itemName`(카멜케이스)으로, 다른 두 API의
    `item_name`(스네이크케이스)과 다르다 — 공공데이터포털 서비스별로 명명 규칙이 다른 것이
    실제 스펙이다(실 서비스키로 검증, 2026-07-08)."""
    params: dict = {"numOfRows": num_of_rows, "pageNo": page_no}
    if item_name:
        params["itemName"] = item_name
    return await _fetch_items(DRUG_SUMMARY_URL, params)


async def fetch_dur_item_info(
    item_seq: str | None = None, num_of_rows: int = _DEFAULT_NUM_OF_ROWS, page_no: int = 1
) -> list[dict]:
    """DUR 품목정보(병용금기 등) 조회서비스 — 품목 단위 병용금기 등 정보(`PROHBT_CONTENT`).
    이 서비스는 약품명이 아니라 품목기준코드(`item_seq`, 낱알식별/허가정보 응답의 `ITEM_SEQ`)로만
    필터링된다 — 약품명 파라미터는 조용히 무시되고 전체 데이터셋(80만 건 이상)이 그대로 반환되므로,
    `item_seq` 없이는 호출하지 않는다(실 서비스키로 검증, 2026-07-08)."""
    if not item_seq:
        return []
    params: dict = {"numOfRows": num_of_rows, "pageNo": page_no, "itemSeq": item_seq}
    return await _fetch_items(DUR_ITEM_INFO_URL, params)


async def fetch_medication_master_data(item_name: str) -> dict | None:
    """세 API(낱알식별/허가정보/e약은요)를 병렬 조회해 품목기준코드(`item_seq`)를 얻고, 그 코드로
    DUR 품목정보까지 이어서 조회한 뒤 `Medication` 컬럼에 바로 대입할 수 있는 필드 딕셔너리로
    병합한다. 실시간 매칭 폴백(Tier 3)과 배치 동기화 스크립트(Tier 2 적재) 양쪽에서 공용으로 쓴다.
    세 API가 모두 빈 응답이면 None. 허가정보(v07) API에는 용법/부작용/보관법 텍스트가 없어(품목
    허가 메타데이터만 제공) 그 텍스트는 e약은요에서 가져온다."""
    pill_items, approval_items, summary_items = await asyncio.gather(
        fetch_pill_identification(item_name=item_name),
        fetch_drug_approval_info(item_name=item_name),
        fetch_drug_summary(item_name=item_name),
    )
    pill = pill_items[0] if pill_items else {}
    approval = approval_items[0] if approval_items else {}
    summary = summary_items[0] if summary_items else {}

    if not pill and not approval and not summary:
        return None

    item_seq = pill.get("ITEM_SEQ") or approval.get("ITEM_SEQ") or summary.get("itemSeq")
    dur_items = await fetch_dur_item_info(item_seq=item_seq) if item_seq else []
    dur = dur_items[0] if dur_items else {}

    return {
        "standard_code": f"PDP_{item_seq}" if item_seq else None,
        "dosage_guideline": summary.get("useMethodQesitm"),
        "side_effects": dur.get("PROHBT_CONTENT") or summary.get("seQesitm"),
        "storage_method": summary.get("depositMethodQesitm"),
        "shape": pill.get("DRUG_SHAPE"),
        "color": pill.get("COLOR_CLASS1"),
        "letters": pill.get("PRINT_FRONT"),
    }
