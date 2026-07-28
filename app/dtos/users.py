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
    is_admin: Annotated[
        bool,
        Field(False, description="관리자 여부 - 프론트에서 관리자 메뉴 노출 여부에만 씀(실제 권한검증은 서버가 함)."),
    ]
    # (2026-07-28) 가입 시 통합 동의 화면 게이트(RequireAuth)가 매 페이지 이동마다 다시
    # 물어볼 필요 없이 이 응답 하나로 판단할 수 있게 여기 포함시킨다.
    health_info_consented_at: Annotated[datetime | None, Field(None, description="개인건강정보 동의 시각.")]
    ai_chat_consented_at: Annotated[datetime | None, Field(None, description="AI 챗봇 데이터 활용 동의 시각.")]
    terms_of_service_consented_at: Annotated[datetime | None, Field(None, description="이용약관 동의 시각.")]
    marketing_consented_at: Annotated[datetime | None, Field(None, description="마케팅 정보 수신 동의 시각(선택).")]
    # (2026-07-28) 소셜 가입자는 비밀번호가 없어서(hashed_password=None) 회원탈퇴 등에서
    # 비밀번호 입력란 자체를 안 보여줘야 한다 - 프론트가 이걸로 판단한다.
    has_password: Annotated[bool, Field(True, description="비밀번호 보유 여부. 소셜 가입자는 false.")]


class ConsentUpdateRequest(BaseModel):
    """[개인정보보호법 제23조 등] true로 보낸 항목만 그 시각으로 서버에 동의 시각이 남는다.
    false/미전달은 "아직 응답 안 함"으로 두고(기존 상태 유지) - 명시적으로 동의를 철회하는
    기능은 별도(회원탈퇴 등)로 다룬다.

    (2026-07-28) 가입 시 한 화면에서 한 번에 받는 통합 동의로 재설계함 - 이용약관/
    건강정보(민감정보 포함)/AI챗봇 데이터활용은 필수, 마케팅만 선택. 위치정보는 브라우저
    자체 geolocation 권한요청이 이미 다루고 있어 별도 항목을 안 둔다."""

    health_info: Annotated[bool, Field(False, description="개인건강정보(민감정보) 수집·이용 동의 여부. 필수.")]
    ai_chat: Annotated[bool, Field(False, description="AI 챗봇 대화 데이터 활용 동의 여부. 필수.")]
    terms_of_service: Annotated[bool, Field(False, description="이용약관 동의 여부. 필수.")]
    marketing: Annotated[bool, Field(False, description="마케팅 정보 수신 동의 여부. 선택.")]


class ConsentStatusResponse(BaseSerializerModel):
    health_info_consented_at: Annotated[datetime | None, Field(description="개인건강정보 동의 시각. 미동의 시 null.")]
    ai_chat_consented_at: Annotated[
        datetime | None, Field(description="AI 챗봇 데이터 활용 동의 시각. 미동의 시 null.")
    ]
    terms_of_service_consented_at: Annotated[datetime | None, Field(description="이용약관 동의 시각. 미동의 시 null.")]
    marketing_consented_at: Annotated[
        datetime | None, Field(description="마케팅 정보 수신 동의 시각(선택). 미동의 시 null.")
    ]
