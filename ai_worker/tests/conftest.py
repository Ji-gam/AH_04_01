"""ai_worker 테스트 공용 픽스처.

T-LLM-2-langfuse-observability: 로컬 `.env`에 Langfuse 키가 채워져 있으면 테스트가
실제 Langfuse 서버로 trace를 쏠 수 있다. 관측을 전 테스트에서 강제 no-op으로 둬서,
테스트가 네트워크/외부 계정에 의존하거나 데이터를 오염시키지 않게 한다. (관측 자체의
활성/비활성 분기는 test_observability.py가 격리해서 따로 검증한다.)
"""

import pytest

from ai_worker.core import observability


@pytest.fixture(autouse=True)
def _disable_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observability, "get_langfuse_handler", lambda: None)
    monkeypatch.setattr(observability, "get_langfuse_client", lambda: None)
