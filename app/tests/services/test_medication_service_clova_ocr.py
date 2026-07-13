import asyncio
import base64
import io

import httpx
from PIL import Image

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
    success = _FakeResponse(
        200, json_data={"images": [{"fields": [{"inferText": "타이레놀정", "inferConfidence": 0.97}]}]}
    )
    _patch_clova_client(monkeypatch, [httpx.TimeoutException("timed out"), success])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == [medication_service.OcrField(text="타이레놀정", confidence=0.97)]


async def test_call_clova_ocr_gives_up_after_max_attempts_on_repeated_timeout(monkeypatch):
    _patch_clova_client(monkeypatch, [httpx.TimeoutException("timed out"), httpx.TimeoutException("timed out again")])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == []


async def test_call_clova_ocr_retries_on_server_error_then_succeeds(monkeypatch):
    success = _FakeResponse(
        200, json_data={"images": [{"fields": [{"inferText": "아스피린정", "inferConfidence": 0.8}]}]}
    )
    _patch_clova_client(monkeypatch, [_FakeResponse(503, text="server busy"), success])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == [medication_service.OcrField(text="아스피린정", confidence=0.8)]


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


async def test_call_clova_ocr_defaults_confidence_to_zero_when_missing_or_invalid(monkeypatch):
    """(T-MED-6) `inferConfidence`가 아예 없거나 숫자로 변환할 수 없으면 매칭률 계산이 죽지
    않도록 0.0으로 취급해야 한다."""
    response = _FakeResponse(
        200,
        json_data={
            "images": [
                {
                    "fields": [
                        {"inferText": "신뢰도없음정"},
                        {"inferText": "신뢰도이상함정", "inferConfidence": "not-a-number"},
                    ]
                }
            ]
        },
    )
    _patch_clova_client(monkeypatch, [response])

    result = await medication_service._call_clova_ocr(b"bytes", "pill.jpg")

    assert result == [
        medication_service.OcrField(text="신뢰도없음정", confidence=0.0),
        medication_service.OcrField(text="신뢰도이상함정", confidence=0.0),
    ]


def _make_webp_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color="red").save(buffer, format="WEBP")
    return buffer.getvalue()


def test_build_clova_ocr_request_converts_unsupported_format_to_png():
    """(#101) webp처럼 CLOVA가 지원하지 않는 포맷을 "jpg"라고만 표시해서 그대로 보내면,
    실제 바이트와 라벨이 달라 CLOVA가 400(Request invalid)을 반환하고 조용히 더미로
    폴백되던 문제가 있었다. 이제는 실제로 png로 변환한 바이트를 보내야 한다."""
    webp_bytes = _make_webp_bytes()

    payload, _headers = medication_service._build_clova_ocr_request(webp_bytes, "prescription.webp")

    assert payload["images"][0]["format"] == "png"
    converted_bytes = base64.b64decode(payload["images"][0]["data"])
    assert converted_bytes != webp_bytes
    # 변환된 바이트가 실제로 유효한 PNG인지 재확인
    Image.open(io.BytesIO(converted_bytes)).load()


def test_build_clova_ocr_request_keeps_supported_format_untouched():
    """jpg처럼 이미 지원되는 포맷은 변환 없이 원본 바이트를 그대로 보내야 한다."""
    original_bytes = b"fake-jpeg-bytes"

    payload, _headers = medication_service._build_clova_ocr_request(original_bytes, "prescription.jpg")

    assert payload["images"][0]["format"] == "jpg"
    assert base64.b64decode(payload["images"][0]["data"]) == original_bytes
