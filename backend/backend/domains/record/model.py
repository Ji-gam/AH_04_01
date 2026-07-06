# backend/domains/record/model.py
# API_Specification_v3.pdf [M5] MEDICAL_RECORDS, RECORD_MEDICATION_MAPPING
import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Date, JSON, Numeric
from sqlalchemy.orm import relationship
from backend.core.database import Base


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(20), nullable=True)  # PRESCRIPTION / BAG
    hospital_name = Column(String(100), nullable=True)
    pharmacy_name = Column(String(100), nullable=True)
    department_name = Column(String(50), nullable=True)
    diagnosis_name = Column(String(150), nullable=True)
    diagnosis_code = Column(String(20), nullable=True)
    visit_date = Column(Date, nullable=True)

    # [v3 변경] ocr_raw_text(TEXT) -> ocr_raw_json + image_s3_url 분리
    # MySQL에서는 JSONB가 아닌 일반 JSON 타입으로 대체합니다 (PostgreSQL 도입 전까지).
    image_s3_url = Column(String(500), nullable=True)
    ocr_raw_json = Column(JSON, nullable=True)

    receipt_amount = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="medical_records")
    medications = relationship("RecordMedicationMapping", back_populates="record", cascade="all, delete-orphan")
    generated_guides = relationship("GeneratedGuide", back_populates="record")
    schedules = relationship("MedicationSchedule", back_populates="record")


class RecordMedicationMapping(Base):
    __tablename__ = "record_medication_mapping"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id = Column(Integer, ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)

    dosage_per_take = Column(String(30), nullable=True)  # 예: "10클릭", "1정"
    takes_per_day = Column(Integer, nullable=True)
    duration_days = Column(Integer, nullable=True)
    instruction = Column(String(255), nullable=True)
    device_type = Column(String(30), nullable=True)  # MULTI_DOSE_PEN / SINGLE_USE_PEN / TABLET
    total_clicks_or_doses = Column(Integer, nullable=True)
    total_prescribed_quantity = Column(Integer, nullable=True)
    remaining_quantity = Column(Integer, nullable=True)

    record = relationship("MedicalRecord", back_populates="medications")
    medication = relationship("Medication", back_populates="mappings")


# OCR 비동기 처리 결과를 임시로 보관하는 테이블 (실제 워커/큐 없이 동기 처리를 흉내내기 위한 최소 구조)
class OcrTask(Base):
    __tablename__ = "ocr_tasks"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String(50), unique=True, nullable=False)
    status = Column(String(20), default="PROCESSING")  # PROCESSING / SUCCESS / FAILED
    record_id = Column(Integer, ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True)
    image_s3_url = Column(String(500), nullable=True)
    ocr_raw_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
