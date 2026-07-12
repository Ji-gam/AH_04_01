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


class PaperAgentResponse(BaseModel):
    answer: str
