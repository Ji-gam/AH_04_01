"""
RAG Retriever / Context Binder — 실제 소유는 `ai_worker/`이지만, AI/RAG 워커
통신 방식이 아직 미정이라(`docs/decision_log.md` 미결사항) 통신 프로토콜이
확정될 때까지 Tier 2 stub으로 `app/services/`에 둔다.
"""


class Retriever:
    def search(self, query: str, context: dict) -> list[str]:
        return []
