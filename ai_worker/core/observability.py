"""T-LLM-2-langfuse-observability: LLM 호출 관측(Langfuse) 진입점.

`ai_worker`의 LLM 호출부(`tasks/chat_agent.py`, `tasks/generate_structured.py`)가 공유하는
LangChain 콜백 핸들러 팩토리. 두 task 모듈이 각자 `_build_llm()`/`_build_chain()`을 갖고 있어
공유 지점이 없으므로, 관측 설정을 이 한 곳으로 모은다(호출부엔 `get_langfuse_handler()` 한 줄만).

관측은 **선택**이다: Langfuse 키가 없으면(로컬 개발, CI) `None`을 돌려주고 호출부는 콜백을
그냥 생략한다 — 챗봇/구조화 생성은 종전과 완전히 동일하게 동작한다(무회귀).

T-LLM-2-langfuse-retrieval-span(2단계): `get_langfuse_client()`/`observe_span()`은 RAG 검색
단계(`retrieve_service.search_documents`, `paper_retrieve_service.search_papers`)를 수동
span으로 계측하는 데 쓴다. `get_client()`가 `CallbackHandler()`와 같은 v4 전역 싱글톤을
돌려주므로(실측 확인됨), 여기서 연 span과 LLM 호출부가 만드는 generation이 별도 설정 없이도
같은 trace로 묶인다.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal, cast

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger

logger = setup_logger("ai_worker.observability")

# 핸들러/클라이언트 생성은 한 번만 시도하고 결과(값 or None)를 캐싱한다.
_handler: Any = None
_handler_initialized = False
_client: Any = None
_client_initialized = False


def _is_configured() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def _bridge_env() -> None:
    """pydantic-settings는 .env를 `settings`로만 읽고 os.environ에는 넣지 않는다.
    Langfuse SDK(v4)는 전역 클라이언트를 표준 환경변수에서 초기화하므로, 여기서
    settings 값을 환경변수로 브릿지해 "설정 단일 소스 = config.py"를 유지한다.
    호스트 변수명이 SDK 패치 버전에 따라 LANGFUSE_HOST / LANGFUSE_BASE_URL로 갈려
    있어 둘 다 세팅한다(같은 값, 무해). `get_langfuse_handler()`/`get_langfuse_client()`
    어느 쪽이 먼저 불려도 안전하도록 매번 호출해도 무해하게(idempotent) 만든다."""
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_BASE_URL"] = settings.LANGFUSE_BASE_URL


def get_langfuse_handler() -> Any:
    """Langfuse LangChain 콜백 핸들러를 반환하거나, 미설정이면 ``None``을 반환한다.

    호출부는 반환값이 있을 때만 ``config={"callbacks": [handler]}``로 넘기면 된다.
    최초 1회만 초기화하고 이후엔 캐싱된 값을 돌려준다.
    """
    global _handler, _handler_initialized
    if _handler_initialized:
        return _handler
    _handler_initialized = True

    if not _is_configured():
        logger.info("Langfuse 키 미설정 — 관측 비활성화(no-op).")
        _handler = None
        return None

    _bridge_env()

    try:
        # 지연 import: langfuse 미설치 환경(관측 안 쓰는 배포)에서도 이 모듈이 깨지지 않게.
        from langfuse.langchain import CallbackHandler

        _handler = CallbackHandler()
        logger.info("Langfuse 관측 활성화(host=%s).", settings.LANGFUSE_BASE_URL)
    except Exception:
        # 관측은 부수효과일 뿐 — 초기화가 실패해도 절대 본 기능(챗봇)을 막지 않는다.
        logger.exception("Langfuse 초기화 실패 — 관측 없이 계속 진행.")
        _handler = None

    return _handler


def get_langfuse_client() -> Any:
    """수동 span 계측용 Langfuse 클라이언트를 반환하거나, 미설정이면 ``None``을 반환한다.

    `get_langfuse_handler()`가 만드는 `CallbackHandler`와 v4 SDK 내부의 같은 전역 싱글톤을
    공유한다(둘 다 결국 SDK의 `get_client()` 경로로 수렴) — 그래서 여기서 연 span 안에서
    LLM을 호출하면 그 generation이 자동으로 같은 trace의 하위로 들어간다.
    """
    global _client, _client_initialized
    if _client_initialized:
        return _client
    _client_initialized = True

    if not _is_configured():
        _client = None
        return None

    _bridge_env()

    try:
        from langfuse import get_client

        _client = get_client()
    except Exception:
        logger.exception("Langfuse 클라이언트 초기화 실패 — 검색 span 없이 계속 진행.")
        _client = None

    return _client


def get_current_trace_id() -> str | None:
    """활성 span 안에서 현재 trace id를 반환한다. 미설정/오류/활성 span 밖에서 호출 시
    ``None``(no-op) — 반드시 ``observe_span()`` ``with`` 블록 안에서 호출해야 한다."""
    client = get_langfuse_client()
    if client is None:
        return None
    try:
        return cast(str | None, client.get_current_trace_id())
    except Exception:
        logger.exception("Langfuse trace id 조회 실패 — None으로 계속 진행.")
        return None


def create_score(trace_id: str, name: str, value: float, comment: str | None = None) -> None:
    """Langfuse trace에 점수를 붙인다. 미설정/오류 시 조용히 무시(no-op) — 결정 4
    (`docs/tasks/T-LLM-2-langfuse-user-feedback.md`): 관측 실패가 호출부(피드백 API)의
    응답을 절대 막지 않는다.

    `ai_worker`는 장수 프로세스라 SDK 내부 배치 전송이 지연될 수 있는데, 이 함수는
    사용자가 버튼을 누를 때만 드물게 호출되는 fire-and-forget 경로라 `flush()` 비용이
    무시할 만하다 — 그래서 항상 명시적으로 flush해 Langfuse UI에 즉시 반영되게 한다."""
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.create_score(name=name, value=value, trace_id=trace_id, data_type="NUMERIC", comment=comment)
        client.flush()
    except Exception:
        logger.exception("Langfuse score('%s', trace_id=%s) 전송 실패 — 무시하고 계속 진행.", name, trace_id)


ObservationType = Literal[
    "span", "generation", "embedding", "agent", "tool", "chain", "retriever", "evaluator", "guardrail"
]


@contextmanager
def observe_span(name: str, as_type: ObservationType = "span", **input_kwargs: Any) -> Iterator[Any]:
    """이름이 붙은 span으로 블록을 감싼다. Langfuse 미설정 시 ``None``을 yield하는 no-op —
    호출부는 반환된 span이 ``None``일 수 있다는 것만 알고 `span.update(...)`를 조건부로 쓰면 된다.

    span 생성 실패(클라이언트 없음/SDK 오류)와 호출부(``with`` 블록) 내부의 예외를 반드시
    구분해야 한다 — `@contextmanager` 제너레이터는 정확히 한 번만 yield할 수 있어서, 호출부
    예외까지 여기서 잡아 두 번째 `yield`를 시도하면 ``RuntimeError: generator didn't stop
    after throw()``로 죽는다. 그래서 진입(`__enter__`)만 try/except로 감싸고, 이후 호출부
    예외는 그대로 통과시킨다."""
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        span_cm = client.start_as_current_observation(name=name, as_type=as_type, input=input_kwargs or None)
        span = span_cm.__enter__()
    except Exception:
        logger.exception("Langfuse span('%s') 생성 실패 — 관측 없이 계속 진행.", name)
        yield None
        return

    try:
        yield span
    except BaseException:
        span_cm.__exit__(*sys.exc_info())
        raise
    else:
        span_cm.__exit__(None, None, None)
