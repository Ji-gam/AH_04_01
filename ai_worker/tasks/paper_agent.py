"""
T-LLM-7: 도구 1개(질환 논문 검색)를 쥔 최소 LangChain 에이전트.

"아무 질문에나 도구를 부르지 않는지"(판단력)를 검증하는 것이 이번 단계의 목적이라,
시스템 프롬프트는 의학 논문 질문과 무관한 질문을 명확히 구분하도록 지시한다.
"""

from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tools.paper_search import search_disease_paper

_SYSTEM_PROMPT = (
    "당신은 의학 논문 검색 비서입니다. 사용자가 특정 질환(암, 심장질환, 뇌혈관질환, "
    "당뇨, 간질환)에 관한 논문/연구 결과를 물으면 search_disease_paper 도구를 호출해 "
    "실제 초록에 담긴 구체적 수치를 인용해 답하고, 이것이 단일 연구 결과임을 밝히세요. "
    "의학 논문과 무관한 질문(날씨, 잡담 등)에는 도구를 호출하지 말고, 논문 검색 범위 "
    "밖의 질문이라고 정중히 답하세요."
)


def _build_agent_executor() -> Any:
    if settings.OPENAI_API_KEY is None:
        raise GenerationUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")

    llm = ChatOpenAI(model=settings.OPENAI_MODEL, api_key=SecretStr(settings.OPENAI_API_KEY))
    return create_agent(model=llm, tools=[search_disease_paper], system_prompt=_SYSTEM_PROMPT)


async def ask_paper_agent(question: str) -> str:
    executor = _build_agent_executor()
    result = await executor.ainvoke({"messages": [{"role": "user", "content": question}]})
    return str(result["messages"][-1].content)
