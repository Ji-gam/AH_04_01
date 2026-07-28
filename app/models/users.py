from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.profiles import Profile


class User(Base):
    """계정/인증 전용. 이름/성별/나이/휴대폰번호 등 개인정보는 Profile로 분리되어 있다."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("sns_provider", "sns_id", name="uq_users_sns_provider_sns_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    # 소셜 로그인 계정은 비밀번호가 없다(본인이 정한 적 없음) - 이메일 가입자만 값이 있다.
    hashed_password: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 로컬(이메일) 가입자는 둘 다 None. 소셜 가입자는 "google"/"kakao"/"naver" + 그 서비스의 사용자 고유 ID.
    sns_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sns_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # [로그인 시도 제한] 브루트포스 방어 - 연속 실패 시 일정 시간 잠근다(app/services/auth.py 참고).
    # 로그인 성공하면 둘 다 초기화된다.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # [개인정보보호법 제23조] 지금까지는 이 동의를 프론트(localStorage)에만 기록해서 서버엔
    # "언제 동의했는지" 근거가 안 남았다 - 여기 서버 DB에도 시각을 남긴다. null이면 미동의.
    health_info_consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # (2026-07-28) 회원가입 화면에서 한 번에 받는 나머지 3종. 위치정보는 브라우저 자체
    # geolocation 권한요청이 이미 그 역할을 해서 별도 항목을 안 둔다.
    ai_chat_consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_of_service_consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    marketing_consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profiles: Mapped[list["Profile"]] = relationship(back_populates="user", cascade="all, delete-orphan")
