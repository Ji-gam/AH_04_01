from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatSessionCreateResponse(BaseModel):
    session_id: str = Field(description="생성된 채팅 세션 ID", examples=["1"])


class ChatMessageRequest(BaseModel):
    message: str = Field(description="사용자가 입력한 자연어 질문", examples=["두통약 뭐가 좋아요?"])


class ChatSessionResponse(BaseModel):
    id: int = Field(description="채팅 세션 ID", examples=[1])
    created_at: datetime = Field(description="세션 생성 시각")
    updated_at: datetime = Field(description="마지막 메시지가 저장된 시각 (목록 정렬 기준)")


class ChatSourceRef(BaseModel):
    name: str = Field(description="출처 이름 (DUR 문서명 또는 논문 제목)")
    url: str | None = Field(default=None, description="논문 링크. DUR 출처는 항상 null")


class ChatMessageResponse(BaseModel):
    id: int = Field(description="메시지 ID. 어시스턴트 답변에 피드백(👍/👎)을 붙일 때 이 값을 쓴다.", examples=[1])
    role: str = Field(description="발화자 (user 또는 assistant)", examples=["user"])
    content: str = Field(description="발화 내용", examples=["두통약 뭐가 좋아요?"])
    sources: list[ChatSourceRef] | None = Field(
        default=None, description="답변 생성에 쓰인 DUR/논문 출처 목록. user 메시지는 항상 null"
    )
    disclaimer: str | None = Field(default=None, description="의료 관련 답변에만 붙는 면책 문구. 없으면 null")
    created_at: datetime = Field(description="메시지 생성 시각")


class ChatFeedbackRequest(BaseModel):
    value: Literal["up", "down"] = Field(description="피드백 값", examples=["up"])
    comment: str | None = Field(default=None, description="자유 서술 코멘트(선택)")
