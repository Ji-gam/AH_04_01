from pydantic import BaseModel


class DocumentChunk(BaseModel):
    content: str
    metadata: dict
    # T-ADMIN-1: 검색 시 계산된 유사도 거리(낮을수록 유사). 답변 생성 프롬프트에는 안 쓰이고
    # SourceRef.score로 그대로 전달되어 관리자 모니터링 화면에서만 노출된다.
    score: float | None = None


class SourceRef(BaseModel):
    """답변 생성에 쓰인 자료 1건의 출처 각주. DUR은 url이 없고(name만), 논문은 PubMed
    URL이 있다 — url이 없는 소스도 있을 수 있어 optional로 둔다. 프론트엔드는 url이
    있으면 [바로가기] 버튼을, 없으면 name만 표시한다."""

    name: str
    url: str | None = None
    # T-ADMIN-1: RAG 유사도 거리(낮을수록 유사). 관리자 모니터링 전용 - 환자용 UI는 렌더링 안 함.
    score: float | None = None


class ChatCompletionRequest(BaseModel):
    """T-LLM-7-3-2: 통합 RAG 스트리밍 채팅 요청. DUR/논문 검색과 최종 답변 생성을
    이 하나의 요청으로 전부 처리한다(기존 /retrieve, /agent/paper-search를 대체).
    개인화 컨텍스트(진단병력/복약정보 등)와 개인 DUR 경고(SQL 조회 기반이라 ai_worker가
    직접 계산 못 함)는 호출자(app/)가 만들어서 넘긴다."""

    message: str
    context: dict
    history: list[dict]
    injected_context: list[str] = []
