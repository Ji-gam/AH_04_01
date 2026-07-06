from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class User(models.Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=100, unique=True, index=True)
    hashed_password = fields.CharField(max_length=128, null=True)
    name = fields.CharField(max_length=50)
    role_type = fields.CharField(max_length=20, default="PATIENT")  # PATIENT / GUARDIAN
    gender = fields.CharField(max_length=10, null=True)
    birth_date = fields.CharField(max_length=20, null=True)
    phone_number = fields.CharField(max_length=11, null=True)
    sns_provider = fields.CharField(max_length=20, default="LOCAL")  # LOCAL / GOOGLE
    sns_id = fields.CharField(max_length=255, null=True)
    refresh_token = fields.CharField(max_length=500, null=True)

    # 노인 접근성 개인화 설정
    use_voice_mode = fields.BooleanField(default=False)
    use_large_font = fields.BooleanField(default=False)
    wake_time = fields.TimeField(null=True)
    breakfast_time = fields.TimeField(null=True)
    lunch_time = fields.TimeField(null=True)
    dinner_time = fields.TimeField(null=True)
    bed_time = fields.TimeField(null=True)

    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
