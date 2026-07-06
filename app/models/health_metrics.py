from tortoise import fields, models

from app.models.users import User


class HealthMetric(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="health_metrics", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    weight = fields.FloatField(null=True)
    height = fields.FloatField(null=True)
    blood_pressure_systolic = fields.IntField(null=True)
    blood_pressure_diastolic = fields.IntField(null=True)
    blood_glucose = fields.IntField(null=True)
    source = fields.CharField(max_length=10, default="MANUAL")  # MANUAL
    recorded_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "health_metrics"
