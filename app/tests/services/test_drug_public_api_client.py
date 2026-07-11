"""
T-LLM-2-drug-gateway: `drug_public_api_client.fetch_drug_summary()` 전용 테스트.
실제 네트워크는 호출하지 않고 httpx 응답을 모킹한다.
"""

import httpx

from app.core import config
from app.services import drug_public_api_client

_RealAsyncClient = httpx.AsyncClient


def _mock_transport(handler):
    return _RealAsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_drug_summary_returns_empty_list_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", None)

    result = await drug_public_api_client.fetch_drug_summary("타이레놀")

    assert result == []


async def test_fetch_drug_summary_parses_single_item_response(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "header": {"resultCode": "00"},
                "body": {
                    "items": {
                        "item": {
                            "itemName": "타이레놀정500밀리그람",
                            "entpName": "한국얀센",
                            "efcyQesitm": "감기로 인한 통증 완화",
                        }
                    }
                },
            },
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda: _mock_transport(handler))

    result = await drug_public_api_client.fetch_drug_summary("타이레놀")

    assert result == [
        {"itemName": "타이레놀정500밀리그람", "entpName": "한국얀센", "efcyQesitm": "감기로 인한 통증 완화"}
    ]


async def test_fetch_drug_summary_returns_empty_list_on_non_200_status(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    monkeypatch.setattr(httpx, "AsyncClient", lambda: _mock_transport(handler))

    result = await drug_public_api_client.fetch_drug_summary("타이레놀")

    assert result == []


async def test_fetch_drug_summary_returns_empty_list_on_error_result_code(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"header": {"resultCode": "99", "resultMsg": "APPLICATION_ERROR"}, "body": {}},
        )

    monkeypatch.setattr(httpx, "AsyncClient", lambda: _mock_transport(handler))

    result = await drug_public_api_client.fetch_drug_summary("타이레놀")

    assert result == []


async def test_fetch_drug_summary_returns_empty_list_on_network_error(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_DATA_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(httpx, "AsyncClient", lambda: _mock_transport(handler))

    result = await drug_public_api_client.fetch_drug_summary("타이레놀")

    assert result == []
