"""
T-LLM-7: 도구 1개(질환 논문 검색)로 시작한 최소 파이프라인.
T-LLM-7-1: 도구 호출 전 질문을 정규화하는 Query Rewriting 단계 추가(1차 개선).
T-LLM-7-2: "질환 인식"과 "도구 호출 여부"를 하나의 LLM 판단으로 뭉뚱그리던 것을
분리 — 구조화 출력(disease + is_information_request) 2축 분류기로 바꾸고, 두 조건이
모두 참일 때만 코드가 결정론적으로 도구를 호출한다(LLM 재판단 없음).
T-LLM-7-3(개정): 라이브 PubMed 호출(`@tool search_disease_paper`)을 폐기하고, 오프라인
인제스천으로 미리 색인된 pubmed_papers 컬렉션의 벡터 검색(`search_papers`)으로 교체했다.
classify_query()가 이미 질환을 결정론적으로 뽑아주므로 "도구를 부를지"를 LLM이 재판단하는
agentic tool-calling(`@tool` 래핑)이 더 이상 필요 없어져, 직접 함수 호출로 바뀌었다.
멀티 논문 인용: 청크 여러 개를 프롬프트에 번호 매겨 넣고, 각 수치가 어느 PMID의 것인지
구분해 답하도록 지시한다. `sources`로 PMID 기준 중복 제거된 출처 목록(제목+URL)을
답변과 별도로 반환해, 프론트엔드가 출처 각주 UI를 붙일 수 있게 해둔다(칩 UI 자체는
별도 작업).
"""

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr

from ai_worker.core.config import settings
from ai_worker.schemas.retrieval_schema import DocumentChunk, PaperSourceRef
from ai_worker.services.paper_retrieve_service import search_papers
from ai_worker.tasks.generate_structured import GenerationUnavailableError
from ai_worker.tasks.ingest_papers import SUPPORTED_DISEASES


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
    "당신은 의학 논문 검색 비서입니다. 주어진 검색 자료(서로 다른 여러 연구일 수 있습니다)의 "
    "구체적 수치를 인용해 답하고, 각 수치가 어느 논문(PMID)의 것인지 구분해서 밝히세요."
)

_REFUSE_SYSTEM_PROMPT = "당신은 의학 논문 검색 비서입니다. 이 질문은 논문 검색 범위 밖입니다. 정중히 안내하세요."


def _not_found_message(disease: str) -> str:
    return f"'{disease}'에 대한 논문 자료를 찾지 못했습니다."


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


def _format_search_context(chunks: list[DocumentChunk]) -> str:
    """청크 여러 개를 번호 매겨 프롬프트에 넣는다 — LLM이 "[번호]"로 답변에서
    어느 논문을 인용했는지 구분해 밝힐 수 있게 한다."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        pmid = chunk.metadata.get("pmid")
        title = chunk.metadata.get("title")
        parts.append(f"[{i}] PMID {pmid}: {title}\n{chunk.content}")
    return "\n\n".join(parts)


def _build_sources(chunks: list[DocumentChunk]) -> list[PaperSourceRef]:
    """청크(같은 논문이 여러 청크로 쪼개졌을 수 있음)에서 PMID 기준 중복 제거된
    출처 목록을 만든다. 프론트엔드 출처 칩이 그대로 소비할 수 있는 형태."""
    seen_pmids: set[str] = set()
    sources: list[PaperSourceRef] = []
    for chunk in chunks:
        pmid = chunk.metadata.get("pmid")
        if not pmid or pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)
        title = chunk.metadata.get("title") or f"PMID {pmid}"
        sources.append(PaperSourceRef(name=title, url=chunk.metadata.get("url")))
    return sources


async def ask_paper_agent(question: str, db: Chroma) -> tuple[str, list[PaperSourceRef]]:
    classification = await classify_query(question)

    if _is_valid_disease(classification.disease) and classification.is_information_request:
        disease = classification.disease
        assert disease is not None  # _is_valid_disease가 이미 보장
        chunks = search_papers(db, question, disease, limit=settings.PAPER_RETRIEVAL_LIMIT)
        if not chunks:
            return _not_found_message(disease), []

        llm = _build_llm()
        context = _format_search_context(chunks)
        answer = await llm.ainvoke(
            [
                {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": f"질문: {question}\n\n검색된 자료:\n{context}"},
            ]
        )
        return str(answer.content), _build_sources(chunks)

    llm = _build_llm()
    answer = await llm.ainvoke(
        [
            {"role": "system", "content": _REFUSE_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
    )
    return str(answer.content), []
