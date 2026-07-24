from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ChatSession(Base):
    """T-LLM-2: 챗봇 대화 세션. profile_id 기준으로 스코핑한다(CODING_RULES.md 2-1번)."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    """세션 내 대화 기록. 응급 Fallback 메시지는 저장하지 않는다(app/services/chat_service.py 참고)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, native_enum=False, length=10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # T-LLM-7-3-2: 통합 RAG 스트리밍이 답변마다 함께 보내는 DUR/논문 출처 목록. 어시스턴트
    # 메시지에만 채워지고(사용자 메시지는 항상 null), 과거 대화를 다시 불러올 때도 출처
    # 칩을 그대로 복원하기 위해 저장한다(스트림 중에만 존재하던 값이라 이전엔 소실됐음).
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 의료 관련 답변에만 붙는 면책 문구(safety_service.DISCLAIMER_TEXT). sources와 같은
    # 이유로 저장한다 — 스트림 종료 시 "done" 청크에만 실려 왔던 값이라 과거엔 소실됐음.
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
