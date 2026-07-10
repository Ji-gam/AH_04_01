from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreateResponse(BaseModel):
    session_id: str = Field(description="생성된 채팅 세션 ID", examples=["1"])


class ChatMessageRequest(BaseModel):
    message: str = Field(description="사용자가 입력한 자연어 질문", examples=["두통약 뭐가 좋아요?"])


class ChatSessionResponse(BaseModel):
    id: int = Field(description="채팅 세션 ID", examples=[1])
    created_at: datetime = Field(description="세션 생성 시각")


class ChatMessageResponse(BaseModel):
    role: str = Field(description="발화자 (user 또는 assistant)", examples=["user"])
    content: str = Field(description="발화 내용", examples=["두통약 뭐가 좋아요?"])
    created_at: datetime = Field(description="메시지 생성 시각")
