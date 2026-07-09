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


class FakePregnantUserHealthContextService:
    def get_context(self, profile_id: int) -> dict:
        return {
            "profile_id": profile_id,
            "conditions": ["ADHD", "당뇨"],
            "medications": [
                {"condition": "ADHD", "name": "콘서타", "dose": "18mg", "times_per_day": 1}
            ],
            "goals": []
        }


def test_is_medical_related_fallback():
    service = ChatService()
    
    # 의료 관련 질의응답 -> True
    assert service._is_medical_related_fallback("콘서타 먹어도 되나요?", "임산부는 복용 시 주의해야 합니다.") is True
    assert service._is_medical_related_fallback("감기약 처방전 질문", "이 약물은 부작용이...") is True
    
    # 무관한 질의응답 -> False
    assert service._is_medical_related_fallback("오늘 날씨 어때?", "오늘 날씨는 매우 맑고 따뜻할 예정입니다.") is False
    assert service._is_medical_related_fallback("초코칩 쿠키 레시피 알려줘", "밀가루와 설탕을 섞어 구우면 됩니다.") is False


async def test_dur_warning_injected_for_pregnant_user():
    repository = FakeChatRepository()
    spy_llm = SpyLlmStream()
    
    # 임산부(콘서타) 건강 정보를 반환하는 Fake 서비스 주입
    service = ChatService(
        repository=cast(ChatRepository, repository),
        health_context_service=cast(UserHealthContextService, FakePregnantUserHealthContextService()),
        retriever=cast(Retriever, FakeRetriever()),
        llm_stream=spy_llm,
    )
    
    # profile_id가 2(임산부) 혹은 profile_name을 Mock 처리하기 위해 Fake DB 세션 등을 모킹하는 대신,
    # chat_service의 로직에 맞게 profile_id = 2 번(임산부) 데이터를 target_mock으로 매핑하도록 실행
    chunks = await _collect(
        service.stream_reply(session=None, profile_id=2, session_id=11, message="콘서타 먹어도 괜찮은지 물어봅니다.")
    )
    
    # done 청크에 면책조항이 들어가 있는지 확인
    assert chunks[-1]["type"] == "done"
    assert chunks[-1]["disclaimer"] == DISCLAIMER_TEXT
    
    # LLM 스트림에 넘겨진 content_chunks에 DUR 경고가 포함되었는지 확인
    assert len(spy_llm.received_chunks) > 0
    assert any("[임부금기 경고]" in c for c in spy_llm.received_chunks)
    assert any("콘서타" in c for c in spy_llm.received_chunks)


class SpyLlmStream:
    def __init__(self):
        self.received_chunks = []

    async def __call__(self, message: str, context: dict, chunks: list[str]):
        self.received_chunks = chunks
        for char in "fake-llm-reply":
            yield char
