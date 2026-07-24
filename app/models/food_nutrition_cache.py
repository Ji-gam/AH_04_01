"""
F-DIET-1: `DietService.search_food()`가 외부 식품영양성분DB API 호출 결과를 캐싱하는 테이블.
`app/models/drug_data_cache_model.py`와 같은 패턴 - `query_name`(검색어 그대로, trim만)을 키로
캐시 히트를 가장 단순하게 보장한다. 빈/무의미한 응답은 캐싱하지 않는다(음성 캐싱 금지 - 나중에
API/시드가 채워질 수 있으므로 매 요청마다 재시도).
"""

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FoodNutritionCache(Base):
    __tablename__ = "food_nutrition_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    query_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    results: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
