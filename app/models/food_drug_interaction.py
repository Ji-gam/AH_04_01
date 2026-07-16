"""(T-DOC-3/4 후속, 2026-07-16) 음식-약물 상호작용 참조 테이블을 SQLite(`app/database/
food_drug_interaction.db`)에서 MySQL로 이전한 테이블. 각자 로컬 파일을 따로 갖지 않고
팀 전체가 공유하는 MySQL에서 조회하도록 통일한다(멘토 피드백).

원문 소스(`food_drug_interaction_reference.json`)와 빌드 스크립트
(`app/scripts/build_food_drug_interaction_db.py`)는 그대로 유지 — 그 스크립트가 만드는
SQLite 파일을 `app/scripts/seed_food_drug_interaction.py`가 읽어 이 테이블에 시딩한다.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FoodDrugPolarity(StrEnum):
    AVOID = "avoid"
    RECOMMEND = "recommend"
    TIMING_CAUTION = "timing_caution"


class FoodDrugSource(Base):
    """출처 메타데이터 단일 행(식약처 「약과 음식 상호작용을 피하는 복약안내서」)."""

    __tablename__ = "food_drug_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published: Mapped[str | None] = mapped_column(String(50), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    not_covered: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FoodDrugCategory(Base):
    __tablename__ = "food_drug_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(200), nullable=False)
    drug_class: Mapped[str] = mapped_column(String(200), nullable=False)
    food_interaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    alcohol_interaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[str | None] = mapped_column(String(50), nullable=True)

    ingredients: Mapped[list["FoodDrugIngredient"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )
    food_items: Mapped[list["FoodDrugFoodItem"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class FoodDrugIngredient(Base):
    __tablename__ = "food_drug_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_drug_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_ko: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    category: Mapped[FoodDrugCategory] = relationship(back_populates="ingredients")


class FoodDrugFoodItem(Base):
    __tablename__ = "food_drug_food_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("food_drug_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food_name: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    polarity: Mapped[FoodDrugPolarity] = mapped_column(
        SAEnum(FoodDrugPolarity, native_enum=False, length=20, values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
        default=FoodDrugPolarity.AVOID,
        server_default=FoodDrugPolarity.AVOID.value,
    )

    category: Mapped[FoodDrugCategory] = relationship(back_populates="food_items")
