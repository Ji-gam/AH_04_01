"""
T-LLM-7: 도구 1개(질환 논문 검색)로 시작한 최소 파이프라인.
T-LLM-7-1: 도구 호출 전 질문을 정규화하는 Query Rewriting 단계 추가(1차 개선).
T-LLM-7-2: "질환 인식"과 "도구 호출 여부"를 하나의 LLM 판단으로 뭉뚱그리던 것을
분리 — 구조화 출력(disease + is_information_request) 2축 분류기로 바꾸고, 두 조건이
모두 참일 때만 코드가 결정론적으로 도구를 호출한다(LLM 재판단 없음). 이전엔
`create_agent`(LangGraph)가 "도구를 부를지"까지 자체 판단해서, 같은 질환이 언급돼도
문구(phrasing)에 따라 호출 여부가 오락가락했다("확률적 개선"에 그침) — 그 원인을
구조적으로 제거한다. 참고: agentic RAG의 Router 분리 패턴, forced tool calling.
"""

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr

from ai_worker.core.config import settings
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tools.paper_search import SUPPORTED_DISEASES, search_disease_paper


class QueryClassification(BaseModel):
    disease: str | None = Field(
        default=None,
        description=(
            "언급된 질환/증상의 표준 의학 명칭. 신체 장기를 빗댄 관용구(예: "
            "'심장이 쫄리다'=불안하다, '간이 크다/작다'=대범하다/겁많다, '간 떨어지다'=놀라다)는 "
            "실제 의학적 증상이 아니므로 null."
        ),
    )
    is_information_request: bool = Field(
        description=(
            "사용자가 그 질환/증상에 대한 정보, 확인, 논문/연구 결과를 원하는 질문인지. 단순 잡담/감정 표현이면 false."
        )
    )


# "5개 중 하나로 골라라"가 아니라 "표준 명칭이 뭐야"를 열어둔다 — 나중에 질환이
# 늘어나도(ADHD, 비만 등) 이 프롬프트 자체는 안 건드려도 되게 하기 위함. 목록은
# SUPPORTED_DISEASES에서 동적으로 가져와, 지금 지원되는 5개가 바뀌면 자동 반영된다.
_CLASSIFY_SYSTEM_PROMPT = (
    "사용자 질문을 분석해 disease(언급된 질환의 표준 명칭 또는 null)와 "
    "is_information_request(그 질환에 대한 정보/확인을 원하는 질문인지)를 판단하세요. "
    f"지원 목록: {', '.join(SUPPORTED_DISEASES)}. 목록 밖 질환/증상도 표준 명칭 그대로 disease에 "
    "담되, 신체 장기를 빗댄 관용구는 disease를 null로 하세요."
)

_ANSWER_SYSTEM_PROMPT = (
    "당신은 의학 논문 검색 비서입니다. 주어진 검색 자료의 구체적 수치를 인용해 답하고, "
    "이것이 단일 연구 결과임을 밝히세요."
)

_REFUSE_SYSTEM_PROMPT = "당신은 의학 논문 검색 비서입니다. 이 질문은 논문 검색 범위 밖입니다. 정중히 안내하세요."


def _build_llm() -> ChatOpenAI:
    if settings.OPENAI_API_KEY is None:
        raise GenerationUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        temperature=settings.OPENAI_TEMPERATURE,
    )


async def classify_query(question: str) -> QueryClassification:
    """질문에서 질환 언급 여부와 정보 요청 여부를 각각 독립적으로 판단한다."""
    llm = _build_llm().with_structured_output(QueryClassification)
    result = await llm.ainvoke(
        [
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
    )
    assert isinstance(result, QueryClassification)
    return result


def _is_valid_disease(disease: str | None) -> bool:
    """with_structured_output이 이따금 실제 None 대신 문자열 "null"을 반환하는
    경우를 방어한다."""
    return disease is not None and disease.strip().lower() not in {"null", "none", ""}


async def ask_paper_agent(question: str) -> str:
    classification = await classify_query(question)

    if _is_valid_disease(classification.disease) and classification.is_information_request:
        paper_result = await search_disease_paper.ainvoke({"disease": classification.disease})
        llm = _build_llm()
        answer = await llm.ainvoke(
            [
                {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": f"질문: {question}\n\n검색된 자료:\n{paper_result}"},
            ]
        )
        return str(answer.content)

    llm = _build_llm()
    answer = await llm.ainvoke(
        [
            {"role": "system", "content": _REFUSE_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
    )
    return str(answer.content)
