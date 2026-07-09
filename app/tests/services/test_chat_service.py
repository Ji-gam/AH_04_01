from collections.abc import AsyncIterator
from typing import cast

from app.models.chat import MessageRole
from app.repositories.chat_repository import ChatRepository
from app.services.chat_service import ChatService
from app.services.retriever_stub import Retriever
from app.services.safety_service import DISCLAIMER_TEXT, EMERGENCY_FALLBACK_MESSAGE
from app.services.user_health_context_service import UserHealthContextService


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
    async def search(self, query: str, context: dict) -> list[dict]:
        return [{"content": "fake-chunk-1", "metadata": {"source": "fake_source.csv"}}]


async def fake_llm_stream(message: str, context: dict, chunks: list[str]):
    for char in "fake-llm-reply":
        yield char


def _build_service(repository: FakeChatRepository) -> ChatService:
    # Fake들은 실제 클래스와 시그니처만 맞춘 덕타이핑 객체라 mypy 통과용으로 cast한다.
    return ChatService(
        repository=cast(ChatRepository, repository),
        health_context_service=cast(UserHealthContextService, FakeUserHealthContextService()),
        retriever=cast(Retriever, FakeRetriever()),
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
    assert "[출처: fake_source.csv]" in full_reply
    assert repository.saved_messages == [
        (10, MessageRole.USER, "두통약 뭐가 좋아요?"),
        (10, MessageRole.ASSISTANT, full_reply),
    ]
