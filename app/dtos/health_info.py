from typing import Annotated

from pydantic import BaseModel, Field, computed_field

from app.core.validators import optional_after_validator, validate_height_cm, validate_weight_kg
from app.dtos.base import BaseSerializerModel
from app.models.profiles import Disease, Gender


class DiseaseEntry(BaseModel):
    """진단병력/가족력의 항목 하나. detail은 선택 입력 - 체크만 하고 상세는 안 적어도 된다."""

    disease: Annotated[Disease, Field(description="5대질환 중 하나 또는 'OTHER'(기타).")]
    detail: Annotated[
        str | None, Field(None, description="상세 메모(선택). 예: '10년째, 인슐린 투여 중'", max_length=200)
    ]


class HealthInfoUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정). 전부 선택 입력 - 회원가입과 무관하게 언제든 입력/수정 가능.
    [변경] 가입 시 나이/성별을 안 받게 되면서, 이 화면이 나이/성별을 처음 입력받는 곳이 됐다."""

    age: Annotated[
        int | None,
        Field(None, description="나이(만 나이 아님, 직접 입력).", examples=[35]),
    ]
    gender: Annotated[Gender | None, Field(None, description="'MALE' 또는 'FEMALE'.")]
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
        list[DiseaseEntry] | None,
        Field(None, description="본인이 진단받은 질환 목록(항목별 상세 메모 포함). 빈 리스트를 보내면 전부 지워진다."),
    ]
    family_history: Annotated[
        list[DiseaseEntry] | None,
        Field(None, description="직계가족의 병력 목록(항목별 상세 메모 포함). 빈 리스트를 보내면 전부 지워진다."),
    ]
    special_notes: Annotated[
        str | None, Field(None, description="특이사항 (알레르기, 복용 중인 약 등)", max_length=1000)
    ]
    other_notes: Annotated[str | None, Field(None, description="기타 자유 입력", max_length=1000)]


class HealthInfoResponse(BaseSerializerModel):
    age: Annotated[int | None, Field(description="Profile에 저장된 나이. 미입력 시 null.")]
    gender: Annotated[Gender | None, Field(description="Profile에 저장된 성별. 미입력 시 null.")]
    height_cm: Annotated[float | None, Field(description="키(cm). 미입력 시 null.")]
    weight_kg: Annotated[float | None, Field(description="체중(kg). 미입력 시 null.")]
    diagnosis_history: Annotated[list[DiseaseEntry], Field(description="본인이 진단받은 질환 목록.")]
    family_history: Annotated[list[DiseaseEntry], Field(description="직계가족의 병력 목록.")]
    special_notes: Annotated[str | None, Field(description="특이사항.")]
    other_notes: Annotated[str | None, Field(description="기타.")]

    @computed_field(description="키/체중으로 계산한 체질량지수. 둘 중 하나라도 없으면 null.")  # type: ignore[prop-decorator]
    @property
    def bmi(self) -> float | None:
        if self.height_cm is None or self.weight_kg is None:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m**2), 1)
