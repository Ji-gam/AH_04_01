"""
T-LLM-7-3-2: 통합 RAG 스트리밍 채팅 에이전트.

기존에 분리돼 있던 두 파이프라인 — DUR 전용 `/retrieve`(청크만 반환, 답변 생성은
app/가 자체 LLM으로 처리)와 논문 전용 `/agent/paper-search`(질환 분류→검색→자체
LLM 답변까지 완결)를 하나로 통합한다. 질문 하나에 DUR도 관련되고 논문도 관련될 수
있는 실제 상황을 반영해, 매 질문마다 DUR(dur_rules)+논문(pubmed_papers) 두 컬렉션을
모두 검색해 청크를 합치고, 단 한 번의 LLM 호출로 스트리밍 답변을 만든다.

"RAG가 필요한 질문인지"는 별도 분류 LLM 호출 없이, 두 컬렉션에서 임계값을 통과하는
청크가 하나도 없으면 자연히 "RAG 없이 그냥 답변"이 된다 — DUR이 원래 이렇게
동작했고, 논문도 이제 같은 원칙을 따른다(질환 사전 분류 제거, paper_retrieve_service
참고). 관용구 등 무관한 질문이 논문 컬렉션에 잘못 걸릴 위험은 임베딩 거리(임계값)
로만 걸러진다는 전제 — 실제 데이터로 점수 분포를 보며 조정이 필요할 수 있다.

개인화 컨텍스트(진단병력/복약정보)와 개인 DUR 경고(사용자의 등록 약물 기반 SQL
조회라 ai_worker가 직접 계산 못 함)는 app/가 만들어서 `ChatCompletionRequest`로
넘긴다 — 이 모듈은 그 값을 프롬프트에 반영할 뿐 직접 조회하지 않는다.
"""

from collections.abc import AsyncIterator

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from ai_worker.core.config import settings
from ai_worker.schemas.retrieval_schema import DocumentChunk, SourceRef
from ai_worker.services.paper_retrieve_service import ensure_paper_db, search_papers
from ai_worker.services.retrieve_service import ensure_db, search_documents
from ai_worker.tasks.generate_structured import GenerationUnavailableError

_SYSTEM_PROMPT_TEMPLATE = (
    "당신은 ReMedi의 건강 상담 챗봇입니다. 아래 사용자 건강 컨텍스트(진단병력·가족력·"
    "복약정보)와 참고 문서를 활용해 개인화되고 안전한 답변을 간결하게 제공하세요.\n"
    "이 시스템은 답변 하단 UI 영역에 면책 조항을 별도로 노출하므로, 답변 본문에 "
    "'의사와 상담하세요' 같은 자가 경고/면책 문구는 적지 마세요.\n"
    "참고 문서가 있다면 그 안의 구체적 내용을 우선 활용하고, 없다면 일반적인 지식으로 답하세요.\n"
    "참고 문서:\n{reference_text}\n"
    "사용자 건강 컨텍스트: {context}"
)


def _build_llm() -> ChatOpenAI:
    if settings.OPENAI_API_KEY is None:
        raise GenerationUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")
    # temperature를 강제하지 않는다 — 분류/논문답변(결정성 우선)과 달리, 일반 대화
    # 답변은 자연스러운 표현 변주가 있는 편이 낫다(기존 app/의 llm_stub.py도 고정하지 않았음).
    return ChatOpenAI(model=settings.OPENAI_MODEL, api_key=SecretStr(settings.OPENAI_API_KEY))


def _build_dur_sources(chunks: list[DocumentChunk]) -> list[SourceRef]:
    names: set[str] = {name for c in chunks if isinstance((name := c.metadata.get("source")), str)}
    return [SourceRef(name=name, url=None) for name in sorted(names)]


# 논문 컬렉션은 DUR과 달리 성분명 같은 필터 대상이 없어 임계값(PAPER_SIMILARITY_THRESHOLD)
# 하나로만 걸러야 하는데, 실측 결과 인사말류 표현의 점수가 요동쳐 임계값 바로 아래로
# 통과하는 경우가 나왔다(예: "좋은 아침이야" 1.4995 < 1.5, 무관한 임신성 당뇨 논문과
# 매칭됨, 2026-07-16). 임계값만 낮추면 진짜 관련 질문 범위(1.06~1.44)와 겹쳐 함께
# 걸러질 위험이 있으므로, 짧고 물음표 없는 인사말/감탄사는 검색 자체를 생략하는 명시적
# 가드를 추가한다(DUR의 성분명 미식별 시 검색 생략과 같은 원칙).
_GREETING_KEYWORDS = (
    "안녕",
    "좋은아침",
    "좋은하루",
    "좋은저녁",
    "굿모닝",
    "굿나잇",
    "하이",
    "헬로",
    "고마워",
    "감사",
    "수고",
    "화이팅",
    "잘가",
    "반가워",
    "잘자",
)


def _is_trivial_greeting(message: str) -> bool:
    """물음표 없이 10자 이내이면서 인사말/감탄사 키워드를 포함하면 논문 검색을 생략할
    후보로 본다. 길이만으로 자르면 "당뇨병 혈당관리"처럼 짧은 진짜 질문까지 걸러지므로
    반드시 인사말 키워드 포함 여부와 함께 판단한다."""
    normalized = message.strip()
    if "?" in normalized or "？" in normalized:
        return False
    compact = normalized.replace(" ", "")
    if len(compact) > 10:
        return False
    return any(keyword in compact for keyword in _GREETING_KEYWORDS)


def _build_paper_sources(chunks: list[DocumentChunk]) -> list[SourceRef]:
    seen_pmids: set[str] = set()
    sources: list[SourceRef] = []
    for chunk in chunks:
        pmid = chunk.metadata.get("pmid")
        if not pmid or pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)
        title = chunk.metadata.get("title") or f"PMID {pmid}"
        sources.append(SourceRef(name=title, url=chunk.metadata.get("url")))
    return sources


def _search_all(message: str) -> tuple[list[DocumentChunk], list[SourceRef]]:
    """DUR + 논문 두 컬렉션을 모두 검색해 청크와 통합 출처 목록을 만든다."""
    dur_db = ensure_db()
    dur_chunks = search_documents(dur_db, message, settings.RAG_RETRIEVAL_LIMIT)

    if _is_trivial_greeting(message):
        return dur_chunks, _build_dur_sources(dur_chunks)

    paper_db = ensure_paper_db()
    paper_chunks = search_papers(paper_db, message, settings.PAPER_RETRIEVAL_LIMIT)

    sources = _build_dur_sources(dur_chunks) + _build_paper_sources(paper_chunks)
    return dur_chunks + paper_chunks, sources


async def stream_chat_answer(
    message: str, context: dict, history: list[dict], injected_context: list[str]
) -> AsyncIterator[dict]:
    """DUR+논문 통합 검색 -> 프롬프트 조립 -> LLM 스트리밍.
    `{"type": "sources", "sources": [...]}` 1건 다음 `{"type": "token", "content": ...}`
    여러 건을 순서대로 내보낸다."""
    rag_chunks, sources = _search_all(message)
    yield {"type": "sources", "sources": [s.model_dump() for s in sources]}

    reference_text = "\n".join(injected_context + [c.content for c in rag_chunks]) or "없음"
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(reference_text=reference_text, context=context)

    llm = _build_llm()
    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]

    async for event in llm.astream(messages):
        if event.content:
            yield {"type": "token", "content": event.content}
