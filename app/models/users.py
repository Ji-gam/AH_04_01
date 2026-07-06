from enum import StrEnum

from tortoise import fields, models


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class User(models.Model):
    id = fields.BigIntField(primary_key=True)
    email = fields.CharField(max_length=40)
    hashed_password = fields.CharField(max_length=128)
    name = fields.CharField(max_length=20)
    gender = fields.CharEnumField(enum_type=Gender)
    birthday = fields.DateField()
    phone_number = fields.CharField(max_length=11)
    is_active = fields.BooleanField(default=True)
    is_admin = fields.BooleanField(default=False)
    # [핀포인트 추가] 소셜 로그인(구글/네이버/카카오) 지원을 위한 필드
    sns_provider = fields.CharField(max_length=20, default="LOCAL")
    sns_id = fields.CharField(max_length=255, null=True)
    last_login = fields.DatetimeField(null=True)
    # [핀포인트 추가] Refresh Token 회전/로그아웃 무효화를 위해 DB에도 현재 유효한 refresh_token을 저장합니다.
    # 쿠키의 값과 여기 저장된 값이 일치할 때만 갱신을 허용합니다 (탈취된 옛날 토큰 재사용 방지).
    refresh_token = fields.CharField(max_length=512, null=True)
    # [핀포인트 추가] 필수 약관에 동의한 시각. 언제 동의했는지 증빙용으로 남깁니다.
    # 소셜 로그인 가입자는 지금 당장은 null입니다 (소셜 가입 화면에 아직 동의 절차가 없음).
    agreed_terms_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
