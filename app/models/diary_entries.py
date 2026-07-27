from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DiaryEntry(Base):
    """마이다이어리 > "오늘의 한 줄" - 하루에 한 건, 다시 저장하면 그날 기록을 덮어쓴다
    (weekly_reports.py와 달리 이건 AI가 아니라 사용자가 직접 쓰는 글이라 수정 가능해야 함).
    (profile_id, entry_date) 유니크 제약으로 하루 한 건만 남는다.

    `image_base64`는 사진 첨부 1장(선택) - 이 프로젝트에 파일을 디스크/오브젝트 스토리지에
    저장하고 다시 서빙하는 기존 인프라가 없어서(복약 사진 인식도 업로드된 이미지를 CLOVA
    OCR에 바로 넘기고 저장은 안 함), 가장 간단하게 base64로 DB에 직접 저장한다. 프론트에서
    업로드 전 캔버스로 리사이즈/압축해서 보내므로 실제 크기는 크지 않다. 일반 `Text`(MySQL
    64KB 한도)로는 사진 하나도 넘칠 수 있어 `LONGTEXT`를 쓴다."""

    __tablename__ = "diary_entries"
    __table_args__ = (UniqueConstraint("profile_id", "entry_date", name="uq_diary_entries_profile_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_base64: Mapped[str | None] = mapped_column(LONGTEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
