from pydantic import BaseModel


class RetrieveRequest(BaseModel):
    query: str
    limit: int = 3


class DocumentChunk(BaseModel):
    content: str
    metadata: dict


class RetrieveResponse(BaseModel):
    chunks: list[DocumentChunk]


class PaperAgentRequest(BaseModel):
    question: str


class PaperSourceRef(BaseModel):
    """답변 생성에 쓰인 논문 1건의 출처 각주. url이 없는 소스가 나중에 추가될 수 있어
    optional로 둔다 — 프론트엔드는 url이 있으면 [바로가기] 버튼을, 없으면 name만 표시한다."""

    name: str
    url: str | None = None


class PaperAgentResponse(BaseModel):
    answer: str
    sources: list[PaperSourceRef]
