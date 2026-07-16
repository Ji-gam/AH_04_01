"""
T-LLM-2-async-gateway: `ai_worker`(RAG+생성/구조화 생성)와 Celery(비동기 작업)를 향한 단일 창구.

프롬프트 문구/응답 스키마는 호출하는 도메인이 소유한다 — 이 Gateway는 그것을 대신
정의하지 않는다(`docs/decision_log/2026-07-10-ai-rag-worker.md` 참고).

T-LLM-7-3-2: DUR 전용 검색(`/retrieve`)과 논문 전용 검색+답변(`/agent/paper-search`)을
호출하던 `search()`/`ask_paper_agent()`는 삭제됐다. 두 파이프라인이 하나의 통합 RAG
스트리밍 엔드포인트(`/agent/chat`)로 합쳐지면서 `stream_chat()`으로 대체됐다 —
DUR+논문 검색과 LLM 생성을 ai_worker가 전부 처리하고 토큰을 스트리밍으로 돌려준다.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx
from pydantic import BaseModel

from app.core import config

logger = logging.getLogger("app.ai_worker_gateway")


class AIWorkerUnavailableError(Exception):
    """업스트림(ai_worker) 무응답/타임아웃, 또는 생성 불가 상태(예: API 키 미설정)."""


class AIWorkerInvalidRequestError(Exception):
    """잘못된 호출(422 등)."""


class AIWorkerProcessingError(Exception):
    """응답은 왔으나 형식이 예상과 다름."""


class AIWorkerGateway:
    def __init__(
        self,
        base_url: str | None = None,
        generate_timeout: float | None = None,
    ) -> None:
        self._base_url = base_url or config.AI_WORKER_BASE_URL
        self._generate_timeout = generate_timeout if generate_timeout is not None else config.AI_WORKER_GENERATE_TIMEOUT

    async def stream_chat(
        self, message: str, context: dict, history: list[dict], injected_context: list[str]
    ) -> AsyncIterator[dict]:
        """`ai_worker`의 통합 RAG 스트리밍 엔드포인트(`/agent/chat`)를 호출한다. DUR+논문
        검색과 답변 생성을 ai_worker가 전부 처리하고, 이 메서드는 그 스트림을 한 줄씩
        파싱해 그대로 전달한다({"type": "sources"|"token"|"error", ...}).

        스트림이 이미 시작된 뒤의 실패(예: OpenAI 쪽 오류)는 HTTP 상태 코드로 알릴 수
        없어 인밴드 {"type": "error", ...} 청크로 오므로, 그건 예외가 아니라 그대로
        yield한다 — 호출자가 타입을 보고 "받은 만큼만 저장" 처리한다. 반면 연결 자체가
        끊기거나(네트워크 문제) 응답을 아예 파싱할 수 없으면 예외로 알린다."""
        payload = {"message": message, "context": context, "history": history, "injected_context": injected_context}
        try:
            async with (
                httpx.AsyncClient(timeout=self._generate_timeout) as client,
                client.stream("POST", f"{self._base_url}/agent/chat", json=payload) as response,
            ):
                if response.status_code == 503:
                    body = await response.aread()
                    raise AIWorkerUnavailableError(f"ai_worker 채팅 불가: {body.decode()}")
                if response.status_code == 422:
                    body = await response.aread()
                    raise AIWorkerInvalidRequestError(f"잘못된 채팅 요청: {body.decode()}")
                if response.status_code != 200:
                    body = await response.aread()
                    raise AIWorkerUnavailableError(
                        f"ai_worker 채팅 실패(status={response.status_code}): {body.decode()}"
                    )

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        yield json.loads(line)
                    except ValueError as e:
                        raise AIWorkerProcessingError(f"채팅 스트림 응답 파싱 실패: {e}") from e
        except httpx.HTTPError as e:
            raise AIWorkerUnavailableError(f"ai_worker 채팅 스트림 요청 실패: {e}") from e

    async def call_structured(self, system_prompt: str, user_input: str, schema: type[BaseModel]) -> BaseModel:
        """`ai_worker`의 `/generate-structured`를 호출해 `schema`를 만족하는 응답을 받아
        검증한다. 프롬프트 문구와 스키마 정의는 호출하는 도메인의 책임이다."""
        payload = {
            "system_prompt": system_prompt,
            "user_input": user_input,
            "json_schema": schema.model_json_schema(),
        }
        try:
            async with httpx.AsyncClient(timeout=self._generate_timeout) as client:
                response = await client.post(f"{self._base_url}/generate-structured", json=payload)
        except httpx.HTTPError as e:
            raise AIWorkerUnavailableError(f"ai_worker 생성 요청 실패: {e}") from e

        if response.status_code == 503:
            raise AIWorkerUnavailableError(f"ai_worker 생성 불가: {response.text}")
        if response.status_code == 422:
            raise AIWorkerInvalidRequestError(f"잘못된 생성 요청: {response.text}")
        if response.status_code != 200:
            raise AIWorkerUnavailableError(f"ai_worker 생성 실패(status={response.status_code}): {response.text}")

        try:
            data = response.json()["data"]
            return schema.model_validate(data)
        except (KeyError, ValueError) as e:
            raise AIWorkerProcessingError(f"생성 응답 형식 이상: {e}") from e

    def enqueue(self, task_name: str, payload: dict) -> str:
        """Celery(+Redis)로 비동기 작업을 등록하고 즉시 리턴한다. 결과는 태스크가 직접
        DB에 저장하며, 별도 상태조회/폴링 API는 두지 않는다."""
        from app.core.celery_app import celery_app

        result = celery_app.send_task(task_name, kwargs=payload)
        return result.id
