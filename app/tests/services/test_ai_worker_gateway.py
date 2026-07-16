import json

import httpx
import pytest
from pydantic import BaseModel

from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)


class FakeCardSchema(BaseModel):
    title: str
    body: str


def _gateway_with_handler(monkeypatch, handler) -> AIWorkerGateway:
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def _patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _patched_client)
    return AIWorkerGateway(base_url="http://ai-worker-test")


async def test_stream_chat_yields_parsed_json_lines(monkeypatch):
    lines = [
        {"type": "sources", "sources": []},
        {"type": "token", "content": "안"},
        {"type": "token", "content": "녕"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n"
        return httpx.Response(200, text=body)

    gateway = _gateway_with_handler(monkeypatch, handler)

    received = [chunk async for chunk in gateway.stream_chat("질문", {}, [], [])]

    assert received == lines


async def test_stream_chat_raises_unavailable_on_503(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="no api key")

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerUnavailableError):
        async for _ in gateway.stream_chat("질문", {}, [], []):
            pass


async def test_stream_chat_raises_invalid_request_on_422(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="bad request")

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerInvalidRequestError):
        async for _ in gateway.stream_chat("질문", {}, [], []):
            pass


async def test_stream_chat_raises_processing_error_on_malformed_line(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not valid json\n")

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerProcessingError):
        async for _ in gateway.stream_chat("질문", {}, [], []):
            pass


async def test_stream_chat_yields_error_chunk_inline_without_raising(monkeypatch):
    """ai_worker가 스트림 도중 실패하면 예외가 아니라 {"type": "error", ...} 인밴드
    청크로 알린다 — 상태 코드로는 더 이상 알릴 수 없기 때문(호출자가 타입으로 구분)."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            json.dumps({"type": "sources", "sources": []})
            + "\n"
            + json.dumps({"type": "token", "content": "안"})
            + "\n"
            + json.dumps({"type": "error", "content": "boom"})
            + "\n"
        )
        return httpx.Response(200, text=body)

    gateway = _gateway_with_handler(monkeypatch, handler)

    received = [chunk async for chunk in gateway.stream_chat("질문", {}, [], [])]

    assert received[-1] == {"type": "error", "content": "boom"}


def _capture_timeout(monkeypatch, captured: dict, response: httpx.Response) -> None:
    real_async_client = httpx.AsyncClient

    def _patched_client(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        kwargs["transport"] = httpx.MockTransport(lambda request: response)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _patched_client)


async def test_stream_chat_uses_generate_timeout(monkeypatch):
    captured: dict = {}
    _capture_timeout(
        monkeypatch, captured, httpx.Response(200, text=json.dumps({"type": "sources", "sources": []}) + "\n")
    )
    gateway = AIWorkerGateway(base_url="http://x", generate_timeout=90.0)

    async for _ in gateway.stream_chat("질문", {}, [], []):
        pass

    assert captured["timeout"] == 90.0


async def test_call_structured_uses_generate_timeout(monkeypatch):
    captured: dict = {}
    _capture_timeout(monkeypatch, captured, httpx.Response(200, json={"data": {"title": "t", "body": "b"}}))
    gateway = AIWorkerGateway(base_url="http://x", generate_timeout=90.0)

    await gateway.call_structured("system", "user", FakeCardSchema)

    assert captured["timeout"] == 90.0


async def test_call_structured_validates_response_against_schema(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"title": "t", "body": "b"}})

    gateway = _gateway_with_handler(monkeypatch, handler)

    result = await gateway.call_structured("system", "user", FakeCardSchema)

    assert result == FakeCardSchema(title="t", body="b")


async def test_call_structured_raises_unavailable_on_503(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="no api key")

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerUnavailableError):
        await gateway.call_structured("system", "user", FakeCardSchema)


async def test_call_structured_raises_processing_error_on_malformed_response(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"unexpected": "shape"}})

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerProcessingError):
        await gateway.call_structured("system", "user", FakeCardSchema)


async def test_enqueue_registers_celery_task_and_returns_id(monkeypatch):
    from app.core.celery_app import celery_app

    class FakeAsyncResult:
        id = "fake-task-id"

    monkeypatch.setattr(celery_app, "send_task", lambda name, kwargs: FakeAsyncResult())

    gateway = AIWorkerGateway(base_url="http://ai-worker-test")
    task_id = gateway.enqueue("app.tasks.some_task", {"foo": "bar"})

    assert task_id == "fake-task-id"
