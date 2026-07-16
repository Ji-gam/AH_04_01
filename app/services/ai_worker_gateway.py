"""
T-LLM-2-async-gateway: `ai_worker`(검색/구조화 생성)와 Celery(비동기 작업)를 향한 단일 창구.

프롬프트 문구/응답 스키마는 호출하는 도메인이 소유한다 — 이 Gateway는 그것을 대신
정의하지 않는다(`docs/decision_log/2026-07-10-ai-rag-worker.md` 참고).
"""

import logging

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
        retrieve_timeout: float | None = None,
        generate_timeout: float | None = None,
    ) -> None:
        self._base_url = base_url or config.AI_WORKER_BASE_URL
        # 검색과 생성은 응답 특성이 달라 타임아웃을 분리한다(생성은 LLM이라 훨씬 김).
        self._retrieve_timeout = retrieve_timeout if retrieve_timeout is not None else config.AI_WORKER_RETRIEVE_TIMEOUT
        self._generate_timeout = generate_timeout if generate_timeout is not None else config.AI_WORKER_GENERATE_TIMEOUT

    async def search(self, query: str) -> list[dict]:
        """`ai_worker`의 `/retrieve`를 동기 HTTP로 호출한다. 실패는 조용히 삼키지 않고
        예외로 알린다 — 빈 결과(정상, 매칭 0건)와 실패(예외)를 명확히 구분한다."""
        try:
            async with httpx.AsyncClient(timeout=self._retrieve_timeout) as client:
                response = await client.post(f"{self._base_url}/retrieve", json={"query": query, "limit": 3})
        except httpx.HTTPError as e:
            raise AIWorkerUnavailableError(f"ai_worker 검색 요청 실패: {e}") from e

        if response.status_code == 422:
            raise AIWorkerInvalidRequestError(f"잘못된 검색 요청: {response.text}")
        if response.status_code != 200:
            raise AIWorkerUnavailableError(f"ai_worker 검색 실패(status={response.status_code}): {response.text}")

        try:
            return response.json()["chunks"]
        except (KeyError, ValueError) as e:
            raise AIWorkerProcessingError(f"검색 응답 형식 이상: {e}") from e

    async def ask_paper_agent(self, question: str) -> dict:
        """`ai_worker`의 `/agent/paper-search`(T-LLM-7-3)를 호출한다. 질환 논문 벡터
        검색+답변을 한 번에 반환하며, `sources`(제목+URL 목록)가 비어 있으면 그 질문이
        논문 검색 범위 밖이라는 뜻이다 — 호출자가 그 경우 일반 답변 흐름으로 폴백한다."""
        try:
            async with httpx.AsyncClient(timeout=self._generate_timeout) as client:
                response = await client.post(f"{self._base_url}/agent/paper-search", json={"question": question})
        except httpx.HTTPError as e:
            raise AIWorkerUnavailableError(f"ai_worker 논문 검색 요청 실패: {e}") from e

        if response.status_code == 503:
            raise AIWorkerUnavailableError(f"ai_worker 논문 검색 불가: {response.text}")
        if response.status_code == 422:
            raise AIWorkerInvalidRequestError(f"잘못된 논문 검색 요청: {response.text}")
        if response.status_code != 200:
            raise AIWorkerUnavailableError(f"ai_worker 논문 검색 실패(status={response.status_code}): {response.text}")

        try:
            data = response.json()
            return {"answer": data["answer"], "sources": data["sources"]}
        except (KeyError, ValueError) as e:
            raise AIWorkerProcessingError(f"논문 검색 응답 형식 이상: {e}") from e

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
