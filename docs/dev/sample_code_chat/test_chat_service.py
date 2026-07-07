"""
가짜(Fake) 의존성으로 격리한 단위테스트 (test_nickname_service.py/test_recognition_service.py와 같은 패턴).
외부 의존성(Repository/Retriever/HealthContext)은 전부 Fake로 대체해 결정적으로 통과한다 (CODING_RULES.md §4).
"""

from app.services.chat_service import ChatService
from app.services.safety_service import EMERGENCY_FALLBACK_MESSAGE


class FakeChatRepository:
    def __init__(self) -> None:
        self.saved_calls: list[tuple[int, str, str]] = []

    def save_message(self, session_id: int, message: str, response: str) -> None:
        self.saved_calls.append((session_id, message, response))


class FakeUserHealthContextService:
    def get_context(self, profile_id: int) -> dict:
        return {"conditions": [], "medications": [], "goals": [], "profile_id": profile_id}


class FakeRetriever:
    def search(self, query: str, context: dict) -> list[str]:
        return ["fake-chunk-1"]


def _build_service(repository: FakeChatRepository) -> ChatService:
    return ChatService(
        repository=repository,
        health_context_service=FakeUserHealthContextService(),
        retriever=FakeRetriever(),
    )


def test_응급_키워드가_감지되면_LLM_호출없이_고정_안내만_반환한다():
    repository = FakeChatRepository()
    service = _build_service(repository)

    reply = "".join(service.stream_reply(profile_id=1, session_id=10, message="가슴 통증 있어요"))

    assert reply == EMERGENCY_FALLBACK_MESSAGE
    assert repository.saved_calls == []


def test_응급이_아니면_스트리밍_응답을_모두_합쳐_대화기록에_저장한다():
    repository = FakeChatRepository()
    service = _build_service(repository)

    reply = "".join(service.stream_reply(profile_id=1, session_id=10, message="두통약 뭐가 좋아요?"))

    assert len(reply) > 0
    assert len(repository.saved_calls) == 1
    saved_session_id, saved_message, saved_response = repository.saved_calls[0]
    assert saved_session_id == 10
    assert saved_message == "두통약 뭐가 좋아요?"
    assert saved_response == reply
