from pydantic import BaseModel, Field


class ChatSessionCreateResponse(BaseModel):
    session_id: str = Field(description="생성된 채팅 세션 ID", examples=["1"])


class ChatMessageRequest(BaseModel):
    message: str = Field(description="사용자가 입력한 자연어 질문", examples=["두통약 뭐가 좋아요?"])
