"""
T-LLM-2-drug-gateway: `DurDrugRepository.drug_data()`가 외부 e약은요 API에서 얻은
결과를 캐싱하는 테이블. `query_name`(요청받은 약품명 그대로, trim만)을 키로 삼아
"동일 조회 시 캐시 히트"를 가장 단순하게 보장한다. API가 빈/무의미한 응답을 준
경우는 여기에 저장하지 않는다 — 나중에 API에 데이터가 채워질 수 있으므로 매 요청마다
재시도한다(음성 캐싱 금지).
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DrugDataCache(Base):
    __tablename__ = "drug_data_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    profiles: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
