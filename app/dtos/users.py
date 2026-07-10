from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.validators import optional_after_validator, validate_phone_number
from app.dtos.base import BaseSerializerModel
from app.models.profiles import Gender


class UserUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정). 전부 Profile에 반영된다.
    email은 로그인 식별자라 여기서 수정할 수 없다(가입 후 고정) - 이메일 인증 절차가 없는 상태에서
    검증 없이 바꾸면 계정을 잃어버릴 위험이 있어서, 실서비스 전환 시 이메일 인증 기능과 함께 재검토한다.
    [변경] 생년월일은 더 이상 안 쓴다 - 나이는 더보기 > 개인건강정보에서 관리한다."""

    name: Annotated[
        str | None, Field(None, description="Profile의 이름(닉네임)", min_length=2, max_length=20, examples=["길동이"])
    ]
    phone_number: Annotated[
        str | None,
        Field(None, description="Available Format: +8201011112222, 01011112222, 010-1111-2222"),
        optional_after_validator(validate_phone_number),
    ]
    gender: Annotated[
        Gender | None,
        Field(None, description="'MALE' or 'FEMALE'"),
    ]


class UserInfoResponse(BaseSerializerModel):
    id: Annotated[int, Field(description="User(계정)의 PK.")]
    profile_id: Annotated[
        int, Field(description="Profile(개인정보)의 PK. 앞으로 추가되는 도메인 API는 이 값을 기준으로 조회/저장한다.")
    ]
    name: Annotated[str, Field(description="Profile에 저장된 이름(닉네임).")]
    email: Annotated[str, Field(description="User(계정)의 로그인 이메일. 가입 후 변경 불가.")]
    phone_number: Annotated[str | None, Field(description="Profile에 저장된 휴대폰번호. 미입력 시 null.")]
    gender: Annotated[Gender | None, Field(description="Profile에 저장된 성별. 미입력 시 null.")]
    created_at: Annotated[datetime, Field(description="User(계정) 생성 시각.")]
