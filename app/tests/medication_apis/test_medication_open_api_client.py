import httpx
import pytest

from app.core import config
from app.services import medication_open_api_client as client


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _wrap_response(items: list[dict] | dict, result_code: str = "00") -> dict:
    return {
        "response": {
            "header": {"resultCode": result_code, "resultMsg": "NORMAL SERVICE"},
            "body": {
                "items": items,
                "numOfRows": 100,
                "pageNo": 1,
                "totalCount": len(items) if isinstance(items, list) else 1,
            },
        }
    }


async def test_fetch_pill_identification_returns_empty_list_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)

    async def _fail_get(*args, **kwargs):
        raise AssertionError("API 키가 없으면 HTTP 호출 자체가 발생하면 안 된다")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail_get)

    result = await client.fetch_pill_identification(item_name="타이레놀")

    assert result == []


async def test_fetch_pill_identification_parses_items(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")

    items = [
        {"ITEM_NAME": "타이레놀정500밀리그람", "DRUG_SHAPE": "원형", "COLOR_CLASS1": "하양", "PRINT_FRONT": "TYLENOL"}
    ]

    async def _fake_get(self, url, params=None, timeout=None):
        assert url == client.PILL_IDENTIFICATION_URL
        assert params["serviceKey"] == "test-service-key"
        assert params["item_name"] == "타이레놀"
        return _FakeResponse(200, _wrap_response(items))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_pill_identification(item_name="타이레놀")

    assert result == items


async def test_fetch_pill_identification_normalizes_single_item_dict(monkeypatch):
    """공공데이터포털 API는 결과가 1건이면 item이 리스트가 아니라 dict로 오는 경우가 있다."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")
    single_item = {"ITEM_NAME": "아스피린정100밀리그람"}

    async def _fake_get(self, url, params=None, timeout=None):
        return _FakeResponse(200, _wrap_response({"item": single_item}))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_pill_identification(item_name="아스피린")

    assert result == [single_item]


async def test_fetch_drug_approval_info_parses_items(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")
    items = [{"ITEM_NAME": "타이레놀정500밀리그람", "EE_DOC_DATA": "해열, 진통", "NB_DOC_DATA": "간질환 환자 주의"}]

    async def _fake_get(self, url, params=None, timeout=None):
        assert url == client.DRUG_APPROVAL_URL
        return _FakeResponse(200, _wrap_response(items))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_drug_approval_info(item_name="타이레놀")

    assert result == items


async def test_fetch_raises_on_non_200_status(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")

    async def _fake_get(self, url, params=None, timeout=None):
        return _FakeResponse(500, {})

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    with pytest.raises(client.PublicDataApiError):
        await client.fetch_pill_identification(item_name="타이레놀")


async def test_fetch_raises_on_error_result_code(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")

    async def _fake_get(self, url, params=None, timeout=None):
        return _FakeResponse(200, _wrap_response([], result_code="30"))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    with pytest.raises(client.PublicDataApiError):
        await client.fetch_drug_approval_info(item_name="타이레놀")


async def test_fetch_drug_summary_parses_items(monkeypatch):
    """e약은요(의약품개요정보) API — 효능효과(efcyQesitm)/용법용량(useMethodQesitm) 등 camelCase
    필드, 파라미터도 itemName(카멜케이스)이 실제 스펙이다."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")
    items = [{"itemName": "타이레놀정500밀리그람", "efcyQesitm": "해열, 진통", "useMethodQesitm": "1회 1~2정"}]

    async def _fake_get(self, url, params=None, timeout=None):
        assert url == client.DRUG_SUMMARY_URL
        assert params["itemName"] == "타이레놀"
        return _FakeResponse(200, _wrap_response(items))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_drug_summary(item_name="타이레놀")

    assert result == items


async def test_fetch_dur_item_info_parses_items(monkeypatch):
    """DUR 품목정보(병용금기 등) API — 약품명이 아니라 item_seq(품목기준코드)로 조회한다."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")
    items = [{"ITEM_NAME": "타이레놀정500밀리그람", "MIXTURE_NAME": "와파린", "PROHBT_CONTENT": "병용금기"}]

    async def _fake_get(self, url, params=None, timeout=None):
        assert url == client.DUR_ITEM_INFO_URL
        assert params["itemSeq"] == "200000407"
        return _FakeResponse(200, _wrap_response(items))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_dur_item_info(item_seq="200000407")

    assert result == items


async def test_fetch_dur_item_info_without_item_seq_returns_empty_without_calling_api(monkeypatch):
    """item_seq 없이 호출하면 필터가 무시되고 전체 데이터셋(80만 건+)이 그대로 오는 것이 실제
    스펙이라, item_seq가 없을 때는 API를 호출하지 않고 즉시 빈 리스트를 반환해야 한다."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")

    async def _fail_get(*args, **kwargs):
        raise AssertionError("item_seq 없이는 DUR API를 호출하면 안 된다")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail_get)

    assert await client.fetch_dur_item_info(item_seq=None) == []


async def test_fetch_drug_summary_returns_empty_list_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)

    async def _fail_get(*args, **kwargs):
        raise AssertionError("API 키가 없으면 HTTP 호출 자체가 발생하면 안 된다")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail_get)

    assert await client.fetch_drug_summary(item_name="타이레놀") == []
    assert await client.fetch_dur_item_info(item_seq="200000407") == []


async def test_fetch_medication_master_data_merges_pill_summary_and_dur(monkeypatch):
    """item_seq를 낱알식별에서 얻어 DUR을 이어서 조회하고, 용법/부작용/보관법은 e약은요에서 온다."""

    async def _fake_pill(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "200000001", "DRUG_SHAPE": "원형", "COLOR_CLASS1": "하양", "PRINT_FRONT": "TYLENOL"}]

    async def _fake_approval(item_name=None, **kwargs):
        return [{"ITEM_SEQ": "200000001", "ITEM_INGR_NAME": "Acetaminophen"}]

    async def _fake_summary(item_name=None, **kwargs):
        return [
            {"itemSeq": "200000001", "useMethodQesitm": "1회 1정", "seQesitm": "구토", "depositMethodQesitm": "실온"}
        ]

    async def _fake_dur(item_seq=None, **kwargs):
        assert item_seq == "200000001"
        return [{"PROHBT_CONTENT": "와파린과 병용금기"}]

    monkeypatch.setattr(client, "fetch_pill_identification", _fake_pill)
    monkeypatch.setattr(client, "fetch_drug_approval_info", _fake_approval)
    monkeypatch.setattr(client, "fetch_drug_summary", _fake_summary)
    monkeypatch.setattr(client, "fetch_dur_item_info", _fake_dur)

    result = await client.fetch_medication_master_data("타이레놀정500밀리그람")

    assert result == {
        "standard_code": "PDP_200000001",
        "dosage_guideline": "1회 1정",
        "side_effects": "와파린과 병용금기",
        "storage_method": "실온",
        "shape": "원형",
        "color": "하양",
        "letters": "TYLENOL",
    }


async def test_fetch_medication_master_data_falls_back_to_summary_side_effects_when_dur_empty(monkeypatch):
    """DUR에 병용금기가 없으면(item_seq는 있지만 결과 없음) e약은요의 부작용 텍스트로 대체한다."""

    async def _fake_pill(item_name=None, **kwargs):
        return []

    async def _fake_approval(item_name=None, **kwargs):
        return []

    async def _fake_summary(item_name=None, **kwargs):
        return [{"itemSeq": "300000002", "useMethodQesitm": "요약 용법", "seQesitm": "메스꺼움"}]

    async def _fake_dur(item_seq=None, **kwargs):
        return []

    monkeypatch.setattr(client, "fetch_pill_identification", _fake_pill)
    monkeypatch.setattr(client, "fetch_drug_approval_info", _fake_approval)
    monkeypatch.setattr(client, "fetch_drug_summary", _fake_summary)
    monkeypatch.setattr(client, "fetch_dur_item_info", _fake_dur)

    result = await client.fetch_medication_master_data("아무개약")

    assert result["standard_code"] == "PDP_300000002"
    assert result["dosage_guideline"] == "요약 용법"
    assert result["side_effects"] == "메스꺼움"


async def test_fetch_medication_master_data_returns_none_when_all_sources_empty(monkeypatch):
    async def _empty(*args, **kwargs):
        return []

    monkeypatch.setattr(client, "fetch_pill_identification", _empty)
    monkeypatch.setattr(client, "fetch_drug_approval_info", _empty)
    monkeypatch.setattr(client, "fetch_drug_summary", _empty)
    monkeypatch.setattr(client, "fetch_dur_item_info", _empty)

    assert await client.fetch_medication_master_data("존재하지않는약") is None
