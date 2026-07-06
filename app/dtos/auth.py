from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.models.users import Gender
from app.core.validators import validate_birthday, validate_password, validate_phone_number


def _validate_agreed_terms(value: bool) -> bool:
    if not value:
        raise ValueError("필수 약관에 동의해야 회원가입을 진행할 수 있습니다.")
    return value


class SignUpRequest(BaseModel):
    email: Annotated[
        EmailStr,
        Field(None, max_length=40),
    ]
    password: Annotated[str, Field(min_length=8), AfterValidator(validate_password)]
    name: Annotated[str, Field(max_length=20)]
    gender: Gender
    birth_date: Annotated[date, AfterValidator(validate_birthday)]
    phone_number: Annotated[str, AfterValidator(validate_phone_number)]
    # [핀포인트 추가] 프론트에서 필수 약관 체크박스를 전부 체크해야 True로 전송됩니다.
    # False(또는 누락)면 422로 거부됩니다 - 실제 저장은 서비스 단에서 시각으로 기록합니다.
    agreed_terms: Annotated[bool, AfterValidator(_validate_agreed_terms)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=8)]


class LoginResponse(BaseModel):
    access_token: str


class TokenRefreshResponse(LoginResponse): ...
