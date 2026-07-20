"""
T-LLM-7-3-2: 통합 RAG 스트리밍 채팅 에이전트 회귀 테스트.

실제 Chroma/OpenAI는 모킹한다 — 여기서는 "DUR+논문 청크를 합쳐서 하나의 프롬프트로
스트리밍하는지", "청크가 없으면 참고 문서 없이도 스트리밍이 되는지"만 검증한다.
실제 검색 품질/임계값 튜닝은 test_retrieve_service.py/test_paper_retrieve_service.py가
따로 검증한다.
"""

from langchain_core.documents import Document

from ai_worker.schemas.retrieval_schema import DocumentChunk
from ai_worker.tasks import chat_agent as chat_agent_module


def test_build_dur_sources_dedupes_and_sorts():
    chunks = [
        DocumentChunk(content="a", metadata={"display_name": "노인주의의약품", "publisher": "식약처"}),
        DocumentChunk(content="b", metadata={"display_name": "임부금기의약품", "publisher": "식약처"}),
        DocumentChunk(content="c", metadata={"display_name": "노인주의의약품", "publisher": "식약처"}),
        DocumentChunk(content="d", metadata={}),
    ]

    sources = chat_agent_module._build_dur_sources(chunks)

    assert [s.name for s in sources] == ["노인주의의약품/식약처", "임부금기의약품/식약처"]
    assert all(s.url is None for s in sources)


def test_build_paper_sources_dedupes_by_pmid():
    chunks = [
        DocumentChunk(content="a", metadata={"pmid": "1", "title": "Paper A"}),
        DocumentChunk(content="b", metadata={"pmid": "1", "title": "Paper A"}),
        DocumentChunk(content="c", metadata={"pmid": "2", "title": "Paper B"}),
    ]

    sources = chat_agent_module._build_paper_sources(chunks)

    assert [(s.name, s.url) for s in sources] == [
        ("Paper A", "https://pubmed.ncbi.nlm.nih.gov/1/"),
        ("Paper B", "https://pubmed.ncbi.nlm.nih.gov/2/"),
    ]


class _FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeStreamingLLM:
    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.received_messages: list[dict] | None = None

    async def astream(self, messages: list[dict]):
        self.received_messages = messages
        for content in self._contents:
            yield _FakeChunk(content)


async def test_stream_chat_answer_merges_dur_and_paper_chunks_and_streams_tokens(monkeypatch):
    dur_doc = Document(page_content="DUR 청크 내용", metadata={"display_name": "노인주의의약품", "publisher": "식약처"})
    paper_doc = Document(page_content="논문 청크 내용", metadata={"pmid": "1", "title": "Paper A"})

    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(
        chat_agent_module,
        "search_documents",
        lambda db, msg, limit: [DocumentChunk(content=dur_doc.page_content, metadata=dur_doc.metadata, score=0.12)],
    )
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(
        chat_agent_module,
        "search_papers",
        lambda db, msg, limit: [DocumentChunk(content=paper_doc.page_content, metadata=paper_doc.metadata, score=0.34)],
    )

    fake_llm = FakeStreamingLLM(["안", "녕"])
    monkeypatch.setattr(chat_agent_module, "_build_llm", lambda: fake_llm)

    chunks = [
        c
        async for c in chat_agent_module.stream_chat_answer(
            "질문", context={"name": "사용자"}, history=[], injected_context=["[DUR 안전 경고 정보] 테스트"]
        )
    ]

    assert chunks[0] == {
        "type": "sources",
        "sources": [
            {"name": "노인주의의약품/식약처", "url": None, "score": 0.12},
            {"name": "Paper A", "url": "https://pubmed.ncbi.nlm.nih.gov/1/", "score": 0.34},
        ],
    }
    assert chunks[1:] == [{"type": "token", "content": "안"}, {"type": "token", "content": "녕"}]

    # 프롬프트에 injected_context(개인 DUR 경고) + DUR/논문 청크가 다 들어갔는지 확인
    system_prompt = fake_llm.received_messages[0]["content"]
    assert "[DUR 안전 경고 정보] 테스트" in system_prompt
    assert "DUR 청크 내용" in system_prompt
    assert "논문 청크 내용" in system_prompt


async def test_stream_chat_answer_uses_no_reference_text_when_no_chunks_found(monkeypatch):
    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_documents", lambda db, msg, limit: [])
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_papers", lambda db, msg, limit: [])

    fake_llm = FakeStreamingLLM(["답변"])
    monkeypatch.setattr(chat_agent_module, "_build_llm", lambda: fake_llm)

    chunks = [
        c async for c in chat_agent_module.stream_chat_answer("잡담", context={}, history=[], injected_context=[])
    ]

    assert chunks[0] == {"type": "sources", "sources": []}
    system_prompt = fake_llm.received_messages[0]["content"]
    assert "참고 문서:\n없음" in system_prompt


async def test_stream_chat_answer_prompt_tells_llm_not_to_confuse_asker_with_question_subject(monkeypatch):
    """실측 버그(2026-07-20): "인데놀 노인이 먹어도 돼?"에 질문자 본인의 is_geriatric로
    답하던 사고 — 시스템 프롬프트가 "질문자 본인 정보"임을 명시하고, 질문이 제3자/일반
    대상에 대한 것이면 그 정보를 쓰지 말라는 지시가 빠지지 않았는지 회귀 가드."""
    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_documents", lambda db, msg, limit: [])
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_papers", lambda db, msg, limit: [])

    fake_llm = FakeStreamingLLM(["답변"])
    monkeypatch.setattr(chat_agent_module, "_build_llm", lambda: fake_llm)

    _ = [
        c
        async for c in chat_agent_module.stream_chat_answer(
            "질문", context={"is_geriatric": False}, history=[], injected_context=[]
        )
    ]

    system_prompt = fake_llm.received_messages[0]["content"]
    assert "질문자 본인 정보" in system_prompt
    assert "질문자가 아닌 다른" in system_prompt
    assert "혼동하지 마세요" in system_prompt


def test_search_all_skips_paper_search_when_query_has_no_disease(monkeypatch):
    """질환이 안 드러난 질문은 진단 이력과 무관하게 논문 검색을 생략한다 — 개인화는
    시스템 프롬프트의 "질문자 본인 정보"가 담당한다(disease_query_resolver 참고)."""
    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_documents", lambda db, msg, limit: [])
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_papers", lambda db, msg, limit: [])

    chunks, sources = chat_agent_module._search_all("좋은 아침이야")

    assert chunks == []
    assert sources == []


def test_build_llm_raises_when_no_api_key(monkeypatch):
    from ai_worker.tasks.generate_structured import GenerationUnavailableError

    monkeypatch.setattr(chat_agent_module.settings, "OPENAI_API_KEY", None)

    try:
        chat_agent_module._build_llm()
        raise AssertionError("GenerationUnavailableError가 발생해야 한다")
    except GenerationUnavailableError:
        pass
