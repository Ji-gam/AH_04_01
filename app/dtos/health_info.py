from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, computed_field

from app.core.validators import optional_after_validator, validate_height_cm, validate_weight_kg
from app.dtos.base import BaseSerializerModel
from app.models.profiles import Disease, Gender


class HealthInfoUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정). 전부 선택 입력 - 회원가입과 무관하게 언제든 입력/수정 가능.
    생년월일/성별은 여기서 수정하지 않는다 - 이미 확정된 개인정보라 계정 정보 수정(PATCH /users/me)에서만 바꾼다.
    이 화면에서는 조회만 되도록 HealthInfoResponse에만 노출한다."""

    height_cm: Annotated[
        float | None,
        Field(None, description="키(cm). 30~250 범위.", examples=[170.5]),
        optional_after_validator(validate_height_cm),
    ]
    weight_kg: Annotated[
        float | None,
        Field(None, description="체중(kg). 2~300 범위.", examples=[65.2]),
        optional_after_validator(validate_weight_kg),
    ]
    diagnosis_history: Annotated[
        list[Disease] | None,
        Field(None, description="본인이 진단받은 5대질환 목록. 빈 리스트를 보내면 전부 지워진다."),
    ]
    family_history: Annotated[
        list[Disease] | None,
        Field(None, description="직계가족의 5대질환 병력 목록. 빈 리스트를 보내면 전부 지워진다."),
    ]
    special_notes: Annotated[
        str | None, Field(None, description="특이사항 (알레르기, 복용 중인 약 등)", max_length=1000)
    ]
    other_notes: Annotated[str | None, Field(None, description="기타 자유 입력", max_length=1000)]


class HealthInfoResponse(BaseSerializerModel):
    birthday: Annotated[date, Field(description="Profile에 저장된 생년월일.")]
    gender: Annotated[Gender, Field(description="Profile에 저장된 성별.")]
    height_cm: Annotated[float | None, Field(description="키(cm). 미입력 시 null.")]
    weight_kg: Annotated[float | None, Field(description="체중(kg). 미입력 시 null.")]
    diagnosis_history: Annotated[list[Disease], Field(description="본인이 진단받은 5대질환 목록.")]
    family_history: Annotated[list[Disease], Field(description="직계가족의 5대질환 병력 목록.")]
    special_notes: Annotated[str | None, Field(description="특이사항.")]
    other_notes: Annotated[str | None, Field(description="기타.")]

    @computed_field(description="키/체중으로 계산한 체질량지수. 둘 중 하나라도 없으면 null.")  # type: ignore[prop-decorator]
    @property
    def bmi(self) -> float | None:
        if self.height_cm is None or self.weight_kg is None:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m**2), 1)
