from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import cast

from app.models.chat import MessageRole
from app.repositories.chat_repository import ChatRepository
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.ai_worker_gateway import AIWorkerGateway
from app.services.chat_service import ChatService
from app.services.safety_service import DISCLAIMER_TEXT, EMERGENCY_FALLBACK_MESSAGE


class FakeChatRepository:
    def __init__(self) -> None:
        self.saved_messages: list[tuple[int, MessageRole, str]] = []

    async def save_message(self, session, session_id: int, role: MessageRole, content: str) -> None:
        self.saved_messages.append((session_id, role, content))

    async def list_messages(self, session, session_id: int, limit: int = 20) -> list[str]:
        return []


@dataclass
class FakeProfile:
    id: int
    name: str = "사용자"
    age: int | None = None
    diagnosis_history: list[dict] | None = None
    family_history: list[dict] | None = None


class FakeProfileRepository:
    def __init__(self, profiles: dict[int, FakeProfile] | None = None) -> None:
        self._profiles = profiles or {}

    async def get_profile(self, session, profile_id: int) -> FakeProfile | None:
        return self._profiles.get(profile_id)


@dataclass
class FakeMedication:
    medication_name: str


@dataclass
class FakeMedicationSchedule:
    medication: FakeMedication
    times: list[str] = field(default_factory=lambda: ["08:00"])


class FakeMedicationRepository:
    def __init__(self, schedules: dict[int, list[FakeMedicationSchedule]] | None = None) -> None:
        self._schedules = schedules or {}

    async def list_schedules_by_profile(self, session, profile_id: int) -> list[FakeMedicationSchedule]:
        return self._schedules.get(profile_id, [])


class FakeRetriever:
    async def search(self, query: str) -> list[dict]:
        return [{"content": "fake-chunk-1", "metadata": {"source": "fake_source.csv"}}]


async def fake_llm_stream(message: str, context: dict, chunks: list[str]):
    for char in "fake-llm-reply":
        yield char


def _build_service(
    repository: FakeChatRepository,
    profile_repository: FakeProfileRepository | None = None,
    medication_repository: FakeMedicationRepository | None = None,
    llm_stream=fake_llm_stream,
    dur_drug_repository=None,
) -> ChatService:
    # Fake들은 실제 클래스와 시그니처만 맞춘 덕타이핑 객체라 mypy 통과용으로 cast한다.
    kwargs = dict(
        repository=cast(ChatRepository, repository),
        retriever=cast(AIWorkerGateway, FakeRetriever()),
        llm_stream=llm_stream,
        profile_repository=cast(ProfileRepository, profile_repository or FakeProfileRepository()),
        medication_repository=cast(MedicationRepository, medication_repository or FakeMedicationRepository()),
    )
    if dur_drug_repository is not None:
        kwargs["dur_drug_repository"] = cast(DurDrugRepository, dur_drug_repository)
    return ChatService(**kwargs)


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
    profiles = FakeProfileRepository({1: FakeProfile(id=1, name="사용자")})
    service = _build_service(repository, profile_repository=profiles)

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


def test_is_medical_related_fallback():
    service = ChatService()

    # 의료 관련 질의응답 -> True
    assert service._is_medical_related_fallback("콘서타 먹어도 되나요?", "임산부는 복용 시 주의해야 합니다.") is True
    assert service._is_medical_related_fallback("감기약 처방전 질문", "이 약물은 부작용이...") is True

    # 무관한 질의응답 -> False
    assert service._is_medical_related_fallback("오늘 날씨 어때?", "오늘 날씨는 매우 맑고 따뜻할 예정입니다.") is False
    assert (
        service._is_medical_related_fallback("초코칩 쿠키 레시피 알려줘", "밀가루와 설탕을 섞어 구우면 됩니다.")
        is False
    )


class SpyLlmStream:
    def __init__(self):
        self.received_chunks = []

    async def __call__(self, message: str, context: dict, chunks: list[str]):
        self.received_chunks = chunks
        for char in "fake-llm-reply":
            yield char


class FakeDurDrugRepository:
    def __init__(self, warnings: list[str]) -> None:
        self._warnings = warnings
        self.received_calls: list[tuple[str, bool, bool]] = []

    def find_dur_warnings(self, item_name: str, *, pregnant: bool, geriatric: bool) -> list[str]:
        self.received_calls.append((item_name, pregnant, geriatric))
        return self._warnings


async def test_dur_warning_injected_for_geriatric_profile():
    """실제 Profile.age(>=65)로 판별되는 고령자는 복용 약물에 DUR 경고가 있으면 주입된다.
    (임신 여부는 Profile 스키마에 실제 데이터가 없어 이 경로로 테스트할 수 없다 — #71 참고,
    게이팅 로직 자체는 test_collect_dur_warnings_gates_on_pregnant_flag가 커버한다.)"""
    repository = FakeChatRepository()
    spy_llm = SpyLlmStream()
    profiles = FakeProfileRepository({2: FakeProfile(id=2, name="어르신", age=75)})
    medications = FakeMedicationRepository({2: [FakeMedicationSchedule(medication=FakeMedication("아스피린"))]})
    fake_dur_repo = FakeDurDrugRepository(["[노인주의 경고] 아스피린: 테스트용 경고 문구"])

    service = _build_service(
        repository,
        profile_repository=profiles,
        medication_repository=medications,
        llm_stream=spy_llm,
        dur_drug_repository=fake_dur_repo,
    )

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=2, session_id=11, message="아스피린 먹어도 괜찮은지 물어봅니다.")
    )

    assert chunks[-1]["type"] == "done"
    assert chunks[-1]["disclaimer"] == DISCLAIMER_TEXT
    assert any("[노인주의 경고]" in c for c in spy_llm.received_chunks)
    assert fake_dur_repo.received_calls == [("아스피린", False, True)]


def test_collect_dur_warnings_gates_on_pregnant_flag():
    """임부금기 게이팅 로직 자체(진짜 프로필로는 재현 불가)를 직접 검증한다."""
    fake_dur_repo = FakeDurDrugRepository(["[임부금기 경고] 콘서타: 테스트용 경고 문구"])
    service = ChatService(dur_drug_repository=cast(DurDrugRepository, fake_dur_repo))

    warnings = service._collect_dur_warnings([{"name": "콘서타"}], is_pregnant=True, is_geriatric=False)

    assert warnings == ["[임부금기 경고] 콘서타: 테스트용 경고 문구"]
    assert fake_dur_repo.received_calls == [("콘서타", True, False)]
