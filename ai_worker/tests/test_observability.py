"""T-LLM-2-langfuse-observability: 관측 팩토리 격리 테스트.

conftest의 autouse 픽스처가 다른 테스트에선 관측을 no-op으로 눌러두므로, 여기서만
`get_langfuse_handler`의 실제 활성/비활성 분기를 검증한다. 실제 Langfuse 서버에는
붙지 않도록(CallbackHandler 생성을 스텁으로 대체) 격리한다.
"""

import os

import pytest

from ai_worker.core import observability

# 실제 함수 객체를 잡아둔다 — conftest의 autouse 픽스처가 모듈 속성을 no-op 람다로
# 바꿔치기해도, 이 바인딩은 원본 함수를 계속 가리킨다.
from ai_worker.core.observability import get_langfuse_handler as real_get_langfuse_handler


@pytest.fixture(autouse=True)
def _reset_observability_cache():
    """팩토리는 결과를 모듈 전역에 캐싱한다 — 각 테스트가 깨끗한 상태에서 시작하도록 리셋."""
    observability._initialized = False
    observability._handler = None
    yield
    observability._initialized = False
    observability._handler = None


def test_returns_none_when_keys_are_not_configured(monkeypatch):
    monkeypatch.setattr(observability.settings, "LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setattr(observability.settings, "LANGFUSE_SECRET_KEY", "")

    assert real_get_langfuse_handler() is None


def test_is_configured_requires_both_public_and_secret_key(monkeypatch):
    monkeypatch.setattr(observability.settings, "LANGFUSE_PUBLIC_KEY", "pk-lf-x")
    monkeypatch.setattr(observability.settings, "LANGFUSE_SECRET_KEY", "")
    assert observability._is_configured() is False

    monkeypatch.setattr(observability.settings, "LANGFUSE_SECRET_KEY", "sk-lf-x")
    assert observability._is_configured() is True


def test_returns_handler_and_bridges_env_when_configured(monkeypatch):
    monkeypatch.setattr(observability.settings, "LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setattr(observability.settings, "LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setattr(observability.settings, "LANGFUSE_BASE_URL", "https://example.test")
    # 코드가 os.environ에 직접 쓰므로, monkeypatch가 원복하도록 스냅샷을 먼저 잡아둔다.
    for var in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "LANGFUSE_BASE_URL"):
        monkeypatch.setenv(var, "")

    sentinel = object()
    # 실제 CallbackHandler 생성(네트워크/스레드)을 막기 위해 지연 import 대상을 스텁으로 대체.
    import langfuse.langchain as lf_langchain

    monkeypatch.setattr(lf_langchain, "CallbackHandler", lambda: sentinel)

    handler = real_get_langfuse_handler()

    assert handler is sentinel
    # settings 값이 표준 환경변수로 브릿지됐는지(호스트는 두 변수명 모두)
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-lf-test"
    assert os.environ["LANGFUSE_SECRET_KEY"] == "sk-lf-test"
    assert os.environ["LANGFUSE_HOST"] == "https://example.test"
    assert os.environ["LANGFUSE_BASE_URL"] == "https://example.test"


def test_result_is_cached_after_first_call(monkeypatch):
    monkeypatch.setattr(observability.settings, "LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setattr(observability.settings, "LANGFUSE_SECRET_KEY", "")

    first = real_get_langfuse_handler()
    assert observability._initialized is True
    second = real_get_langfuse_handler()
    assert first is second is None
