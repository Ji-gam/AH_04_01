"""
T-LLM-7: 도구 1개(질환 논문 검색)를 쥔 최소 LangChain 에이전트.
T-LLM-7-1: 도구 호출 전 질문을 정규화하는 Query Rewriting 단계 추가.

"아무 질문에나 도구를 부르지 않는지"(판단력)를 검증하는 것이 이번 단계의 목적이라,
시스템 프롬프트는 의학 논문 질문과 무관한 질문을 명확히 구분하도록 지시한다.
"""

from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tools.paper_search import SUPPORTED_DISEASES, search_disease_paper

_SYSTEM_PROMPT = (
    "당신은 의학 논문 검색 비서입니다. 사용자가 특정 질환(암, 심장질환, 뇌혈관질환, "
    "당뇨, 간질환)에 관한 논문/연구 결과를 물으면 search_disease_paper 도구를 호출해 "
    "실제 초록에 담긴 구체적 수치를 인용해 답하고, 이것이 단일 연구 결과임을 밝히세요. "
    "의학 논문과 무관한 질문(날씨, 잡담 등)에는 도구를 호출하지 말고, 논문 검색 범위 "
    "밖의 질문이라고 정중히 답하세요."
)

# "5개 중 하나로 골라라"가 아니라 "표준 명칭이 뭐야"를 열어둔다 — 나중에 질환이
# 늘어나도(ADHD, 비만 등) 이 프롬프트 자체는 안 건드려도 되게 하기 위함. 목록은
# SUPPORTED_DISEASES에서 동적으로 가져와, 지금 지원되는 5개가 바뀌면 자동 반영된다.
_REWRITE_SYSTEM_PROMPT = (
    "사용자 질문에서 언급된 질환/증상의 표준 의학 명칭을 한 단어로 답하세요. "
    f"예를 들어 다음 목록에 해당하면 그 표기 그대로 사용하세요: {', '.join(SUPPORTED_DISEASES)}. "
    "목록에 없는 질환/증상이 언급되면(예: ADHD, 비만) 그 표준 명칭을 그대로 답하세요. "
    "질환/증상이 전혀 언급되지 않았으면 정확히 NONE이라고만 답하세요. "
    "다른 설명 없이 명칭 또는 NONE만 출력하세요."
)


def _build_llm() -> ChatOpenAI:
    if settings.OPENAI_API_KEY is None:
        raise GenerationUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return ChatOpenAI(model=settings.OPENAI_MODEL, api_key=SecretStr(settings.OPENAI_API_KEY))


async def rewrite_disease_query(question: str) -> str | None:
    """질문에 언급된 질환/증상의 표준 명칭을 추출한다. 언급이 없으면 None.

    지금 지원되는 5개 질환에 해당하지 않는 명칭(예: ADHD)이 나와도 그대로
    반환한다 — 화이트리스트 필터링은 여기서 하지 않고, 실제 검색 가능 여부는
    search_disease_paper 도구의 "찾지 못했습니다" 응답이 처리한다.
    """
    llm = _build_llm()
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
    )
    normalized = str(response.content).strip()
    return None if normalized == "NONE" else normalized


def _build_agent_executor() -> Any:
    llm = _build_llm()
    return create_agent(model=llm, tools=[search_disease_paper], system_prompt=_SYSTEM_PROMPT)


async def ask_paper_agent(question: str) -> str:
    normalized_disease = await rewrite_disease_query(question)
    effective_question = (
        f"{question}\n(질의 정규화 결과 — 관련 질환/증상 후보: {normalized_disease})"
        if normalized_disease is not None
        else question
    )

    executor = _build_agent_executor()
    result = await executor.ainvoke({"messages": [{"role": "user", "content": effective_question}]})
    return str(result["messages"][-1].content)
