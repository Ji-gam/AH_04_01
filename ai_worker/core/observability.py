"""T-LLM-2-langfuse-observability: LLM 호출 관측(Langfuse) 진입점.

`ai_worker`의 LLM 호출부(`tasks/chat_agent.py`, `tasks/generate_structured.py`)가 공유하는
LangChain 콜백 핸들러 팩토리. 두 task 모듈이 각자 `_build_llm()`/`_build_chain()`을 갖고 있어
공유 지점이 없으므로, 관측 설정을 이 한 곳으로 모은다(호출부엔 `get_langfuse_handler()` 한 줄만).

관측은 **선택**이다: Langfuse 키가 없으면(로컬 개발, CI) `None`을 돌려주고 호출부는 콜백을
그냥 생략한다 — 챗봇/구조화 생성은 종전과 완전히 동일하게 동작한다(무회귀).
"""

from __future__ import annotations

import os
from typing import Any

from ai_worker.core.config import settings
from ai_worker.core.logger import setup_logger

logger = setup_logger("ai_worker.observability")

# 핸들러 생성은 한 번만 시도하고 결과(핸들러 or None)를 캐싱한다.
# _handler는 성공 시 Langfuse CallbackHandler, 실패/미설정 시 None.
_handler: Any = None
_initialized = False


def _is_configured() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def get_langfuse_handler() -> Any:
    """Langfuse LangChain 콜백 핸들러를 반환하거나, 미설정이면 ``None``을 반환한다.

    호출부는 반환값이 있을 때만 ``config={"callbacks": [handler]}``로 넘기면 된다.
    최초 1회만 초기화하고 이후엔 캐싱된 값을 돌려준다.
    """
    global _handler, _initialized
    if _initialized:
        return _handler
    _initialized = True

    if not _is_configured():
        logger.info("Langfuse 키 미설정 — 관측 비활성화(no-op).")
        _handler = None
        return None

    # pydantic-settings는 .env를 `settings`로만 읽고 os.environ에는 넣지 않는다.
    # Langfuse SDK(v3)는 전역 클라이언트를 표준 환경변수에서 초기화하므로, 여기서
    # settings 값을 환경변수로 브릿지해 "설정 단일 소스 = config.py"를 유지한다.
    # 호스트 변수명이 SDK 패치 버전에 따라 LANGFUSE_HOST / LANGFUSE_BASE_URL로 갈려
    # 있어 둘 다 세팅한다(같은 값, 무해).
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_BASE_URL"] = settings.LANGFUSE_BASE_URL

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
