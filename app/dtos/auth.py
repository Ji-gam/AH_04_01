from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field, field_validator

from app.core.validators import validate_birthday, validate_password, validate_phone_number
from app.models.profiles import Gender


class AgreementRequest(BaseModel):
    """[T-AUTH-7] 개인정보보호법 제23조(민감정보는 다른 개인정보 처리 동의와 "별도"로 받아야 함)를
    반영해 항목을 분리했다. service_terms/privacy/sensitive_info는 필수, marketing은 선택이다."""

    service_terms: Annotated[bool, Field(description="[필수] 서비스 이용약관 동의")]
    privacy: Annotated[bool, Field(description="[필수] 개인정보 수집이용 동의")]
    sensitive_info: Annotated[
        bool,
        Field(description="[필수] 민감정보(진단병력/가족력 등 건강정보) 수집이용 동의 - 일반 개인정보 동의와 별도"),
    ]
    marketing: Annotated[bool, Field(False, description="[선택] 마케팅 정보 수신 동의")]

    @field_validator("service_terms", "privacy", "sensitive_info")
    @classmethod
    def _required_agreements_must_be_true(cls, value: bool, info) -> bool:
        if not value:
            raise ValueError(f"필수 항목({info.field_name})에 동의해야 가입을 진행할 수 있습니다.")
        return value


class SignUpRequest(BaseModel):
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
            description="대/소문자, 숫자, 특수문자를 각 1개 이상 포함, 8자 이상.",
            min_length=8,
            examples=["Password123!"],
        ),
        AfterValidator(validate_password),
    ]
    name: Annotated[str, Field(description="본인 Profile의 이름으로 저장된다.", max_length=20, examples=["홍길동"])]
    gender: Annotated[Gender, Field(description="'MALE' 또는 'FEMALE'.")]
    birth_date: Annotated[
        date,
        Field(description="YYYY-MM-DD. 만 14세 미만은 가입할 수 없다.", examples=["1995-05-05"]),
        AfterValidator(validate_birthday),
    ]
    phone_number: Annotated[
        str,
        Field(
            description="010-1234-5678 / 01012345678 / +821012345678 형식 모두 허용. 중복 시 409를 반환한다.",
            examples=["01012345678"],
        ),
        AfterValidator(validate_phone_number),
    ]
    agreements: Annotated[AgreementRequest, Field(description="약관/개인정보/민감정보 동의 항목")]


class LoginRequest(BaseModel):
    email: Annotated[EmailStr, Field(examples=["test@example.com"])]
    password: Annotated[str, Field(min_length=8, examples=["Password123!"])]


class LoginResponse(BaseModel):
    access_token: Annotated[
        str,
        Field(
            description="Authorization: Bearer 헤더에 담아 보낸다. Refresh Token은 이 응답이 아니라 httpOnly 쿠키로 내려간다."
        ),
    ]
    profile_id: Annotated[
        int,
        Field(description="본인(SELF) Profile의 ID. 도메인 API 호출 시 이 값 기준으로 데이터를 조회/기록한다."),
    ]

class TokenRefreshResponse(LoginResponse): ...


class PendingSocialSignupResponse(BaseModel):
    """[T-AUTH-7] 프론트가 리다이렉트 쿼리스트링으로 이 값들을 받는다(백엔드가 직접 JSON으로
    내려주진 않음 - 리다이렉트라서). 신규 가입자에게는 이 값들이 있고, 기존 사용자는 바로
    로그인 처리되어 이 값들 없이 FRONTEND_URL로만 리다이렉트된다."""

    pending_token: Annotated[str, Field(description="10분간 유효. complete-signup 호출 시 그대로 실어 보낸다.")]
    provider: Annotated[str, Field(description="google | naver | kakao")]
    email: Annotated[str | None, Field(description="제공자가 준 이메일. 없을 수 있다.")]
    name: Annotated[str | None, Field(description="제공자가 준 이름/닉네임. 없을 수 있다.")]


class SocialSignupCompleteRequest(BaseModel):
    """[T-AUTH-7] '약관 동의 + 정보 입력' 화면에서 '가입 완료'를 누르면 호출한다.
    소셜 제공자는 이름/이메일만 주므로, 성별/생년월일/휴대폰번호는 이 화면에서 직접 입력받는다.
    이 시점에 비로소 User+Profile이 실제로 생성된다(=개인정보 "수집" 시점)."""

    pending_token: Annotated[str, Field(description="콜백에서 받은 값 그대로.")]
    name: Annotated[str, Field(description="소셜에서 받은 값을 기본으로 보여주되, 사용자가 수정 가능.", max_length=20)]
    gender: Annotated[Gender, Field(description="'MALE' 또는 'FEMALE'. 소셜에서 안 주므로 직접 입력.")]
    birth_date: Annotated[
        date,
        Field(description="YYYY-MM-DD. 소셜에서 안 주므로 직접 입력. 만 14세 미만은 가입할 수 없다."),
        AfterValidator(validate_birthday),
    ]
    phone_number: Annotated[
        str, Field(description="소셜에서 안 주므로 직접 입력."), AfterValidator(validate_phone_number)
    ]
    agreements: Annotated[AgreementRequest, Field(description="약관/개인정보/민감정보 동의 항목")]


class WithdrawRequest(BaseModel):
    """[T-AUTH-8 회원탈퇴] LOCAL 가입자는 비밀번호 재확인이 필수다(탈취된 Access Token만으로
    탈퇴되는 것을 막기 위함). 소셜 가입자는 비밀번호 자체가 없으므로 생략 가능하다."""

    password: Annotated[str | None, Field(None, description="LOCAL 계정만 필요. 소셜 계정은 비워도 된다.")]
