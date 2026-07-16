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
        DocumentChunk(content="a", metadata={"source": "식약처 DUR 노인주의 정보"}),
        DocumentChunk(content="b", metadata={"source": "식약처 DUR 임부금기 정보"}),
        DocumentChunk(content="c", metadata={"source": "식약처 DUR 노인주의 정보"}),
        DocumentChunk(content="d", metadata={}),
    ]

    sources = chat_agent_module._build_dur_sources(chunks)

    assert [s.name for s in sources] == ["식약처 DUR 노인주의 정보", "식약처 DUR 임부금기 정보"]
    assert all(s.url is None for s in sources)


def test_build_paper_sources_dedupes_by_pmid():
    chunks = [
        DocumentChunk(content="a", metadata={"pmid": "1", "title": "Paper A", "url": "https://x/1/"}),
        DocumentChunk(content="b", metadata={"pmid": "1", "title": "Paper A", "url": "https://x/1/"}),
        DocumentChunk(content="c", metadata={"pmid": "2", "title": "Paper B", "url": "https://x/2/"}),
    ]

    sources = chat_agent_module._build_paper_sources(chunks)

    assert [(s.name, s.url) for s in sources] == [("Paper A", "https://x/1/"), ("Paper B", "https://x/2/")]


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
    dur_doc = Document(page_content="DUR 청크 내용", metadata={"source": "식약처 DUR 노인주의 정보"})
    paper_doc = Document(
        page_content="논문 청크 내용", metadata={"pmid": "1", "title": "Paper A", "url": "https://x/1/"}
    )

    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(
        chat_agent_module,
        "search_documents",
        lambda db, msg, limit: [DocumentChunk(content=dur_doc.page_content, metadata=dur_doc.metadata)],
    )
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(
        chat_agent_module,
        "search_papers",
        lambda db, msg, limit: [DocumentChunk(content=paper_doc.page_content, metadata=paper_doc.metadata)],
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
            {"name": "식약처 DUR 노인주의 정보", "url": None},
            {"name": "Paper A", "url": "https://x/1/"},
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


def test_is_trivial_greeting_skips_short_greetings_without_question_mark():
    assert chat_agent_module._is_trivial_greeting("좋은 아침이야") is True
    assert chat_agent_module._is_trivial_greeting("안녕") is True
    assert chat_agent_module._is_trivial_greeting("고마워") is True


def test_is_trivial_greeting_keeps_real_questions():
    # 인사말 키워드가 없는 짧은 질문은 걸러지면 안 된다.
    assert chat_agent_module._is_trivial_greeting("당뇨병 혈당관리") is False
    # 물음표가 있으면 인사말 키워드가 있어도 걸러지지 않는다.
    assert chat_agent_module._is_trivial_greeting("안녕하세요, 타이레놀 먹어도 되나요?") is False
    # 인사말 키워드를 포함해도 10자를 넘으면(잡담 이상의 실제 내용일 가능성) 걸러지지 않는다.
    assert chat_agent_module._is_trivial_greeting("좋은 아침인데 두통이 심해요") is False


def test_search_all_skips_paper_search_for_trivial_greeting(monkeypatch):
    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_documents", lambda db, msg, limit: [])

    def _fail_if_called(db, msg, limit):
        raise AssertionError("인사말에는 논문 검색이 호출되면 안 된다")

    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_papers", _fail_if_called)

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
