from tortoise import fields, models

from app.models.medications import Medication
from app.models.records import MedicalRecord
from app.models.users import User


class MedicationSchedule(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="medication_schedules", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    medication: Medication = fields.ForeignKeyField(
        "models.Medication", related_name="schedules", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    medication_id: int
    record: MedicalRecord | None = fields.ForeignKeyField(
        "models.MedicalRecord", related_name="schedules", on_delete=fields.SET_NULL, null=True
    )  # type: ignore[assignment]
    record_id: int | None

    card_alias = fields.CharField(max_length=100, null=True)  # 예: "다이어트 삭센다 주사"
    frequency_type = fields.CharField(max_length=10, default="DAILY")  # DAILY / WEEKLY
    target_day_of_week = fields.CharField(max_length=10, null=True)  # WEEKLY일 때만: 월/화/.../금 등
    alarm_time = fields.TimeField()
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "medication_schedules"
