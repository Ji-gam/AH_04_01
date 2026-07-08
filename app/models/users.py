from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.profiles import Profile


class User(Base):
    """계정/인증 전용. 이름/성별/생일/휴대폰번호 등 개인정보는 Profile로 분리되어 있다."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # [소셜로그인 추가] 로컬 가입 계정은 sns_provider="LOCAL", sns_id=None.
    sns_provider: Mapped[str] = mapped_column(String(20), default="LOCAL", nullable=False)
    sns_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # [T-AUTH-3 로그아웃] 현재 유효한 refresh_token. 로그아웃 시 여기를 null로 비워서
    # 브라우저에 남아있는 쿠키가 더 이상 재발급에 쓰이지 못하게 만든다.
    refresh_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # [T-AUTH-7 동의이력] 개인정보보호법 제23조(민감정보는 다른 동의와 "별도"로 받아야 함)를
    # 반영해 각각을 독립된 시각으로 기록한다. null이면 아직 동의 전(가입 미완료) 상태다.
    service_terms_agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    privacy_agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sensitive_info_agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marketing_agreed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profiles: Mapped[list["Profile"]] = relationship(back_populates="user", cascade="all, delete-orphan")
