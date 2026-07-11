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


async def test_search_returns_chunks_on_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"chunks": [{"content": "c", "metadata": {}}]})

    gateway = _gateway_with_handler(monkeypatch, handler)

    chunks = await gateway.search("query")

    assert chunks == [{"content": "c", "metadata": {}}]


async def test_search_raises_unavailable_on_5xx(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerUnavailableError):
        await gateway.search("query")


async def test_search_raises_invalid_request_on_422(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="bad request")

    gateway = _gateway_with_handler(monkeypatch, handler)

    with pytest.raises(AIWorkerInvalidRequestError):
        await gateway.search("query")


def _capture_timeout(monkeypatch, captured: dict, response: httpx.Response) -> None:
    real_async_client = httpx.AsyncClient

    def _patched_client(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        kwargs["transport"] = httpx.MockTransport(lambda request: response)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _patched_client)


async def test_search_uses_retrieve_timeout(monkeypatch):
    """검색(/retrieve)은 짧은 retrieve 타임아웃을 쓴다."""
    captured: dict = {}
    _capture_timeout(monkeypatch, captured, httpx.Response(200, json={"chunks": []}))
    gateway = AIWorkerGateway(base_url="http://x", retrieve_timeout=3.0, generate_timeout=90.0)

    await gateway.search("query")

    assert captured["timeout"] == 3.0


async def test_call_structured_uses_generate_timeout(monkeypatch):
    """생성(/generate-structured)은 긴 generate 타임아웃을 쓴다(5초 초과 정상 생성 보호)."""
    captured: dict = {}
    _capture_timeout(monkeypatch, captured, httpx.Response(200, json={"data": {"title": "t", "body": "b"}}))
    gateway = AIWorkerGateway(base_url="http://x", retrieve_timeout=3.0, generate_timeout=90.0)

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
