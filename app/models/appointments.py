from tortoise import fields, models

from app.models.users import User


class Appointment(models.Model):
    id = fields.IntField(pk=True)
    user: User = fields.ForeignKeyField("models.User", related_name="appointments", on_delete=fields.CASCADE)  # type: ignore[assignment]
    user_id: int
    hospital_name = fields.CharField(max_length=100)
    doctor_name = fields.CharField(max_length=50, null=True)
    doctor_contact = fields.CharField(max_length=30, null=True)
    appointment_at = fields.DatetimeField()
    memo = fields.TextField(null=True)

    class Meta:
        table = "hospital_appointments"
