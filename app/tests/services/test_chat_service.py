from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import cast

from app.models.chat import MessageRole
from app.models.profiles import Disease
from app.repositories.chat_repository import ChatRepository
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.ai_worker_gateway import AIWorkerGateway, AIWorkerUnavailableError
from app.services.chat_service import ChatService, EmergencyClassification, MedicalRelatednessClassification
from app.services.safety_service import DISCLAIMER_TEXT, EMERGENCY_FALLBACK_MESSAGE


class FakeChatRepository:
    def __init__(self) -> None:
        self.saved_messages: list[tuple[int, MessageRole, str]] = []

    async def save_message(self, session, session_id: int, role: MessageRole, content: str) -> None:
        self.saved_messages.append((session_id, role, content))

    async def list_messages(self, session, session_id: int, limit: int = 20) -> list[str]:
        return []


@dataclass
class FakeDiagnosisEntry:
    """`chat_context_service.py`가 `e.disease.value`로 읽으므로, disease는 실제 Disease enum을 쓴다."""

    disease: Disease


@dataclass
class FakeProfile:
    # [정규화] diagnosis_history(JSON) -> diagnosis_entries(관계형 리스트)로 필드명/타입 변경.
    id: int
    name: str = "사용자"
    age: int | None = None
    is_pregnant: bool | None = None
    diagnosis_entries: list[FakeDiagnosisEntry] = field(default_factory=list)
    family_history_entries: list[FakeDiagnosisEntry] = field(default_factory=list)


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
    """`call_structured`는 기본적으로 응급=False/의료관련=True를 반환한다("두통약 뭐가 좋아요?"
    같은 기존 테스트 메시지들이 면책문구를 받는다고 가정하던 동작을 그대로 유지하기 위함).
    `raise_on_structured`를 주면 두 분류 호출 모두 그 예외를 던져 ai_worker 장애 상황을 재현한다."""

    def __init__(
        self,
        is_emergency: bool = False,
        is_medical_related: bool = True,
        raise_on_structured: Exception | None = None,
        paper_result: dict | None = None,
        raise_on_paper_agent: Exception | None = None,
    ) -> None:
        self.is_emergency = is_emergency
        self.is_medical_related = is_medical_related
        self.raise_on_structured = raise_on_structured
        self.structured_calls: list[tuple[str, str, type]] = []
        # 기본은 "논문 검색 범위 밖"(sources 빈 목록) — 기존 테스트가 전제하는 일반
        # DUR RAG 흐름을 그대로 타도록 한다.
        self.paper_result = paper_result if paper_result is not None else {"answer": "", "sources": []}
        self.raise_on_paper_agent = raise_on_paper_agent
        self.paper_agent_calls: list[str] = []

    async def search(self, query: str) -> list[dict]:
        return [{"content": "fake-chunk-1", "metadata": {"source": "fake_source.csv"}}]

    async def call_structured(self, system_prompt: str, user_input: str, schema: type):
        self.structured_calls.append((system_prompt, user_input, schema))
        if self.raise_on_structured is not None:
            raise self.raise_on_structured
        if schema is EmergencyClassification:
            return EmergencyClassification(is_emergency=self.is_emergency)
        if schema is MedicalRelatednessClassification:
            return MedicalRelatednessClassification(is_medical_related=self.is_medical_related)
        raise AssertionError(f"예상치 못한 schema: {schema}")

    async def ask_paper_agent(self, question: str) -> dict:
        self.paper_agent_calls.append(question)
        if self.raise_on_paper_agent is not None:
            raise self.raise_on_paper_agent
        return self.paper_result


async def fake_llm_stream(message: str, context: dict, chunks: list[str]):
    for char in "fake-llm-reply":
        yield char


def _build_service(
    repository: FakeChatRepository,
    profile_repository: FakeProfileRepository | None = None,
    medication_repository: FakeMedicationRepository | None = None,
    llm_stream=fake_llm_stream,
    dur_drug_repository=None,
    retriever: FakeRetriever | None = None,
) -> ChatService:
    # Fake들은 실제 클래스와 시그니처만 맞춘 덕타이핑 객체라 mypy 통과용으로 cast한다.
    kwargs = dict(
        repository=cast(ChatRepository, repository),
        retriever=cast(AIWorkerGateway, retriever or FakeRetriever()),
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


async def test_check_if_medical_related_uses_ai_worker_result():
    """ai_worker(`call_structured`)가 성공하면 그 결과를 그대로 신뢰한다(키워드 폴백 미사용)."""
    retriever = FakeRetriever(is_medical_related=True)
    service = ChatService(retriever=cast(AIWorkerGateway, retriever))

    assert await service._check_if_medical_related_via_llm("오늘 아침 뭘 먹을까?", "계란후라이 어때요?") is True
    assert retriever.structured_calls[-1][2] is MedicalRelatednessClassification


async def test_check_if_medical_related_falls_back_to_keyword_when_ai_worker_unavailable():
    """ai_worker 호출이 실패하면 키워드 폴백(`_is_medical_related_fallback`)으로 전환한다."""
    retriever = FakeRetriever(raise_on_structured=AIWorkerUnavailableError("down"))
    service = ChatService(retriever=cast(AIWorkerGateway, retriever))

    assert (
        await service._check_if_medical_related_via_llm("아스피린 부작용 있나요?", "부작용이 있을 수 있습니다.") is True
    )
    assert await service._check_if_medical_related_via_llm("오늘 날씨 어때?", "맑고 따뜻합니다.") is False


async def test_emergency_llm_check_catches_phrase_outside_keyword_list():
    """키워드 목록에 없는 표현도 ai_worker LLM 판정이 응급으로 잡으면 short-circuit한다."""
    repository = FakeChatRepository()
    retriever = FakeRetriever(is_emergency=True)
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=1, session_id=10, message="갑자기 말이 잘 안 나와요")
    )

    assert chunks == [
        {"type": "emergency_fallback", "content": EMERGENCY_FALLBACK_MESSAGE, "disclaimer": DISCLAIMER_TEXT}
    ]
    assert repository.saved_messages == []


async def test_ai_worker_unavailable_falls_back_to_keyword_only_emergency_gating():
    """ai_worker가 응답 불가면 응급 판정은 키워드 결과만으로 게이팅한다(전체 채팅을 막지 않음)."""
    repository = FakeChatRepository()
    profiles = FakeProfileRepository({1: FakeProfile(id=1, name="사용자")})
    retriever = FakeRetriever(raise_on_structured=AIWorkerUnavailableError("down"), is_medical_related=False)
    service = _build_service(repository, profile_repository=profiles, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="안녕하세요"))

    assert chunks[-1] == {"type": "done", "content": "", "disclaimer": ""}
    assert repository.saved_messages != []


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


async def test_paper_agent_answer_used_when_sources_present():
    """paper-search가 sources를 반환하면(질문이 논문 검색 범위 안이라는 뜻) 그 답변+출처를
    그대로 반환하고, 일반 DUR RAG 흐름(토큰 스트리밍)은 타지 않는다."""
    repository = FakeChatRepository()
    paper_sources = [{"name": "Paper A", "url": "https://pubmed.ncbi.nlm.nih.gov/111/"}]
    retriever = FakeRetriever(paper_result={"answer": "HbA1c가 감소했습니다.", "sources": paper_sources})
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=1, session_id=10, message="당뇨 저혈당 관리 논문 알려줘")
    )

    assert chunks[0] == {"type": "paper_answer", "content": "HbA1c가 감소했습니다.", "sources": paper_sources}
    assert chunks[-1]["type"] == "done"
    assert not any(c["type"] == "token" for c in chunks)
    assert repository.saved_messages == [
        (10, MessageRole.USER, "당뇨 저혈당 관리 논문 알려줘"),
        (10, MessageRole.ASSISTANT, "HbA1c가 감소했습니다.\n\n[출처: Paper A]"),
    ]


async def test_paper_agent_falls_back_to_generic_flow_when_no_sources():
    """paper-search가 sources 없이 응답하면(범위 밖 질문) 기존 일반 DUR RAG 흐름으로 폴백한다."""
    repository = FakeChatRepository()
    profiles = FakeProfileRepository({1: FakeProfile(id=1, name="사용자")})
    retriever = FakeRetriever()  # 기본값: sources=[]
    service = _build_service(repository, profile_repository=profiles, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="오늘 날씨 어때?"))

    assert retriever.paper_agent_calls == ["오늘 날씨 어때?"]
    assert any(c["type"] == "token" for c in chunks)
    assert not any(c["type"] == "paper_answer" for c in chunks)


async def test_paper_agent_unavailable_falls_back_to_generic_flow():
    """ai_worker 논문 검색이 실패해도 전체 채팅은 막지 않고 일반 흐름으로 계속 진행한다."""
    repository = FakeChatRepository()
    profiles = FakeProfileRepository({1: FakeProfile(id=1, name="사용자")})
    retriever = FakeRetriever(raise_on_paper_agent=AIWorkerUnavailableError("down"))
    service = _build_service(repository, profile_repository=profiles, retriever=retriever)

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=1, session_id=10, message="당뇨 저혈당 관리 논문 알려줘")
    )

    assert any(c["type"] == "token" for c in chunks)
    assert not any(c["type"] == "paper_answer" for c in chunks)


async def test_emergency_short_circuits_even_when_paper_agent_found_sources():
    """응급이 감지되면 paper-search가 이미 sources를 찾아뒀더라도 노출하지 않고 fallback만 반환한다."""
    repository = FakeChatRepository()
    paper_sources = [{"name": "Paper A", "url": "https://pubmed.ncbi.nlm.nih.gov/111/"}]
    retriever = FakeRetriever(paper_result={"answer": "논문 답변", "sources": paper_sources})
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="가슴 통증 있어요"))

    assert chunks == [
        {"type": "emergency_fallback", "content": EMERGENCY_FALLBACK_MESSAGE, "disclaimer": DISCLAIMER_TEXT}
    ]
    assert repository.saved_messages == []


def test_collect_dur_warnings_gates_on_pregnant_flag():
    """임부금기 게이팅 로직 자체(진짜 프로필로는 재현 불가)를 직접 검증한다."""
    fake_dur_repo = FakeDurDrugRepository(["[임부금기 경고] 콘서타: 테스트용 경고 문구"])
    service = ChatService(dur_drug_repository=cast(DurDrugRepository, fake_dur_repo))

    warnings = service._collect_dur_warnings([{"name": "콘서타"}], is_pregnant=True, is_geriatric=False)

    assert warnings == ["[임부금기 경고] 콘서타: 테스트용 경고 문구"]
    assert fake_dur_repo.received_calls == [("콘서타", True, False)]
