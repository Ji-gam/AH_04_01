from tortoise import fields, models

from app.models.users import User


class EmergencyCard(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.OneToOneField("models.User", related_name="emergency_card", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    blood_type = fields.CharField(max_length=5, null=True)
    food_allergies = fields.TextField(null=True)
    medication_allergies = fields.TextField(null=True)
    past_history = fields.TextField(null=True)
    present_history = fields.TextField(null=True)
    family_history = fields.TextField(null=True)
    emergency_contacts = fields.TextField(null=True)

    class Meta:
        table = "emergency_cards"
