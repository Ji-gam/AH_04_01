import datetime
from typing import Any

from app.dtos.base import BaseSerializerModel


class MedicationMappingCreate(BaseSerializerModel):
    medication_id: int
    dosage_per_take: str | None = None
    takes_per_day: int | None = None
    duration_days: int | None = None
    instruction: str | None = None
    device_type: str | None = None
    total_clicks_or_doses: int | None = None
    total_prescribed_quantity: int | None = None


class RecordCreate(BaseSerializerModel):
    document_type: str = "PRESCRIPTION"
    hospital_name: str | None = None
    pharmacy_name: str | None = None
    department_name: str | None = None
    diagnosis_name: str | None = None
    diagnosis_code: str | None = None
    visit_date: datetime.date | None = None
    image_s3_url: str | None = None
    receipt_amount: int | None = None
    medications: list[MedicationMappingCreate] = []


class RecordCreateResponse(BaseSerializerModel):
    id: int
    user_id: int
    document_type: str | None = None
    visit_date: datetime.date | None = None
    diagnosis_name: str | None = None
    uploaded_at: datetime.datetime


class MedicationMappingResponse(BaseSerializerModel):
    id: int
    medication_id: int
    medication_name: str
    dosage_per_take: str | None = None
    takes_per_day: int | None = None
    duration_days: int | None = None
    instruction: str | None = None
    device_type: str | None = None
    total_clicks_or_doses: int | None = None
    total_prescribed_quantity: int | None = None
    remaining_quantity: int | None = None


class RecordDetailResponse(BaseSerializerModel):
    id: int
    document_type: str | None = None
    hospital_name: str | None = None
    pharmacy_name: str | None = None
    diagnosis_name: str | None = None
    diagnosis_code: str | None = None
    visit_date: datetime.date | None = None
    receipt_amount: int | None = None
    medications: list[MedicationMappingResponse] = []


class OcrTaskAccepted(BaseSerializerModel):
    task_id: str
    status: str
    created_at: datetime.datetime


class OcrTaskStatus(BaseSerializerModel):
    task_id: str
    status: str
    record_id: int | None = None
    image_s3_url: str | None = None
    ocr_raw_json: Any | None = None
