from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PushSendLog(Base):
    """복약 알림 스케줄러가 (알림 종류, 알림 id, 날짜, 시각) 단위로 "이미 보냈다"를 기록해두는
    테이블. APScheduler가 uvicorn 워커 개수만큼 프로세스별로 따로 도는 구조라(push_scheduler.py
    docstring 참고) 같은 1분 틱에 여러 워커가 동시에 같은 알림을 보내려 할 수 있는데, 이 테이블의
    유니크 제약을 "선착순 클레임"으로 써서 한 워커만 실제 발송하고 나머지는 중복 삽입 시
    IntegrityError로 걸러 건너뛴다."""

    __tablename__ = "push_send_logs"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "source_id", "sent_date", "sent_time", name="uq_push_send_logs_source_date_time"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sent_date: Mapped[date] = mapped_column(Date, nullable=False)
    sent_time: Mapped[str] = mapped_column(String(5), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
