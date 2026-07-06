from tortoise import fields, models

from app.models.users import User


class FoodIntakeLog(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="food_intake_logs", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    meal_time_type = fields.CharField(max_length=20, null=True)  # BREAKFAST/LUNCH/DINNER/SNACK
    food_name = fields.CharField(max_length=200)
    image_url = fields.CharField(max_length=500, null=True)
    key_nutrients = fields.CharField(max_length=200, null=True)
    calories = fields.FloatField(null=True)
    sugar_content = fields.FloatField(null=True)
    recorded_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "food_intake_logs"
