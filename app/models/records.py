from typing import Any

from tortoise import fields, models

from app.models.medications import Medication
from app.models.users import User


class MedicalRecord(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="medical_records", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    document_type = fields.CharField(max_length=20, null=True)  # PRESCRIPTION / BAG
    hospital_name = fields.CharField(max_length=100, null=True)
    pharmacy_name = fields.CharField(max_length=100, null=True)
    department_name = fields.CharField(max_length=50, null=True)
    diagnosis_name = fields.CharField(max_length=150, null=True)
    diagnosis_code = fields.CharField(max_length=20, null=True)
    visit_date = fields.DateField(null=True)
    image_s3_url = fields.CharField(max_length=500, null=True)
    ocr_raw_json: Any = fields.JSONField(null=True)
    receipt_amount = fields.IntField(null=True)
    uploaded_at = fields.DatetimeField(auto_now_add=True)

    medications: fields.ReverseRelation["RecordMedicationMapping"]

    class Meta:
        table = "medical_records"


class RecordMedicationMapping(models.Model):
    id = fields.IntField(pk=True)
    record: MedicalRecord = fields.ForeignKeyField(
        "models.MedicalRecord", related_name="medications", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    record_id: int
    medication: Medication = fields.ForeignKeyField(
        "models.Medication", related_name="mappings", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    medication_id: int
    dosage_per_take = fields.CharField(max_length=30, null=True)  # 예: "10클릭", "1정"
    takes_per_day = fields.IntField(null=True)
    duration_days = fields.IntField(null=True)
    instruction = fields.CharField(max_length=255, null=True)
    device_type = fields.CharField(max_length=30, null=True)  # MULTI_DOSE_PEN / SINGLE_USE_PEN / TABLET
    total_clicks_or_doses = fields.IntField(null=True)
    total_prescribed_quantity = fields.IntField(null=True)
    remaining_quantity = fields.IntField(null=True)

    class Meta:
        table = "record_medication_mapping"


class OcrTask(models.Model):
    id = fields.IntField(pk=True)
    task_id = fields.CharField(max_length=50, unique=True)
    status = fields.CharField(max_length=20, default="PROCESSING")  # PROCESSING / SUCCESS / FAILED
    record: MedicalRecord | None = fields.ForeignKeyField(
        "models.MedicalRecord", related_name="ocr_tasks", on_delete=fields.SET_NULL, null=True
    )  # type: ignore[assignment]
    record_id: int | None
    image_s3_url = fields.CharField(max_length=500, null=True)
    ocr_raw_json: Any = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "ocr_tasks"
