from collections.abc import AsyncIterator

from app.models.chat import MessageRole
from app.services.chat_service import ChatService
from app.services.safety_service import DISCLAIMER_TEXT, EMERGENCY_FALLBACK_MESSAGE


class FakeChatRepository:
    def __init__(self) -> None:
        self.saved_messages: list[tuple[int, MessageRole, str]] = []

    async def save_message(self, session, session_id: int, role: MessageRole, content: str) -> None:
        self.saved_messages.append((session_id, role, content))

    async def list_messages(self, session, session_id: int, limit: int = 20) -> list[str]:
        return []


class FakeUserHealthContextService:
    def get_context(self, profile_id: int) -> dict:
        return {"conditions": [], "medications": [], "goals": [], "profile_id": profile_id}


class FakeRetriever:
    def search(self, query: str, context: dict) -> list[str]:
        return ["fake-chunk-1"]


async def fake_llm_stream(message: str, context: dict, chunks: list[str]):
    for char in "fake-llm-reply":
        yield char


def _build_service(repository: FakeChatRepository) -> ChatService:
    return ChatService(
        repository=repository,
        health_context_service=FakeUserHealthContextService(),
        retriever=FakeRetriever(),
        llm_stream=fake_llm_stream,
    )


async def _collect(stream: AsyncIterator[dict]) -> list[dict]:
    return [chunk async for chunk in stream]


async def test_emergency_keyword_short_circuits_without_saving():
    repository = FakeChatRepository()
    service = _build_service(repository)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="가슴 통증 있어요"))

    assert chunks == [
        {"type": "emergency_fallback", "content": EMERGENCY_FALLBACK_MESSAGE, "disclaimer": DISCLAIMER_TEXT}
    ]
    assert repository.saved_messages == []


async def test_normal_message_streams_tokens_and_saves_conversation():
    repository = FakeChatRepository()
    service = _build_service(repository)

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=1, session_id=10, message="두통약 뭐가 좋아요?")
    )

    assert chunks[-1] == {"type": "done", "content": "", "disclaimer": DISCLAIMER_TEXT}
    token_chunks = [c for c in chunks if c["type"] == "token"]
    assert len(token_chunks) > 0

    full_reply = "".join(c["content"] for c in token_chunks)
    assert repository.saved_messages == [
        (10, MessageRole.USER, "두통약 뭐가 좋아요?"),
        (10, MessageRole.ASSISTANT, full_reply),
    ]
