"""
Retriever 데모 — 실제로는 `ai_worker/sync_api.py`의 POST /retrieve를 호출하는 자리다
(decision_log.md "AI/RAG 워커 분리 원칙" 참고. AI/RAG 추론은 이 백엔드 프로세스에 두지 않는다).

⚠ RAG(서현) 완성 전까지는 이 stub을 그대로 쓴다.
RAG 완성 후 교체 방법 (ChatService 내부만 바뀌고 Router/DTO는 그대로):

    chunks = Retriever().search(message, context)
    ↓ 이렇게 교체
    resp = httpx.post(f"{settings.AI_WORKER_SYNC_URL}/retrieve", json={"query": message, "profile_id": profile_id})
    chunks = resp.json()["chunks"]
"""


class Retriever:
    def search(self, query: str, context: dict) -> list[str]:
        return [f"[stub-chunk] '{query}' 관련 문서를 아직 찾을 수 없습니다 (RAG 연동 전)."]
