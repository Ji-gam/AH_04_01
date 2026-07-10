import asyncio

import httpx

from app.services import medication_service


class _FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("invalid json")
        return self._json_data


class _FakeAsyncClient:
    """`async with httpx.AsyncClient() as client` 흐름을 흉내낸다.
    재시도마다 새 인스턴스가 만들어지므로, 공유 `plan` 리스트를 순서대로 소비한다."""

    def __init__(self, plan: list):
        self._plan = plan

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None, headers=None, timeout=None):
        step = self._plan.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


_original_sleep = asyncio.sleep


def _patch_clova_client(monkeypatch, plan: list):
    monkeypatch.setattr(medication_service, "CLOVA_OCR_SECRET_KEY", "test_secret")
    monkeypatch.setattr(medication_service, "CLOVA_OCR_INVOKE_URL", "https://example.test/ocr")
    monkeypatch.setattr(httpx, "AsyncClient", lambda: _FakeAsyncClient(plan))
    # 재시도 사이 sleep으로 테스트가 느려지지 않게 한다.
    monkeypatch.setattr(asyncio, "sleep", lambda *_args, **_kwargs: _original_sleep(0))


async def test_call_clova_ocr_retries_on_timeout_then_succeeds(monkeypatch):
    success = _FakeResponse(200, json_data={"images": [{"fields": [{"inferText": "타이레놀정"}]}]})
    _patch_clova_client(monkeypatch, [httpx.TimeoutException("timed out"), success])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == ["타이레놀정"]


async def test_call_clova_ocr_gives_up_after_max_attempts_on_repeated_timeout(monkeypatch):
    _patch_clova_client(monkeypatch, [httpx.TimeoutException("timed out"), httpx.TimeoutException("timed out again")])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == []


async def test_call_clova_ocr_retries_on_server_error_then_succeeds(monkeypatch):
    success = _FakeResponse(200, json_data={"images": [{"fields": [{"inferText": "아스피린정"}]}]})
    _patch_clova_client(monkeypatch, [_FakeResponse(503, text="server busy"), success])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == ["아스피린정"]


async def test_call_clova_ocr_does_not_retry_on_auth_error(monkeypatch):
    plan = [_FakeResponse(401, text="invalid secret")]
    _patch_clova_client(monkeypatch, plan)

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == []
    assert plan == []  # 401은 재시도하지 않으므로 plan에서 정확히 1개만 소비되어야 한다


async def test_call_clova_ocr_returns_empty_on_malformed_response_body(monkeypatch):
    _patch_clova_client(monkeypatch, [_FakeResponse(200, json_data=None)])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == []
