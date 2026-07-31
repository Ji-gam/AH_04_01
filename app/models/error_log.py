from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ErrorLog(Base):
    """앱 전체(챗봇 제외 - 그쪽은 이미 파일 로그로 별도 처리 중) API에서 안 잡힌 예외가
    나면 main.py의 전역 예외 핸들러가 여기 기록한다. 전체 트레이스백/요청 바디는 민감정보
    유출 위험이 있어 저장하지 않고, 예외 타입 + 잘라낸 메시지 + 경로만 남긴다."""

    __tablename__ = "error_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
