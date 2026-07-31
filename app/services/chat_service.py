"""
T-LLM-2: 응급 감지 → (아니면) 히스토리/컨텍스트 조회 → 통합 RAG 스트리밍 → 대화 저장.
`docs/dev/sample_code_chat/app/services/chat_service.py`의 검증된 흐름을 실제
SQLAlchemy(AsyncSession) 기반으로 옮긴 것 — 흐름 구조 자체는 동일하다.

T-LLM-7-3-2: DUR 검색(`/retrieve`)과 논문 검색+답변(`/agent/paper-search`)이 따로
놀고, 실제 답변 생성(LLM 호출)은 `app/`가 자체적으로(`llm_stub.py`) 하던 구조를
걷어냈다. 이제 DUR+논문 검색과 LLM 생성 전부가 `ai_worker`의 통합 스트리밍
엔드포인트(`/agent/chat`) 하나로 들어가 있고, `app/`는 응급 판정(안전 게이팅)과
사용자 개인 복약정보 기반 DUR 경고(SQL 조회라 ai_worker가 계산 못 함)만 처리해
`injected_context`로 넘긴 뒤, 그 스트림을 그대로 중계 + 저장 + 면책문구 부착만 한다.

응급 판정은 키워드 필터링만 쓴다(결정: 2026-07-16). 한때 LLM 분류를 병행 추가했었으나
(파라프레이즈로 키워드를 피해가는 표현을 잡기 위함) 매 턴 ~1.3초의 직렬 대기가 추가돼
되돌렸다 — 속도를 우선하기로 한 결정이며, 키워드 목록이 놓치는 표현이 실제로 문제가
되면 그때 키워드를 보강하는 쪽으로 대응한다(LLM 분류 재도입이 아니라).
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import config
from app.core.db.databases import AsyncSessionLocal
from app.models.chat import MessageRole
from app.repositories.chat_repository import ChatRepository
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.profile_repository import ProfileRepository
from app.services import safety_service
from app.services.ai_worker_gateway import (
    AIWorkerGateway,
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.chat_context_service import ChatContextService
from app.services.dur_service import DurScreeningService
from app.services.notification_settings_service import NotificationSettingsService
from app.services.push_service import PushService
from app.services.quiet_hours import is_in_quiet_hours

logger = logging.getLogger("app.chat_service")

_AI_WORKER_ERRORS = (AIWorkerUnavailableError, AIWorkerProcessingError, AIWorkerInvalidRequestError)

# 스트림이 이미 시작된 뒤(사용자에게 이미 일부 토큰이 보인 뒤) 실패하면 상태 코드로
# 알릴 수 없으므로, 받은 만큼만 살리고 이 안내문을 이어붙인 뒤 정상 종료 절차(저장/면책
# 문구 판정)를 그대로 밟는다.
_STREAM_INTERRUPTED_NOTICE = "[응답이 중단되었습니다. 잠시 후 다시 시도해주세요.]"

# 답변 생성을 요청 연결과 무관하게 끝까지 돌리려고 asyncio.create_task로 분리하는데(아래
# ChatService._run_detached 참고), 태스크 객체 참조를 아무 데도 안 들고 있으면 파이썬이
# 도중에 가비지컬렉트해버릴 수 있다(공식 문서가 명시적으로 경고하는 함정) - 여기 모아뒀다가
# 끝나면 스스로 빠지게 한다.
_background_tasks: set[asyncio.Task] = set()


class MedicalRelatednessClassification(BaseModel):
    is_medical_related: bool


_MEDICAL_RELATEDNESS_SYSTEM_PROMPT = (
    "당신은 대화 한 턴(사용자 질문 + 어시스턴트 답변)을 보고, 하단에 의학적 조언이 아니라는 "
    "면책 문구를 노출해야 하는지 판단하는 분류기입니다.\n"
    "다음 중 하나라도 답변에 실제로 포함된 경우에만 true로 판단하세요:\n"
    "- 특정 약물의 복용법/부작용/상호작용/DUR 경고\n"
    "- 질병 진단 또는 감별 진단 관련 언급\n"
    "- 특정 증상에 대한 임상적 처치/치료 조언\n"
    "- 생리적 부작용이나 신체 반응에 대한 구체적 설명\n"
    "다음은 명확히 false로 판단해야 하는 예시입니다(자주 오탐되는 경계 사례):\n"
    "- '오늘 아침 뭘 먹을까' 같은 일반 식단/레시피 질문 → false\n"
    "- 운동 계획, 수면 시간, 일정 관리 등 생활 습관 질문(질병/약물과 무관) → false\n"
    "- 일반 잡담, 인사, 감정 표현 → false\n"
    "확신이 서지 않으면 false를 반환하세요(과다 판정보다 과소 판정이 낫습니다).\n"
    'JSON 형식으로만 답하세요: {"is_medical_related": true} 또는 {"is_medical_related": false}'
)


class ChatService:
    def __init__(
        self,
        repository: ChatRepository | None = None,
        chat_context_service: ChatContextService | None = None,
        retriever: AIWorkerGateway | None = None,
        dur_drug_repository: DurDrugRepository | None = None,
        profile_repository: ProfileRepository | None = None,
        medication_repository: MedicationRepository | None = None,
        dur_screening_service: DurScreeningService | None = None,
        push_service: PushService | None = None,
        notification_settings_service: NotificationSettingsService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._repository = repository or ChatRepository()
        self._chat_context_service = chat_context_service or ChatContextService()
        self._retriever = retriever or AIWorkerGateway()
        self._dur_drug_repository = dur_drug_repository or DurDrugRepository()
        self._profile_repository = profile_repository or ProfileRepository()
        self._medication_repository = medication_repository or MedicationRepository()
        self._dur_screening_service = dur_screening_service or DurScreeningService()
        self._push_service = push_service or PushService()
        self._notification_settings_service = notification_settings_service or NotificationSettingsService()
        # _run_detached()가 요청 스코프 session 대신 이 팩토리로 독립된 세션을 새로 연다.
        self._session_factory = session_factory or AsyncSessionLocal

    async def create_session(self, session: AsyncSession, profile_id: int):
        return await self._repository.create_session(session, profile_id)

    async def stream_reply(self, profile_id: int, session_id: int, message: str) -> AsyncIterator[dict]:
        """
        응급 키워드가 감지되면 LLM을 호출하지 않고 고정 fallback만 반환한다(T-LLM-1 원칙).
        이 경우 대화 기록도 저장하지 않고, 별도 태스크도 만들지 않는다.

        응급이 아니면 실제 생성(`_generate`)은 `_run_detached` 태스크로 분리해서 시작한다 -
        사용자가 채팅 화면을 벗어나거나 탭을 닫아도(라우터의 StreamingResponse 소비가
        Starlette에 의해 취소돼도) 생성 자체는 끝까지 진행되어 저장과 답변 완료 알림까지
        마치도록 하기 위함이다(F-NTFY-6 챗봇 답변 알림). 이 제너레이터는 그 태스크가 큐에
        넣는 청크를 그대로 릴레이만 한다."""
        if safety_service.check_emergency(message):
            yield {
                "type": "emergency_fallback",
                "content": safety_service.EMERGENCY_FALLBACK_MESSAGE,
                "disclaimer": safety_service.DISCLAIMER_TEXT,
            }
            return

        queue: asyncio.Queue[dict | None] = asyncio.Queue()
        task = asyncio.create_task(self._run_detached(profile_id, session_id, message, queue))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        while True:
            chunk = await queue.get()
            if chunk is None:
                return
            yield chunk

    async def _run_detached(
        self, profile_id: int, session_id: int, message: str, queue: "asyncio.Queue[dict | None]"
    ) -> None:
        """호출자(라우터)의 요청-스코프 session을 쓰지 않고 독립된 세션을 새로 연다 -
        habit_repository.save_subtype_suggestions와 같은 이유다: 요청이 끝나면(탭이
        닫히면) 그 session은 닫히지만, 이 태스크는 그 뒤에도 계속 돌아야 한다."""
        try:
            async with self._session_factory() as session:
                async for chunk in self._generate(session, profile_id, session_id, message):
                    await queue.put(chunk)
        except Exception:
            logger.exception("채팅 답변 생성 태스크 실패 (profile_id=%s, session_id=%s)", profile_id, session_id)
        finally:
            queue.put_nowait(None)

    async def _generate(
        self, session: AsyncSession, profile_id: int, session_id: int, message: str
    ) -> AsyncIterator[dict]:
        history = await self._repository.list_messages(session, session_id)

        # profile은 이 턴에서 한 번만 조회하고, 그 결과로 컨텍스트/DUR 게이팅을 전부 파생시킨다.
        profile = await self._profile_repository.get_profile(session, profile_id)
        medications = (
            await self._medication_repository.list_schedules_by_profile(session, profile_id) if profile else []
        )
        drug_names = await self._dur_drug_repository.get_names_by_item_seqs(session, {m.item_seq for m in medications})
        context = self._chat_context_service.build(profile, medications, drug_names)
        # MessageRole enum 값 자체가 "USER"/"ASSISTANT"(대문자)라, OpenAI 메시지 role로
        # 그대로 보내면 거부당한다(소문자 "user"/"assistant"만 허용) — chat_routers.py의
        # 이력 조회 응답과 동일하게 여기서도 API 경계에서 소문자로 변환한다.
        history_payload = [{"role": m.role.value.lower(), "content": m.content} for m in history]

        dur_warnings = await self._collect_dur_warnings(
            session, context["medications"], context["is_pregnant"], context["is_geriatric"]
        )
        interaction_warnings = await self._collect_interaction_warnings(session, context["medications"])
        injected_context = [f"[DUR 안전 경고 정보] 복용 약물 중 위험 경고 발견: {w}" for w in dur_warnings] + [
            f"[병용금기 경고] {w}" for w in interaction_warnings
        ]

        full_response = ""
        sources: list[dict] = []
        has_sources = bool(injected_context)  # 개인 DUR 경고가 있으면 이미 의료 관련 확정
        try:
            async for chunk in self._retriever.stream_chat(message, context, history_payload, injected_context):
                if chunk["type"] == "token":
                    full_response += chunk["content"]
                    yield chunk
                elif chunk["type"] == "sources":
                    sources = chunk["sources"]
                    has_sources = has_sources or bool(sources)
                    yield chunk
                elif chunk["type"] == "error":
                    logger.error(
                        "채팅 스트림 도중 오류(ai_worker 보고), 받은 만큼만 저장 (%d자, 내용 미기록)",
                        len(chunk["content"]),
                    )
                    full_response = self._append_interrupted_notice(full_response)
                    yield {"type": "token", "content": _STREAM_INTERRUPTED_NOTICE}
                    break
        except _AI_WORKER_ERRORS as e:
            logger.error("채팅 스트림 연결 실패, 받은 만큼만 저장: %s (내용 미기록)", type(e).__name__)
            full_response = self._append_interrupted_notice(full_response)
            yield {"type": "token", "content": _STREAM_INTERRUPTED_NOTICE}

        # DUR/논문 출처(또는 개인 DUR 경고)가 전혀 없으면 의료 관련 콘텐츠일 가능성이 낮으므로,
        # 매 턴 LLM 왕복(~1초) 없이 키워드 폴백만으로 판정한다 — 있으면 정밀도 위해 LLM 분류.
        # 저장 전에 먼저 계산해야 어시스턴트 메시지에 면책 문구를 함께 저장할 수 있다(과거엔
        # "done" 청크로만 내보내고 저장하지 않아, 히스토리를 다시 불러오면 면책 문구가
        # 사라지는 버그가 있었음).
        is_medical = (
            await self._check_if_medical_related_via_llm(message, full_response)
            if has_sources
            else self._is_medical_related_fallback(message, full_response)
        )
        disclaimer = safety_service.DISCLAIMER_TEXT if is_medical else ""

        await self._repository.save_message(session, session_id, MessageRole.USER, message)
        await self._repository.save_message(
            session,
            session_id,
            MessageRole.ASSISTANT,
            full_response,
            sources=sources or None,
            disclaimer=disclaimer or None,
        )

        # 저장까지 끝난 뒤(= 이 턴이 완전히 끝난 뒤) 보낸다 - "done" 청크 이후에는 코드를
        # 더 못 두므로(이 async generator가 여기서 끝남) 반드시 yield 이전에 호출해야 한다.
        # 이 메서드는 _run_detached 태스크 안에서 독립 세션으로 돌아서, 사용자가 채팅
        # 화면을 벗어나거나 탭을 완전히 닫아도 여기까지는 끝까지 실행된다 - 대화 내용
        # 자체는 알림 문구에 담지 않는다(잠금화면 노출 등 프라이버시 고려).
        try:
            settings = await self._notification_settings_service.get_settings(session, profile_id)
            # 챗봇 답변 알림은 필수 알림(복약)이 아니라, 무음 시간대엔 보류한다(F-NTFY-6).
            if settings.chatbot_reply_enabled and not is_in_quiet_hours(settings, datetime.now(tz=config.TIMEZONE)):
                await self._push_service.send_to_profile(
                    session,
                    profile_id,
                    title="💬 AI 상담 답변 도착",
                    body="질문하신 내용에 답변이 도착했어요.",
                    link_url="/chat",
                )
        except Exception:
            logger.exception("챗봇 답변 알림 발송 실패 (profile_id=%s)", profile_id)

        yield {"type": "done", "content": "", "disclaimer": disclaimer}

    @staticmethod
    def _append_interrupted_notice(full_response: str) -> str:
        if not full_response:
            return _STREAM_INTERRUPTED_NOTICE
        return f"{full_response}\n\n{_STREAM_INTERRUPTED_NOTICE}"

    async def _collect_dur_warnings(
        self, session: AsyncSession, meds: list[dict], is_pregnant: bool, is_geriatric: bool
    ) -> list[str]:
        if not ((is_pregnant or is_geriatric) and meds):
            return []

        dur_warnings: list[str] = []
        for med in meds:
            med_name = med.get("name", "")
            dur_warnings.extend(
                await self._dur_drug_repository.find_dur_warnings(
                    session, med_name, pregnant=is_pregnant, geriatric=is_geriatric
                )
            )
        return list(set(dur_warnings))

    async def _collect_interaction_warnings(self, session: AsyncSession, meds: list[dict]) -> list[str]:
        # 병용금기/효능군중복은 조합 위험이라 임신/노인 여부와 무관하게 항상 확인한다
        # (_collect_dur_warnings의 게이팅과 달리 대상이 전체 사용자).
        if len(meds) < 2:
            return []

        med_names = [med.get("name", "") for med in meds]
        response = await self._dur_screening_service.screen_interactions(session, med_names)
        return [
            f"{w.drug_a.item_name} + {w.drug_b.item_name} ({w.rule_type}) — {w.prohbt_content or w.remark or ''}"
            for w in response.drug_intrc.interactions
        ]

    async def _check_if_medical_related_via_llm(self, message: str, response: str) -> bool:
        try:
            result = await self._retriever.call_structured(
                system_prompt=_MEDICAL_RELATEDNESS_SYSTEM_PROMPT,
                user_input=f"User: {message}\nAssistant: {response}",
                schema=MedicalRelatednessClassification,
            )
        except _AI_WORKER_ERRORS as e:
            logger.warning(f"의료 관련성 LLM 분류 실패, 키워드 폴백으로 전환: {e}")
            return self._is_medical_related_fallback(message, response)
        return cast(MedicalRelatednessClassification, result).is_medical_related

    def _is_medical_related_fallback(self, message: str, response: str) -> bool:
        # 의료 키워드 목록은 safety_service가 단일 소유한다("판단은 여기서만" 원칙).
        return safety_service.is_medical_related(message, response)
