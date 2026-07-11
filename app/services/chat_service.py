"""
T-LLM-2: 응급 감지 → (아니면) 컨텍스트 조회 → RAG 검색 → LLM 스트리밍 → 대화 저장.
`docs/dev/sample_code_chat/app/services/chat_service.py`의 검증된 흐름을 실제
SQLAlchemy(AsyncSession) 기반으로 옮긴 것 — 흐름 구조 자체는 동일하다.
"""

import logging
from collections.abc import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import MessageRole
from app.repositories.chat_repository import ChatRepository
from app.repositories.dur_drug_repository import DurDrugRepository
from app.repositories.medication_repository import MedicationRepository
from app.repositories.profile_repository import ProfileRepository
from app.services import safety_service
from app.services.ai_worker_gateway import AIWorkerGateway, AIWorkerProcessingError, AIWorkerUnavailableError
from app.services.chat_context_service import ChatContextService
from app.services.llm_stub import stream_llm_reply

logger = logging.getLogger("app.chat_service")

LlmStream = Callable[[str, dict, list[str]], AsyncIterator[str]]


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
        """
        if safety_service.check_emergency(message):
            yield {
                "type": "emergency_fallback",
                "content": safety_service.EMERGENCY_FALLBACK_MESSAGE,
                "disclaimer": safety_service.DISCLAIMER_TEXT,
            }
            return

        history = await self._repository.list_messages(session, session_id)

        # profile은 이 턴에서 한 번만 조회하고, 그 결과로 컨텍스트/DUR 게이팅을 전부 파생시킨다.
        profile = await self._profile_repository.get_profile(session, profile_id)
        medications = (
            await self._medication_repository.list_schedules_by_profile(session, profile_id) if profile else []
        )
        context = self._chat_context_service.build(profile, medications)

        context["history"] = [{"role": m.role, "content": m.content} for m in history]

        chunks = await self._search_chunks(message, context)
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

    async def _search_chunks(self, message: str, context: dict) -> list[dict]:
        """ai_worker 검색 실패는 조용히 삼키지 않고 로깅 후 빈 컨텍스트로 계속 진행한다
        (`AIWorkerGateway`가 실패를 예외로 알리므로, 그 예외를 여기서만 흡수한다)."""
        try:
            return await self._retriever.search(message, context)
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

    async def _check_if_medical_related_via_llm(self, message: str, response: str) -> bool:
        import json
        import os

        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self._is_medical_related_fallback(message, response)

        try:
            client = AsyncOpenAI(api_key=api_key)
            chat_completion = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a clinical classification assistant. Your task is to analyze the conversation and "
                            "determine if the assistant's response contains any clinical advice, medical warnings, "
                            "drug safety warnings (DUR), disease diagnoses, drug interaction guidance, or physiological side effects. "
                            "If the response is purely about general nutrition, diet recipe recommendations, sports, scheduling, "
                            "general chat, or non-medical life choices, output false. "
                            'Return JSON format: {"is_medical_related": true} or {"is_medical_related": false}.'
                        ),
                    },
                    {"role": "user", "content": f"User: {message}\nAssistant: {response}"},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            result_text = chat_completion.choices[0].message.content
            if result_text:
                result_json = json.loads(result_text)
                return bool(result_json.get("is_medical_related", False))
        except Exception:
            pass

        return self._is_medical_related_fallback(message, response)

    def _is_medical_related_fallback(self, message: str, response: str) -> bool:
        medical_keywords = [
            "약",
            "복용",
            "약물",
            "부작용",
            "처방",
            "dur",
            "치료",
            "복약",
            "먹어",
            "먹는",
            "정제",
            "알약",
            "콘서타",
            "디아제팜",
            "메트포르민",
            "암로디핀",
            "아스피린",
            "타이레놀",
            "졸피뎀",
            "병",
            "질환",
            "의사",
            "진단",
            "당뇨",
            "고혈압",
            "임신",
            "임산부",
            "노인",
            "고령",
            "증상",
            "의료",
            "병원",
            "진료",
            "의학",
        ]
        text_to_check = (message + " " + response).lower()
        return any(kw in text_to_check for kw in medical_keywords)
