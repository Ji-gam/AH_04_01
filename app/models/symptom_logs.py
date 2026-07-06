from tortoise import fields, models

from app.models.users import User


class SymptomLog(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="symptom_logs", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    symptom_notes = fields.TextField()
    severity_level = fields.IntField(default=1)  # 1~5 단계
    recorded_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "symptom_logs"
