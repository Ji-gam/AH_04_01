# backend/domains/medication/model.py
# API_Specification_v3.pdf [M5] MEDICATIONS (의약품 마스터)
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from backend.core.database import Base


class Medication(Base):
    __tablename__ = "medications"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    standard_code = Column(String(50), nullable=True)
    medication_name = Column(String(150), nullable=False)
    form_type = Column(String(30), nullable=True)  # TABLET / INJECTION 등
    dosage_guideline = Column(Text, nullable=True)
    side_effects = Column(Text, nullable=True)
    precautions = Column(Text, nullable=True)
    storage_method = Column(Text, nullable=True)

    # [보류 - pgvector] shape/color/letters(외형 검색용), embedding(VECTOR(512))은
    # PostgreSQL + pgvector 확장 도입 결정 전까지 스키마에 반영하지 않았습니다.
    # 알약 이미지 검색 API(search-by-image)는 이 컬럼들이 생기기 전까지 스텁으로만 존재합니다.
    shape = Column(String(30), nullable=True)
    color = Column(String(30), nullable=True)
    letters = Column(String(50), nullable=True)

    mappings = relationship("RecordMedicationMapping", back_populates="medication", cascade="all, delete-orphan")
    schedules = relationship("MedicationSchedule", back_populates="medication", cascade="all, delete-orphan")
    interactions = relationship("DrugFoodInteraction", back_populates="medication", cascade="all, delete-orphan")
