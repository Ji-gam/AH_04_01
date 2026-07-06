from tortoise import fields, models

from app.models.medications import Medication


class DrugFoodInteraction(models.Model):
    id = fields.IntField(pk=True)
    medication: Medication = fields.ForeignKeyField(
        "models.Medication", related_name="interactions", on_delete=fields.CASCADE
    )  # type: ignore[assignment]
    medication_id: int
    substance_name = fields.CharField(max_length=100)
    risk_level = fields.CharField(max_length=20, default="INFO")  # INFO / WARNING / DANGER
    guidance_text = fields.TextField(null=True)

    class Meta:
        table = "drug_food_interactions"
