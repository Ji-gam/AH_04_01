from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class FeedbackValue(StrEnum):
    UP = "UP"
    DOWN = "DOWN"


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
    # T-LLM-2-langfuse-user-feedback: 어시스턴트 메시지에만 채워지고, Langfuse 미설정
    # 환경(로컬/CI)에서는 항상 null이다 — 사용자 피드백을 받을 때 이 값으로 Langfuse
    # trace를 찾아 점수를 붙인다(프론트에는 노출하지 않음, 설계 결정 1).
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessageFeedback(Base):
    """T-LLM-2-langfuse-user-feedback: 챗봇 답변에 대한 사용자 평가(👍/👎).
    `chat_messages`에 컬럼을 더하지 않고 별도 테이블로 둔다 — 대화 기록이라는 단일
    책임을 유지하고, 재평가 시각(updated_at)과 자유 서술 comment를 담기 좋다(설계 결정 2).
    message_id는 UNIQUE라 답변 하나당 피드백은 한 건 뿐이고, 다시 누르면 값을 갱신한다."""

    __tablename__ = "chat_message_feedbacks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_messages.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    value: Mapped[FeedbackValue] = mapped_column(SAEnum(FeedbackValue, native_enum=False, length=10), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
