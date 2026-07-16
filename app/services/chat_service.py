"""
T-LLM-2: 응급 감지 → (아니면) 컨텍스트 조회 → RAG 검색 → LLM 스트리밍 → 대화 저장.
`docs/dev/sample_code_chat/app/services/chat_service.py`의 검증된 흐름을 실제
SQLAlchemy(AsyncSession) 기반으로 옮긴 것 — 흐름 구조 자체는 동일하다.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import cast

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.llm_stub import stream_llm_reply

logger = logging.getLogger("app.chat_service")

LlmStream = Callable[[str, dict, list[str]], AsyncIterator[str]]

_AI_WORKER_ERRORS = (AIWorkerUnavailableError, AIWorkerProcessingError, AIWorkerInvalidRequestError)


class EmergencyClassification(BaseModel):
    is_emergency: bool


class MedicalRelatednessClassification(BaseModel):
    is_medical_related: bool


_EMERGENCY_SYSTEM_PROMPT = (
    "당신은 사용자 메시지 하나를 보고 즉각적인 생명 위협 응급 상황(예: 의식 소실, 심정지, "
    "자살/자해 의도, 심한 호흡곤란, 심한 흉통, 발작/경련 등)을 나타내는지 판단하는 안전 분류기입니다.\n"
    "조금이라도 응급 상황일 가능성이 있으면 true로 판단하세요(과다 판정이 과소 판정보다 안전합니다).\n"
    "일상적인 건강 질문, 만성질환 관리, 가벼운 불편감은 false입니다.\n"
    'JSON 형식으로만 답하세요: {"is_emergency": true} 또는 {"is_emergency": false}'
)

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
        llm_stream: LlmStream | None = None,
        dur_drug_repository: DurDrugRepository | None = None,
        profile_repository: ProfileRepository | None = None,
        medication_repository: MedicationRepository | None = None,
    ) -> None:
        self._repository = repository or ChatRepository()
        self._chat_context_service = chat_context_service or ChatContextService()
        self._retriever = retriever or AIWorkerGateway()
        self._llm_stream = llm_stream or stream_llm_reply
        self._dur_drug_repository = dur_drug_repository or DurDrugRepository()
        self._profile_repository = profile_repository or ProfileRepository()
        self._medication_repository = medication_repository or MedicationRepository()

    async def create_session(self, session: AsyncSession, profile_id: int):
        return await self._repository.create_session(session, profile_id)

    async def stream_reply(
        self, session: AsyncSession, profile_id: int, session_id: int, message: str
    ) -> AsyncIterator[dict]:
        """
        응급 키워드가 감지되면 LLM을 호출하지 않고 고정 fallback만 반환한다(T-LLM-1 원칙).
        이 경우 대화 기록도 저장하지 않는다.

        키워드 판정과 별개로 LLM 기반 응급 판정을 히스토리/컨텍스트/RAG 조회와 병렬로 미리
        발사해두고, 실제 생성 직전에만 결과를 확인한다 — 매 턴 직렬 지연시간을 늘리지 않기
        위함이며, 응급으로 판명되면 그 전에 조회한 RAG/컨텍스트는 버려진다(트래픽이 적은
        지금은 이 비용보다 지연시간 감소가 더 중요하다는 판단).

        T-LLM-7-3: 질환 논문 검색(`/agent/paper-search`)도 같은 이유로 병렬 발사한다.
        그 결과 `sources`가 비어 있으면(질문이 논문 검색 범위 밖이라고 ai_worker가 이미
        판단한 것) 기존 DUR RAG 흐름으로 그대로 폴백하고, 있으면 그 답변+출처를 한 번에
        반환한다(paper_agent가 이미 자체 LLM으로 답변까지 만들어주므로, DUR 흐름처럼
        토큰 스트리밍하지 않고 emergency_fallback과 같은 단일 청크로 전달한다).
        """
        keyword_emergency = safety_service.check_emergency(message)
        emergency_llm_task = asyncio.create_task(self._check_emergency_via_llm(message))
        paper_task = asyncio.create_task(self._try_paper_agent(message))

        history = await self._repository.list_messages(session, session_id)

        # profile은 이 턴에서 한 번만 조회하고, 그 결과로 컨텍스트/DUR 게이팅을 전부 파생시킨다.
        profile = await self._profile_repository.get_profile(session, profile_id)
        medications = (
            await self._medication_repository.list_schedules_by_profile(session, profile_id) if profile else []
        )
        context = self._chat_context_service.build(profile, medications)

        context["history"] = [{"role": m.role, "content": m.content} for m in history]

        chunks = await self._search_chunks(message)
        content_chunks = [chunk.get("content", "") for chunk in chunks]
        sources = sorted(
            {
                chunk["metadata"]["source"]
                for chunk in chunks
                if chunk.get("metadata") and chunk["metadata"].get("source")
            }
        )

        dur_warnings = self._collect_dur_warnings(
            context["medications"], context["is_pregnant"], context["is_geriatric"]
        )

        if dur_warnings:
            for warning in dur_warnings:
                content_chunks.insert(0, f"[DUR 안전 경고 정보] 복용 약물 중 위험 경고 발견: {warning}")
            if "식약처 DUR 안전 정보" not in sources:
                sources.append("식약처 DUR 안전 정보")
            sources = sorted(sources)

        if keyword_emergency or await emergency_llm_task:
            paper_task.cancel()
            yield {
                "type": "emergency_fallback",
                "content": safety_service.EMERGENCY_FALLBACK_MESSAGE,
                "disclaimer": safety_service.DISCLAIMER_TEXT,
            }
            return

        paper_result = await paper_task
        if paper_result and paper_result["sources"]:
            paper_answer = paper_result["answer"]
            paper_sources = paper_result["sources"]
            yield {"type": "paper_answer", "content": paper_answer, "sources": paper_sources}

            source_label = ", ".join(s["name"] for s in paper_sources)
            await self._repository.save_message(session, session_id, MessageRole.USER, message)
            await self._repository.save_message(
                session, session_id, MessageRole.ASSISTANT, f"{paper_answer}\n\n[출처: {source_label}]"
            )

            is_medical = await self._check_if_medical_related_via_llm(message, paper_answer)
            yield {"type": "done", "content": "", "disclaimer": safety_service.DISCLAIMER_TEXT if is_medical else ""}
            return

        full_response = ""
        async for token in self._llm_stream(message, context, content_chunks):
            full_response += token
            yield {"type": "token", "content": token}

        # RAG 메타데이터 출처가 존재할 경우, 답변 끝에 출처를 합성하여 노출하고 데이터베이스에도 함께 기록합니다.
        if sources:
            source_text = f"\n\n[출처: {', '.join(sources)}]"
            full_response += source_text
            yield {"type": "token", "content": source_text}

        await self._repository.save_message(session, session_id, MessageRole.USER, message)
        await self._repository.save_message(session, session_id, MessageRole.ASSISTANT, full_response)

        # LLM 판정 및 기존 키워드 폴백 적용
        is_medical = await self._check_if_medical_related_via_llm(message, full_response)

        yield {"type": "done", "content": "", "disclaimer": safety_service.DISCLAIMER_TEXT if is_medical else ""}

    async def _try_paper_agent(self, message: str) -> dict | None:
        """`/agent/paper-search`를 매 턴 미리 발사해두고, 응급 판정과 마찬가지로 실제
        사용 직전(`stream_reply`)에만 결과를 확인한다. ai_worker 쪽 `classify_query()`가
        이미 "논문 검색 대상 질문인지"를 결정론적으로 판단하므로 여기서 다시 분류하지
        않는다 — `sources`가 비어 있으면 범위 밖이라는 뜻이라 호출자가 일반 흐름으로
        폴백한다. 장애 시에도 전체 채팅을 막지 않도록 None을 반환해 같은 폴백을 태운다."""
        try:
            return await self._retriever.ask_paper_agent(message)
        except _AI_WORKER_ERRORS as e:
            logger.error(f"논문 검색 에이전트 실패, 일반 답변 흐름으로 폴백: {e}")
            return None

    async def _search_chunks(self, message: str) -> list[dict]:
        """ai_worker 검색 실패는 조용히 삼키지 않고 로깅 후 빈 컨텍스트로 계속 진행한다
        (`AIWorkerGateway`가 실패를 예외로 알리므로, 그 예외를 여기서만 흡수한다)."""
        try:
            return await self._retriever.search(message)
        except (AIWorkerUnavailableError, AIWorkerProcessingError) as e:
            logger.error(f"ai_worker 검색 실패, 컨텍스트 없이 계속 진행: {e}")
            return []

    def _collect_dur_warnings(self, meds: list[dict], is_pregnant: bool, is_geriatric: bool) -> list[str]:
        if not ((is_pregnant or is_geriatric) and meds):
            return []

        dur_warnings: list[str] = []
        for med in meds:
            med_name = med.get("name", "")
            dur_warnings.extend(
                self._dur_drug_repository.find_dur_warnings(med_name, pregnant=is_pregnant, geriatric=is_geriatric)
            )
        return list(set(dur_warnings))

    async def _check_emergency_via_llm(self, message: str) -> bool:
        """ai_worker 장애 시 키워드 판정만으로 게이팅하도록 False를 반환한다(fail-safe —
        전체 채팅을 막지는 않되 키워드 레이어는 그대로 유지)."""
        try:
            result = await self._retriever.call_structured(
                system_prompt=_EMERGENCY_SYSTEM_PROMPT,
                user_input=message,
                schema=EmergencyClassification,
            )
        except _AI_WORKER_ERRORS as e:
            logger.error(f"응급 LLM 분류 실패, 키워드 판정만으로 게이팅: {e}")
            return False
        return cast(EmergencyClassification, result).is_emergency

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
