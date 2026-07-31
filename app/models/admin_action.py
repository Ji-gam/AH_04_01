from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminAction(Base):
    """관리자 화면에서 이뤄진 행위(권한 승격/강등, 공지 발송 등)의 감사로그.

    관리자 권한은 공용 가입코드 같은 새 공개 경로 없이 "기존 관리자가 화면에서
    다른 사용자를 승격"하는 방식으로만 늘어나므로(2026-07-27 설계), "누가 언제
    누구를 관리자로 지정했는지" / "누가 언제 어떤 공지를 보냈는지"가 이 테이블
    말고는 남는 곳이 없다 - 감사 추적용으로 반드시 필요."""

    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # 예: "grant_admin", "revoke_admin", "create_notice"
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # 액션 종류에 따라 대상 user_id, notice_id 등 - 범용적으로 문자열로만 남긴다.
    target: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
