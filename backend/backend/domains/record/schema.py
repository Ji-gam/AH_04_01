# backend/domains/record/schema.py
import datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class MedicationMappingCreate(BaseModel):
    medication_id: int
    dosage_per_take: Optional[str] = None
    takes_per_day: Optional[int] = None
    duration_days: Optional[int] = None
    instruction: Optional[str] = None
    device_type: Optional[str] = None
    total_clicks_or_doses: Optional[int] = None
    total_prescribed_quantity: Optional[int] = None


class RecordCreate(BaseModel):
    document_type: str = "PRESCRIPTION"
    hospital_name: Optional[str] = None
    pharmacy_name: Optional[str] = None
    department_name: Optional[str] = None
    diagnosis_name: Optional[str] = None
    diagnosis_code: Optional[str] = None
    visit_date: Optional[datetime.date] = None
    image_s3_url: Optional[str] = None
    receipt_amount: Optional[int] = None
    medications: List[MedicationMappingCreate] = []


class RecordCreateResponse(BaseModel):
    record_id: int
    user_id: int
    document_type: Optional[str] = None
    visit_date: Optional[datetime.date] = None
    diagnosis_name: Optional[str] = None
    uploaded_at: datetime.datetime


class MedicationMappingResponse(BaseModel):
    mapping_id: int
    medication_id: int
    medication_name: str
    dosage_per_take: Optional[str] = None
    takes_per_day: Optional[int] = None
    duration_days: Optional[int] = None
    instruction: Optional[str] = None
    device_type: Optional[str] = None
    total_clicks_or_doses: Optional[int] = None
    total_prescribed_quantity: Optional[int] = None
    remaining_quantity: Optional[int] = None


class RecordDetailResponse(BaseModel):
    record_id: int
    document_type: Optional[str] = None
    hospital_name: Optional[str] = None
    pharmacy_name: Optional[str] = None
    diagnosis_name: Optional[str] = None
    diagnosis_code: Optional[str] = None
    visit_date: Optional[datetime.date] = None
    receipt_amount: Optional[int] = None
    medications: List[MedicationMappingResponse] = []


class OcrTaskAccepted(BaseModel):
    task_id: str
    status: str
    created_at: datetime.datetime


class OcrTaskStatus(BaseModel):
    task_id: str
    status: str
    record_id: Optional[int] = None
    image_s3_url: Optional[str] = None
    ocr_raw_json: Optional[Any] = None
