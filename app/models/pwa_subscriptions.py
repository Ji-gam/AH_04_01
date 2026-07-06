from tortoise import fields, models

from app.models.users import User


class PwaSubscription(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="pwa_subscriptions", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    endpoint_url = fields.CharField(max_length=500, unique=True)
    p256dh_key = fields.CharField(max_length=255)
    auth_key = fields.CharField(max_length=255)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "pwa_subscriptions"
