# backend/domains/generated_guide/model.py
# API_Specification_v3.pdf [M10] GENERATED_GUIDES
# [v3 참고사항] 명세서 v7 테이블에는 title/visual_cards/voice_audio_url 컬럼이 없다고 나와있지만,
# PRD/TRD에서 카드뉴스·TTS 기능을 요구하고 있어 우선 컬럼은 남겨뒀습니다 (nullable).
# 팀에서 이 필드들을 계속 쓸지 정식 논의 후 확정해주세요.
import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class GeneratedGuide(Base):
    __tablename__ = "generated_guides"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    record_id = Column(Integer, ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True)
    guide_type = Column(String(30), nullable=False)  # MEDICATION 등
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # [확인 필요 - v3 스키마 미반영 상태] 아래 3개는 PRD/TRD 요구사항 반영을 위해 임시로 남겨둔 컬럼입니다.
    title = Column(String(150), nullable=True)
    visual_card_path = Column(String(255), nullable=True)
    voice_audio_path = Column(String(255), nullable=True)

    user = relationship("User", back_populates="generated_guides")
    record = relationship("MedicalRecord", back_populates="generated_guides")
