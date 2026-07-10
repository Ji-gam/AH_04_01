"""
T-LLM-2-async-gateway: 범용 구조화 생성.

도메인(질환 콘텐츠, 약품 정보 등)에 종속적인 프롬프트/응답 스키마는 호출하는 쪽
(`app/`의 `AIWorkerGateway.call_structured`)이 정의한다. 이 모듈은 "system_prompt +
user_input + json_schema를 받아 그 스키마를 만족하는 JSON을 생성한다"는 범용 능력만
제공하고, 도메인 지식을 갖지 않는다.
"""

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings

logger = logging.getLogger("ai_worker.generate_structured")


class GenerationUnavailableError(Exception):
    """`OPENAI_API_KEY`가 설정되지 않아 생성을 수행할 수 없을 때 발생."""


def _build_chain(json_schema: dict[str, Any], api_key: str):
    llm = ChatOpenAI(model=settings.OPENAI_MODEL, api_key=SecretStr(api_key))
    return llm.with_structured_output(json_schema)


async def generate_structured(system_prompt: str, user_input: str, json_schema: dict[str, Any]) -> dict:
    if settings.OPENAI_API_KEY is None:
        raise GenerationUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")

    try:
        chain = _build_chain(json_schema, settings.OPENAI_API_KEY)
        return await chain.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
        )
    except GenerationUnavailableError:
        raise
    except Exception:
        logger.exception("구조화 생성 실패")
        raise
