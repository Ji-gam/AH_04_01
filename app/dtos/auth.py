from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.validators import validate_birthday, validate_password, validate_phone_number
from app.models.profiles import Gender


class SignUpRequest(BaseModel):
    email: Annotated[
        EmailStr,
        Field(description="로그인 아이디로 쓰이는 이메일. 중복 시 409를 반환한다.", max_length=40, examples=["test@example.com"]),
    ]
    password: Annotated[
        str,
        Field(description="대/소문자, 숫자, 특수문자를 각 1개 이상 포함, 8자 이상.", min_length=8, examples=["Password123!"]),
        AfterValidator(validate_password),
    ]
    name: Annotated[str, Field(description="본인 Profile의 이름으로 저장된다.", max_length=20, examples=["홍길동"])]
    gender: Annotated[Gender, Field(description="'MALE' 또는 'FEMALE'.")]
    birth_date: Annotated[
        date, Field(description="YYYY-MM-DD. 만 14세 미만은 가입할 수 없다.", examples=["1995-05-05"]), AfterValidator(validate_birthday)
    ]
    phone_number: Annotated[
        str,
        Field(description="010-1234-5678 / 01012345678 / +821012345678 형식 모두 허용. 중복 시 409를 반환한다.", examples=["01012345678"]),
        AfterValidator(validate_phone_number),
    ]


class LoginRequest(BaseModel):
    email: Annotated[EmailStr, Field(examples=["test@example.com"])]
    password: Annotated[str, Field(min_length=8, examples=["Password123!"])]


class LoginResponse(BaseModel):
    access_token: Annotated[
        str,
        Field(description="Authorization: Bearer 헤더에 담아 보낸다. Refresh Token은 이 응답이 아니라 httpOnly 쿠키로 내려간다."),
    ]


class TokenRefreshResponse(LoginResponse): ...
