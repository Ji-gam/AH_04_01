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
    """e약은요(의약품개요정보) API — 효능효과/용법용량/주의사항 텍스트 포함."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")
    items = [{"ITEM_NAME": "타이레놀정500밀리그람", "EE_DOC_DATA": "해열, 진통", "UD_DOC_DATA": "1회 1~2정"}]

    async def _fake_get(self, url, params=None, timeout=None):
        assert url == client.DRUG_SUMMARY_URL
        assert params["item_name"] == "타이레놀"
        return _FakeResponse(200, _wrap_response(items))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_drug_summary(item_name="타이레놀")

    assert result == items


async def test_fetch_dur_item_info_parses_items(monkeypatch):
    """DUR 품목정보(병용금기 등) API — 품목 단위 병용금기/주의 정보."""
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-service-key")
    items = [{"ITEM_NAME": "타이레놀정500밀리그람", "MIXTURE_NAME": "와파린", "PROHBT_CONTENT": "병용금기"}]

    async def _fake_get(self, url, params=None, timeout=None):
        assert url == client.DUR_ITEM_INFO_URL
        assert params["itemName"] == "타이레놀"
        return _FakeResponse(200, _wrap_response(items))

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    result = await client.fetch_dur_item_info(item_name="타이레놀")

    assert result == items


async def test_fetch_drug_summary_returns_empty_list_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)

    async def _fail_get(*args, **kwargs):
        raise AssertionError("API 키가 없으면 HTTP 호출 자체가 발생하면 안 된다")

    monkeypatch.setattr(httpx.AsyncClient, "get", _fail_get)

    assert await client.fetch_drug_summary(item_name="타이레놀") == []
    assert await client.fetch_dur_item_info(item_name="타이레놀") == []
