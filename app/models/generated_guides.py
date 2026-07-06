from tortoise import fields, models

from app.models.records import MedicalRecord
from app.models.users import User


class GeneratedGuide(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="generated_guides", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    record: MedicalRecord | None = fields.ForeignKeyField(
        "models.MedicalRecord", related_name="generated_guides", on_delete=fields.SET_NULL, null=True
    )  # type: ignore[assignment]
    record_id: int | None
    guide_type = fields.CharField(max_length=30)  # MEDICATION 등
    content = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    title = fields.CharField(max_length=150, null=True)
    visual_card_path = fields.CharField(max_length=255, null=True)
    voice_audio_path = fields.CharField(max_length=255, null=True)

    class Meta:
        table = "generated_guides"
