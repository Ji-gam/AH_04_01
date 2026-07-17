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
    dur_doc = Document(page_content="DUR 청크 내용", metadata={"display_name": "노인주의의약품", "publisher": "식약처"})
    paper_doc = Document(
        page_content="논문 청크 내용", metadata={"pmid": "1", "title": "Paper A", "url": "https://x/1/"}
    )

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
        lambda db, msg, limit, conditions=None: [
            DocumentChunk(content=paper_doc.page_content, metadata=paper_doc.metadata, score=0.34)
        ],
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
            {"name": "Paper A", "url": "https://x/1/", "score": 0.34},
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
    monkeypatch.setattr(chat_agent_module, "search_papers", lambda db, msg, limit, conditions=None: [])

    fake_llm = FakeStreamingLLM(["답변"])
    monkeypatch.setattr(chat_agent_module, "_build_llm", lambda: fake_llm)

    chunks = [
        c async for c in chat_agent_module.stream_chat_answer("잡담", context={}, history=[], injected_context=[])
    ]

    assert chunks[0] == {"type": "sources", "sources": []}
    system_prompt = fake_llm.received_messages[0]["content"]
    assert "참고 문서:\n없음" in system_prompt


def test_search_all_passes_user_conditions_to_paper_search(monkeypatch):
    """질환이 안 드러난 질문도 사용자 본인 진단 질환으로 논문을 찾을 수 있어야 한다."""
    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_documents", lambda db, msg, limit: [])
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    received: dict = {}

    def _capture(db, msg, limit, conditions=None):
        received["conditions"] = conditions
        return []

    monkeypatch.setattr(chat_agent_module, "search_papers", _capture)

    chat_agent_module._search_all("운동 뭐가 좋아?", {"conditions": ["당뇨"]})

    assert received["conditions"] == ["당뇨"]


def test_search_all_tolerates_context_without_conditions(monkeypatch):
    """비로그인/프로필 미입력이면 context에 conditions 키가 없을 수 있다."""
    monkeypatch.setattr(chat_agent_module, "ensure_db", lambda: "dur-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_documents", lambda db, msg, limit: [])
    monkeypatch.setattr(chat_agent_module, "ensure_paper_db", lambda: "paper-db-sentinel")
    monkeypatch.setattr(chat_agent_module, "search_papers", lambda db, msg, limit, conditions=None: [])

    chunks, sources = chat_agent_module._search_all("좋은 아침이야", {})

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
