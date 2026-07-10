from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.validators import validate_password


class SignUpRequest(BaseModel):
    """[가입 최소화] 나중에 소셜 로그인을 붙일 걸 감안해서, 가입 시점엔 최소한의 정보만 받는다.
    성별/나이/휴대폰번호는 여기서 안 받고, 더보기 > 개인건강정보에서 따로 입력받는다."""

    email: Annotated[
        EmailStr,
        Field(
            description="로그인 아이디로 쓰이는 이메일. 중복 시 409를 반환한다.",
            max_length=40,
            examples=["test@example.com"],
        ),
    ]
    password: Annotated[
        str,
        Field(
            description="소문자, 숫자, 특수문자를 각 1개 이상 포함, 8자 이상.",
            min_length=8,
            examples=["password123!"],
        ),
        AfterValidator(validate_password),
    ]
    name: Annotated[
        str, Field(description="닉네임. 본인 Profile의 이름으로 저장된다.", max_length=20, examples=["길동이"])
    ]


class LoginRequest(BaseModel):
    email: Annotated[EmailStr, Field(examples=["test@example.com"])]
    password: Annotated[str, Field(min_length=8, examples=["Password123!"])]


class WithdrawRequest(BaseModel):
    """회원탈퇴 - 탈취된 토큰만으로 탈퇴되는 것을 막기 위해 현재 비밀번호 재확인을 요구한다."""

    password: Annotated[str, Field(min_length=8, description="본인 확인용 현재 비밀번호.", examples=["Password123!"])]


class LoginResponse(BaseModel):
    access_token: Annotated[
        str,
        Field(
            description="Authorization: Bearer 헤더에 담아 보낸다. Refresh Token은 이 응답이 아니라 httpOnly 쿠키로 내려간다."
        ),
    ]


class TokenRefreshResponse(LoginResponse): ...
