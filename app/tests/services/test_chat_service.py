from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast

from app.models.chat import MessageRole
from app.models.profiles import Disease
from app.repositories.chat_repository import ChatRepository
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.ai_worker_gateway import AIWorkerGateway, AIWorkerUnavailableError
from app.services.chat_service import ChatService, MedicalRelatednessClassification
from app.services.safety_service import DISCLAIMER_TEXT, EMERGENCY_FALLBACK_MESSAGE


@dataclass
class FakeChatMessage:
    role: MessageRole
    content: str


class FakeChatRepository:
    def __init__(self, history: list[FakeChatMessage] | None = None) -> None:
        self.saved_messages: list[tuple[int, MessageRole, str, list[dict] | None, str | None]] = []
        self._history = history or []

    async def save_message(
        self,
        session,
        session_id: int,
        role: MessageRole,
        content: str,
        sources: list[dict] | None = None,
        disclaimer: str | None = None,
    ) -> None:
        self.saved_messages.append((session_id, role, content, sources, disclaimer))

    async def list_messages(self, session, session_id: int, limit: int = 20) -> list[FakeChatMessage]:
        return self._history


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


_DEFAULT_STREAM_CHUNKS: list[dict] = [
    {"type": "sources", "sources": []},
    {"type": "token", "content": "fake-llm-reply"},
]


class FakeRetriever:
    """`call_structured`는 기본적으로 의료관련=True를 반환한다. `raise_on_structured`를
    주면 그 예외를 던져 ai_worker 장애 상황을 재현한다(의료관련성 분류에만 쓰인다 —
    응급 판정은 키워드 전용이라 더 이상 `call_structured`를 타지 않는다).
    `stream_chunks`는 `ai_worker`의 통합 RAG 스트리밍(`/agent/chat`) 응답을 그대로 흉내낸다."""

    def __init__(
        self,
        is_medical_related: bool = True,
        raise_on_structured: Exception | None = None,
        stream_chunks: list[dict] | None = None,
        raise_after_stream_chunks: Exception | None = None,
    ) -> None:
        self.is_medical_related = is_medical_related
        self.raise_on_structured = raise_on_structured
        self.structured_calls: list[tuple[str, str, type]] = []
        self.stream_chunks = stream_chunks if stream_chunks is not None else list(_DEFAULT_STREAM_CHUNKS)
        self.raise_after_stream_chunks = raise_after_stream_chunks
        self.stream_chat_calls: list[tuple[str, dict, list[dict], list[str]]] = []

    async def call_structured(self, system_prompt: str, user_input: str, schema: type):
        self.structured_calls.append((system_prompt, user_input, schema))
        if self.raise_on_structured is not None:
            raise self.raise_on_structured
        if schema is MedicalRelatednessClassification:
            return MedicalRelatednessClassification(is_medical_related=self.is_medical_related)
        raise AssertionError(f"예상치 못한 schema: {schema}")

    async def stream_chat(
        self, message: str, context: dict, history: list[dict], injected_context: list[str]
    ) -> AsyncIterator[dict]:
        self.stream_chat_calls.append((message, context, history, injected_context))
        for chunk in self.stream_chunks:
            yield chunk
        if self.raise_after_stream_chunks is not None:
            raise self.raise_after_stream_chunks


def _build_service(
    repository: FakeChatRepository,
    profile_repository: FakeProfileRepository | None = None,
    medication_repository: FakeMedicationRepository | None = None,
    dur_drug_repository=None,
    retriever: FakeRetriever | None = None,
) -> ChatService:
    # Fake들은 실제 클래스와 시그니처만 맞춘 덕타이핑 객체라 mypy 통과용으로 cast한다.
    kwargs: dict[str, Any] = dict(
        repository=cast(ChatRepository, repository),
        retriever=cast(AIWorkerGateway, retriever or FakeRetriever()),
        profile_repository=cast(ProfileRepository, profile_repository or FakeProfileRepository()),
        medication_repository=cast(MedicationRepository, medication_repository or FakeMedicationRepository()),
    )
    if dur_drug_repository is not None:
        kwargs["dur_drug_repository"] = cast(DurDrugRepository, dur_drug_repository)
    return ChatService(**kwargs)


async def _collect(stream: AsyncIterator[dict]) -> list[dict]:
    return [chunk async for chunk in stream]


async def test_emergency_keyword_short_circuits_without_saving():
    """응급 판정은 키워드 전용이다(속도 우선 결정, 2026-07-16) — LLM 호출 자체가 없다."""
    repository = FakeChatRepository()
    retriever = FakeRetriever()
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="가슴 통증 있어요"))

    assert chunks == [
        {"type": "emergency_fallback", "content": EMERGENCY_FALLBACK_MESSAGE, "disclaimer": DISCLAIMER_TEXT}
    ]
    assert repository.saved_messages == []
    # 응급이면 ai_worker에 RAG+생성 스트리밍 요청도, LLM 분류 호출도 전혀 보내지 않는다.
    assert retriever.stream_chat_calls == []
    assert retriever.structured_calls == []


async def test_normal_message_streams_sources_then_tokens_and_saves_conversation():
    """sources는 ai_worker가 보낸 그대로 전달되고(본문 텍스트에 섞이지 않음),
    저장되는 답변 내용도 순수 LLM 답변 텍스트뿐이다(옛 "[출처: ...]" 텍스트 접미사는 사라짐).
    출처와 면책 문구 자체도 assistant 메시지와 함께 저장돼야 과거 대화를 다시 불러올 때
    칩/면책 문구가 복원된다(버그: 과거엔 sources/disclaimer가 DB에 저장되지 않아 히스토리
    로드 시 둘 다 사라졌음, 2026-07-16)."""
    repository = FakeChatRepository()
    profiles = FakeProfileRepository({1: FakeProfile(id=1, name="사용자")})
    stream_chunks = [
        {"type": "sources", "sources": [{"name": "식약처 DUR 노인주의 정보", "url": None}]},
        {"type": "token", "content": "fake-"},
        {"type": "token", "content": "llm-reply"},
    ]
    retriever = FakeRetriever(stream_chunks=stream_chunks)
    service = _build_service(repository, profile_repository=profiles, retriever=retriever)

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=1, session_id=10, message="두통약 뭐가 좋아요?")
    )

    assert chunks[0] == stream_chunks[0]
    assert chunks[-1] == {"type": "done", "content": "", "disclaimer": DISCLAIMER_TEXT}
    token_chunks = [c for c in chunks if c["type"] == "token"]
    full_reply = "".join(c["content"] for c in token_chunks)
    assert full_reply == "fake-llm-reply"
    assert repository.saved_messages == [
        (10, MessageRole.USER, "두통약 뭐가 좋아요?", None, None),
        (
            10,
            MessageRole.ASSISTANT,
            "fake-llm-reply",
            [{"name": "식약처 DUR 노인주의 정보", "url": None}],
            DISCLAIMER_TEXT,
        ),
    ]


async def test_medical_response_saves_disclaimer_with_assistant_message():
    """면책 문구도 sources와 같은 이유로 assistant 메시지에 저장돼야 한다 — 과거엔 "done"
    청크로만 내보내고 저장하지 않아 히스토리를 다시 불러오면 면책 문구가 사라졌다(2026-07-16)."""
    repository = FakeChatRepository()
    stream_chunks = [
        {"type": "sources", "sources": [{"name": "식약처 DUR 노인주의 정보", "url": None}]},
        {"type": "token", "content": "약물 답변"},
    ]
    retriever = FakeRetriever(stream_chunks=stream_chunks, is_medical_related=True)
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(
        service.stream_reply(session=None, profile_id=1, session_id=10, message="타이레놀 먹어도 되나요?")
    )

    assert chunks[-1] == {"type": "done", "content": "", "disclaimer": DISCLAIMER_TEXT}
    saved_disclaimer = repository.saved_messages[-1][4]
    assert saved_disclaimer == DISCLAIMER_TEXT


async def test_normal_message_saves_none_sources_when_no_rag_matches():
    """RAG 매칭이 하나도 없으면 빈 배열이 아니라 None으로 저장한다(스트림 응답 자체는
    그대로 빈 배열 chunk를 유지 — 프론트 프로토콜은 안 바뀜)."""
    repository = FakeChatRepository()
    retriever = FakeRetriever()  # 기본 stream_chunks: sources=[]

    service = _build_service(repository, retriever=retriever)

    await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="잡담"))

    assert repository.saved_messages[-1] == (10, MessageRole.ASSISTANT, "fake-llm-reply", None, None)


async def test_stream_reply_lowercases_history_roles_for_openai_compatibility():
    """MessageRole enum 값 자체가 "USER"/"ASSISTANT"(대문자)인데, ai_worker가 이 history를
    그대로 OpenAI 메시지 role에 spread하므로 소문자가 아니면 두 번째 턴부터 OpenAI가
    거부한다(400) — API 경계에서 반드시 소문자로 변환해야 한다."""
    repository = FakeChatRepository(
        history=[
            FakeChatMessage(role=MessageRole.USER, content="이전 질문"),
            FakeChatMessage(role=MessageRole.ASSISTANT, content="이전 답변"),
        ]
    )
    retriever = FakeRetriever()
    service = _build_service(repository, retriever=retriever)

    await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="다음 질문"))

    _, _, history_payload, _ = retriever.stream_chat_calls[0]
    assert history_payload == [
        {"role": "user", "content": "이전 질문"},
        {"role": "assistant", "content": "이전 답변"},
    ]


async def test_stream_reply_passes_history_context_and_injected_dur_warnings():
    repository = FakeChatRepository()
    profiles = FakeProfileRepository({2: FakeProfile(id=2, name="어르신", age=75)})
    medications = FakeMedicationRepository({2: [FakeMedicationSchedule(medication=FakeMedication("아스피린"))]})
    fake_dur_repo = FakeDurDrugRepository(["[노인주의 경고] 아스피린: 테스트용 경고 문구"])
    retriever = FakeRetriever()
    service = _build_service(
        repository,
        profile_repository=profiles,
        medication_repository=medications,
        dur_drug_repository=fake_dur_repo,
        retriever=retriever,
    )

    await _collect(
        service.stream_reply(session=None, profile_id=2, session_id=11, message="아스피린 먹어도 괜찮은지 물어봅니다.")
    )

    assert len(retriever.stream_chat_calls) == 1
    message, context, history, injected_context = retriever.stream_chat_calls[0]
    assert message == "아스피린 먹어도 괜찮은지 물어봅니다."
    assert context["name"] == "어르신"
    assert history == []
    assert any("[노인주의 경고] 아스피린" in c for c in injected_context)
    assert fake_dur_repo.received_calls == [("아스피린", False, True)]


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


async def test_medical_relatedness_uses_llm_when_ai_worker_sources_present():
    """DUR/논문 출처가 하나라도 있으면 정밀도를 위해 LLM 분류를 호출한다."""
    repository = FakeChatRepository()
    stream_chunks = [
        {"type": "sources", "sources": [{"name": "식약처 DUR 노인주의 정보", "url": None}]},
        {"type": "token", "content": "답변"},
    ]
    retriever = FakeRetriever(stream_chunks=stream_chunks, is_medical_related=True)
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="질문"))

    assert retriever.structured_calls
    assert retriever.structured_calls[-1][2] is MedicalRelatednessClassification
    assert chunks[-1] == {"type": "done", "content": "", "disclaimer": DISCLAIMER_TEXT}


async def test_medical_relatedness_skips_llm_when_no_sources_at_all():
    """출처가 전혀 없으면(RAG 매칭 0건, 개인 DUR 경고도 없음) 매 턴 ~1초짜리 LLM 왕복을
    아끼기 위해 호출 없이 키워드 폴백만 쓴다."""
    repository = FakeChatRepository()
    stream_chunks = [
        {"type": "sources", "sources": []},
        {"type": "token", "content": "오늘 날씨는 맑습니다"},
    ]
    retriever = FakeRetriever(stream_chunks=stream_chunks)
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="오늘 날씨 어때?"))

    assert retriever.structured_calls == []
    assert chunks[-1] == {"type": "done", "content": "", "disclaimer": ""}


async def test_medical_relatedness_uses_llm_when_injected_dur_warning_present_even_without_ai_worker_sources():
    """개인 DUR 경고(SQL 조회)가 있으면 ai_worker의 sources가 비어 있어도 LLM 분류를 쓴다
    (개인 경고 자체가 이미 의료 관련 콘텐츠라는 신호이기 때문)."""
    repository = FakeChatRepository()
    profiles = FakeProfileRepository({2: FakeProfile(id=2, name="어르신", age=75)})
    medications = FakeMedicationRepository({2: [FakeMedicationSchedule(medication=FakeMedication("아스피린"))]})
    fake_dur_repo = FakeDurDrugRepository(["[노인주의 경고] 아스피린: 테스트용 경고 문구"])
    stream_chunks = [{"type": "sources", "sources": []}, {"type": "token", "content": "답변"}]
    retriever = FakeRetriever(stream_chunks=stream_chunks, is_medical_related=True)
    service = _build_service(
        repository,
        profile_repository=profiles,
        medication_repository=medications,
        dur_drug_repository=fake_dur_repo,
        retriever=retriever,
    )

    await _collect(service.stream_reply(session=None, profile_id=2, session_id=11, message="아스피린 먹어도 되나요"))

    assert retriever.structured_calls
    assert retriever.structured_calls[-1][2] is MedicalRelatednessClassification


async def test_stream_reply_saves_partial_content_when_ai_worker_reports_inband_error():
    """ai_worker가 스트림 도중 {"type": "error", ...}를 보내면(상태 코드로는 이미 알릴 수
    없는 시점) 그때까지 받은 토큰만 살려서 저장하고, 중단 안내문을 이어붙인다."""
    repository = FakeChatRepository()
    stream_chunks = [
        {"type": "sources", "sources": []},
        {"type": "token", "content": "부분 답변"},
        {"type": "error", "content": "OpenAI 오류"},
    ]
    retriever = FakeRetriever(stream_chunks=stream_chunks)
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="질문"))

    assert chunks[-1]["type"] == "done"
    saved_answer = repository.saved_messages[-1][2]
    assert saved_answer.startswith("부분 답변")
    assert "중단되었습니다" in saved_answer


async def test_stream_reply_saves_partial_content_when_stream_connection_fails_midway():
    """ai_worker와의 연결 자체가 스트림 도중 끊기면(AIWorkerUnavailableError) 그때까지
    받은 토큰만 살려서 저장하고, 중단 안내문을 이어붙인다."""
    repository = FakeChatRepository()
    stream_chunks = [
        {"type": "sources", "sources": []},
        {"type": "token", "content": "일부만 "},
        {"type": "token", "content": "도착함"},
    ]
    retriever = FakeRetriever(
        stream_chunks=stream_chunks, raise_after_stream_chunks=AIWorkerUnavailableError("dropped")
    )
    service = _build_service(repository, retriever=retriever)

    chunks = await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="질문"))

    assert chunks[-1]["type"] == "done"
    saved_answer = repository.saved_messages[-1][2]
    assert saved_answer.startswith("일부만 도착함")
    assert "중단되었습니다" in saved_answer


async def test_stream_reply_saves_interruption_notice_when_connection_fails_before_any_token():
    """토큰이 하나도 오기 전에 연결이 끊겨도(예: 첫 요청부터 실패) 빈 답변을 저장하는
    대신 중단 안내문을 답변으로 남긴다."""
    repository = FakeChatRepository()
    retriever = FakeRetriever(stream_chunks=[], raise_after_stream_chunks=AIWorkerUnavailableError("down"))
    service = _build_service(repository, retriever=retriever)

    await _collect(service.stream_reply(session=None, profile_id=1, session_id=10, message="질문"))

    saved_answer = repository.saved_messages[-1][2]
    assert "중단되었습니다" in saved_answer
    assert not saved_answer.startswith("\n")


class FakeDurDrugRepository:
    def __init__(self, warnings: list[str]) -> None:
        self._warnings = warnings
        self.received_calls: list[tuple[str, bool, bool]] = []

    def find_dur_warnings(self, item_name: str, *, pregnant: bool, geriatric: bool) -> list[str]:
        self.received_calls.append((item_name, pregnant, geriatric))
        return self._warnings


def test_collect_dur_warnings_gates_on_pregnant_flag():
    """임부금기 게이팅 로직 자체(진짜 프로필로는 재현 불가)를 직접 검증한다."""
    fake_dur_repo = FakeDurDrugRepository(["[임부금기 경고] 콘서타: 테스트용 경고 문구"])
    service = ChatService(dur_drug_repository=cast(DurDrugRepository, fake_dur_repo))

    warnings = service._collect_dur_warnings([{"name": "콘서타"}], is_pregnant=True, is_geriatric=False)

    assert warnings == ["[임부금기 경고] 콘서타: 테스트용 경고 문구"]
    assert fake_dur_repo.received_calls == [("콘서타", True, False)]
