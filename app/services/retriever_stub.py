"""
RAG Retriever / Context Binder — 실제 소유는 `ai_worker/`이지만, AI/RAG 워커
통신 방식이 아직 미정이라(`docs/decision_log.md` 미결사항) 통신 프로토콜이
확정될 때까지 Tier 2 stub으로 `app/services/`에 둔다.
"""

import logging

import httpx

from app.core import config

logger = logging.getLogger("app.retriever")


class Retriever:
    def __init__(self) -> None:
        self.endpoint = config.AI_WORKER_RETRIEVE_URL

    async def search(self, query: str, context: dict) -> list[dict]:
        """
        ai-worker 서비스의 /retrieve API를 비동기 호출하여 유사 의약품 안전 정보(본문 및 메타데이터)를 가져옵니다.
        """
        payload = {"query": query, "limit": 3}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.endpoint, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("chunks", [])
                else:
                    logger.error(f"ai-worker retrieve API failed (status: {response.status_code}): {response.text}")
        except Exception as e:
            logger.error(f"Failed to communicate with RAG ai-worker: {e}")

        # 오류 발생 시 빈 리스트 반환하여 기능이 완전히 뻗지 않도록 방어
        return []
