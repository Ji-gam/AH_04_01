from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from app.core.validators import optional_after_validator, validate_birthday, validate_phone_number
from app.dtos.base import BaseSerializerModel
from app.models.profiles import Disease, Gender


class UserUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정). name/phone_number/birthday/gender는 Profile에, email은 User에 반영된다."""

    name: Annotated[
        str | None, Field(None, description="Profile의 이름", min_length=2, max_length=20, examples=["홍길동"])
    ]
    email: Annotated[
        EmailStr | None,
        Field(
            None,
            description="변경할 이메일. 다른 계정이 이미 쓰고 있으면 409를 반환한다.",
            max_length=40,
            examples=["new@example.com"],
        ),
    ]
    phone_number: Annotated[
        str | None,
        Field(None, description="Available Format: +8201011112222, 01011112222, 010-1111-2222"),
        optional_after_validator(validate_phone_number),
    ]
    birthday: Annotated[
        date | None,
        Field(None, description="Date Format: YYYY-MM-DD"),
        optional_after_validator(validate_birthday),
    ]
    gender: Annotated[
        Gender | None,
        Field(None, description="'MALE' or 'FEMALE'"),
    ]


class BiometricInfoRequest(BaseModel):
    """[T-PROFILE-1] 회원가입 직후 별도 화면에서 입력받는 생체정보. 전달한 필드만 갱신한다(부분 수정).
    diagnosis_history/family_history에 빈 리스트([])를 명시적으로 보내면 "해당 없음"으로 저장된다
    (필드 자체를 아예 안 보내면 기존 값을 그대로 둔다)."""

    height_cm: Annotated[float | None, Field(None, gt=0, le=250, description="키(cm)", examples=[170.5])]
    weight_kg: Annotated[float | None, Field(None, gt=0, le=300, description="체중(kg)", examples=[65.2])]
    diagnosis_history: Annotated[
        list[Disease] | None, Field(None, description="본인이 진단받은 5대질환 목록. 없으면 빈 리스트.")
    ]
    family_history: Annotated[
        list[Disease] | None, Field(None, description="가족(직계) 5대질환 병력 목록. 없으면 빈 리스트.")
    ]
    health_notes: Annotated[
        str | None,
        Field(None, max_length=1000, description="'기타' 탭 자유 메모(복용 중인 영양제, 알레르기, 특이사항 등)."),
    ]


class UserInfoResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="User(계정)의 PK.")]
    profile_id: Annotated[
        int, Field(description="Profile(개인정보)의 PK. 앞으로 추가되는 도메인 API는 이 값을 기준으로 조회/저장한다.")
    ]
    name: Annotated[str, Field(description="Profile에 저장된 이름.")]
    email: Annotated[str, Field(description="User(계정)의 로그인 이메일.")]
    phone_number: Annotated[str, Field(description="Profile에 저장된 휴대폰번호.")]
    birthday: Annotated[date, Field(description="Profile에 저장된 생년월일.")]
    gender: Annotated[Gender, Field(description="Profile에 저장된 성별.")]
    height_cm: Annotated[float | None, Field(description="키(cm). 아직 입력 전이면 null.")]
    weight_kg: Annotated[float | None, Field(description="체중(kg). 아직 입력 전이면 null.")]
    diagnosis_history: Annotated[list[Disease], Field(description="본인 진단병력(5대질환). 없으면 빈 리스트.")]
    family_history: Annotated[list[Disease], Field(description="가족력(5대질환). 없으면 빈 리스트.")]
    health_notes: Annotated[str | None, Field(description="'기타' 탭 자유 메모. 없으면 null.")]
    created_at: Annotated[datetime, Field(description="User(계정) 생성 시각.")]
