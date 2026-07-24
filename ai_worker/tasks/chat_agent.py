"""
T-LLM-7-3-2: 통합 RAG 스트리밍 채팅 에이전트.

기존에 분리돼 있던 두 파이프라인 — DUR 전용 `/retrieve`(청크만 반환, 답변 생성은
app/가 자체 LLM으로 처리)와 논문 전용 `/agent/paper-search`(질환 분류→검색→자체
LLM 답변까지 완결)를 하나로 통합한다. 질문 하나에 DUR도 관련되고 논문도 관련될 수
있는 실제 상황을 반영해, 매 질문마다 DUR(structured)+논문(unstructured) 두 컬렉션을
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
    "당신은 ReMedi의 건강 상담 챗봇입니다. 아래 참고 문서와 '질문자 본인 정보'를 활용해 "
    "안전한 답변을 간결하게 제공하세요.\n"
    "'질문자 본인 정보'는 지금 대화 중인 사용자 자신의 진단병력·가족력·복약정보입니다. "
    "질문이 질문자 자신에 대한 것(예: '이 약 먹어도 될까요?', '내 약이랑 같이 먹어도 돼?')일 "
    "때만 이 정보로 답을 개인화하세요. 질문이 노인·임산부·어린이 등 질문자가 아닌 다른 "
    "대상 전반에 대한 일반적인 질문(예: '이 약 노인이 먹어도 되나요?')이면, 질문자 본인 "
    "정보와는 무관하게 질문이 실제로 묻는 대상 기준으로만 답하세요 — 질문자 본인의 나이나 "
    "임신 여부를 질문 속 대상과 혼동하지 마세요.\n"
    "이 시스템은 답변 하단 UI 영역에 면책 조항을 별도로 노출하므로, 답변 본문에 "
    "'의사와 상담하세요' 같은 자가 경고/면책 문구는 적지 마세요.\n"
    "참고 문서가 있다면 그 안의 구체적 내용을 우선 활용하고, 없다면 일반적인 지식으로 답하세요.\n"
    "참고 문서:\n{reference_text}\n"
    "질문자 본인 정보: {context}"
)


def _build_llm() -> ChatOpenAI:
    if settings.OPENAI_API_KEY is None:
        raise GenerationUnavailableError("OPENAI_API_KEY가 설정되지 않았습니다.")
    # temperature를 강제하지 않는다 — 분류/논문답변(결정성 우선)과 달리, 일반 대화
    # 답변은 자연스러운 표현 변주가 있는 편이 낫다(기존 app/의 llm_stub.py도 고정하지 않았음).
    return ChatOpenAI(model=settings.OPENAI_MODEL, api_key=SecretStr(settings.OPENAI_API_KEY))


def _build_dur_sources(chunks: list[DocumentChunk]) -> list[SourceRef]:
    # T-RAG-SOURCE-MIGRATION: source_id(내부 삭제 필터 키)와 별개로 display_name/publisher를
    # "자료명/제공처" 형태로 조합해 노출한다(예: "임부금기의약품/식약처"). 같은 출처로 여러
    # 청크가 매칭될 수 있어, 그중 가장 유사한(거리가 가장 짧은) 점수를 남긴다.
    best_score_by_name: dict[str, float | None] = {}
    for c in chunks:
        display_name = c.metadata.get("display_name")
        if not isinstance(display_name, str):
            continue
        publisher = c.metadata.get("publisher")
        name = f"{display_name}/{publisher}" if isinstance(publisher, str) and publisher else display_name
        current = best_score_by_name.get(name)
        if current is None or (c.score is not None and c.score < current):
            best_score_by_name[name] = c.score
    return [SourceRef(name=name, url=None, score=best_score_by_name[name]) for name in sorted(best_score_by_name)]


# 인사말 전용 가드(`_is_trivial_greeting`)가 여기 있었다. 인사말이 임계값 바로 아래로
# 새어 들어오던 실측("좋은 아침이야" 1.4995 < 1.5, 2026-07-16)에 대응한 땜질이었는데,
# 그 근본 원인이던 고아 청크(제목 없이 잘려나간 초록 조각, 컬렉션의 70%)를 없애자
# 불필요해졌다 — 재적재 후 실측하니 "좋은 아침이야" 0.4706, "안녕" 0.4694,
# "고마워" 0.4830으로 전부 임계값 0.40을 여유 있게 못 넘는다. 게다가 이제 질환 사전이
# 대상 질환을 못 정하면 논문 검색 자체를 생략하므로(paper_retrieve_service) 인사말은
# 두 겹으로 걸러진다. 근본 원인이 해결돼 제거함(2026-07-17).


def _build_paper_sources(chunks: list[DocumentChunk]) -> list[SourceRef]:
    # 원본 JSON(ingest_papers._parse_articles)이 pmid/title/abstract만 수집하고 url은
    # 애초에 저장하지 않는다 — PMID만 있으면 PubMed 표준 URL을 그대로 조립할 수 있어
    # 별도 필드로 챙길 이유가 없다.
    seen_pmids: set[str] = set()
    sources: list[SourceRef] = []
    for chunk in chunks:
        pmid = chunk.metadata.get("pmid")
        if not pmid or pmid in seen_pmids:
            continue
        seen_pmids.add(pmid)
        title = chunk.metadata.get("title") or f"PMID {pmid}"
        sources.append(SourceRef(name=title, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", score=chunk.score))
    return sources


def _search_all(message: str) -> tuple[list[DocumentChunk], list[SourceRef]]:
    """DUR + 논문 두 컬렉션을 모두 검색해 청크와 통합 출처 목록을 만든다.
    사용자 본인 진단 질환은 논문 검색 필터로는 쓰지 않는다 — 답변 개인화는 시스템
    프롬프트의 "질문자 본인 정보"로 이미 보장되므로, 질의 자체에 질환이 안 드러나면
    논문 검색을 생략한다(`disease_query_resolver.resolve_diseases` docstring 참고)."""
    dur_db = ensure_db()
    dur_chunks = search_documents(dur_db, message, settings.RAG_RETRIEVAL_LIMIT)

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
