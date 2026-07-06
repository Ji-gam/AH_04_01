from tortoise import fields, models

from app.models.schedules import MedicationSchedule


class IntakeLog(models.Model):
    id = fields.IntField(pk=True)
    schedule: MedicationSchedule = fields.ForeignKeyField(
        "models.MedicationSchedule", related_name="intake_logs", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    schedule_id: int
    planned_date = fields.DateField()
    actual_take_time = fields.DatetimeField(null=True)
    status = fields.CharField(max_length=20, default="MISSED")  # COMPLETED / MISSED
    verification_media_url = fields.CharField(max_length=500, null=True)

    class Meta:
        table = "intake_logs"
