from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, computed_field

from app.core.validators import optional_after_validator, validate_height_cm, validate_weight_kg
from app.dtos.base import BaseSerializerModel
from app.models.profiles import Disease, DiseaseStatus, FamilyRelation, Gender


class DiagnosisEntry(BaseModel):
    """본인 진단병력 항목 하나. disease 외 나머지는 전부 선택 - AI 상담이 바로 참고할 수 있게
    "몇 년째"/"조절상태"/"약물치료 여부"는 정해진 값(구조화)으로 받고, 나머지는 자유메모로 받는다.

    [구체적 질환명] 같은 대분류(예: 암)라도 폐암/간암/갑상선암처럼 세부 종류에 따라 약물이나
    건강관리 방향이 크게 달라진다. 그래서 대분류(disease)와 별개로 "구체적으로 어떤 질환인지"를
    짧은 이름으로 따로 받는다 - 자유서술(detail)에 섞이면 AI가 놓칠 수 있어서 분리했다."""

    disease: Annotated[Disease, Field(description="5대질환 중 하나 또는 'OTHER'(기타).")]
    disease_subtype: Annotated[
        str | None,
        Field(None, description="구체적 질환명(선택). 예: '폐암', '제2형 당뇨'", max_length=50),
    ]
    diagnosed_years_ago: Annotated[
        int | None, Field(None, ge=0, le=100, description="진단받은 지 몇 년째인지(선택).", examples=[10])
    ]
    status: Annotated[DiseaseStatus | None, Field(None, description="현재 조절상태(선택).")]
    on_medication: Annotated[bool | None, Field(None, description="현재 약물치료 중인지(선택).")]
    detail: Annotated[
        str | None, Field(None, description="나머지 자유 메모(선택). 예: '인슐린 투여 중'", max_length=200)
    ]


class FamilyHistoryEntry(BaseModel):
    """가족력 항목 하나. disease 외 나머지는 전부 선택 - 혈연관계(relation)는 유전적 위험도
    해석에 직접 영향을 주므로 구조화된 값으로 받는다. disease_subtype은 DiagnosisEntry와 동일한
    이유(대분류만으론 부족)로 추가."""

    disease: Annotated[Disease, Field(description="5대질환 중 하나 또는 'OTHER'(기타).")]
    disease_subtype: Annotated[str | None, Field(None, description="구체적 질환명(선택). 예: '폐암'", max_length=50)]
    relation: Annotated[FamilyRelation | None, Field(None, description="누구의 병력인지(선택).")]
    detail: Annotated[str | None, Field(None, description="나머지 자유 메모(선택).", max_length=200)]


class DiseaseSubtypeSearchResult(BaseModel):
    """구체적 질환명 검색(자동완성) 결과 항목 하나."""

    name: Annotated[str, Field(description="구체적 질환명. 이 값을 그대로 disease_subtype으로 보내면 됨.")]
    is_custom: Annotated[bool, Field(description="미리 등록된 항목이 아니라 다른 사용자가 직접 추가한 항목인지.")]


class HealthInfoUpdateRequest(BaseModel):
    """전달한 필드만 갱신한다(부분 수정). 전부 선택 입력 - 회원가입과 무관하게 언제든 입력/수정 가능.
    [변경] 가입 시 나이/성별을 안 받게 되면서, 이 화면이 나이/성별을 처음 입력받는 곳이 됐다.
    [재설계] 나이를 직접 입력받지 않고 생년월일(birth_date)을 받아서, 나이는 항상 그로부터
    자동 계산한다(카카오 비즈앱 전환 후 실제 생년월일을 받아올 가능성을 고려한 결정)."""

    birth_date: Annotated[
        date | None,
        Field(None, description="생년월일. 만 나이는 이 값으로 항상 자동 계산된다.", examples=["1990-05-20"]),
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
        list[DiagnosisEntry] | None,
        Field(None, description="본인이 진단받은 질환 목록(항목별 상세 정보 포함). 빈 리스트를 보내면 전부 지워진다."),
    ]
    family_history: Annotated[
        list[FamilyHistoryEntry] | None,
        Field(None, description="직계가족의 병력 목록(항목별 상세 정보 포함). 빈 리스트를 보내면 전부 지워진다."),
    ]
    special_notes: Annotated[
        str | None, Field(None, description="특이사항 (알레르기, 복용 중인 약 등)", max_length=1000)
    ]
    other_notes: Annotated[str | None, Field(None, description="기타 자유 입력", max_length=1000)]


class HealthInfoResponse(BaseSerializerModel):
    age: Annotated[int | None, Field(description="만 나이 - birth_date로부터 자동 계산된 값. 미입력 시 null.")]
    birth_date: Annotated[date | None, Field(description="생년월일. 미입력 시 null.")]
    gender: Annotated[Gender | None, Field(description="Profile에 저장된 성별. 미입력 시 null.")]
    height_cm: Annotated[float | None, Field(description="키(cm). 미입력 시 null.")]
    weight_kg: Annotated[float | None, Field(description="체중(kg). 미입력 시 null.")]
    diagnosis_history: Annotated[list[DiagnosisEntry], Field(description="본인이 진단받은 질환 목록.")]
    family_history: Annotated[list[FamilyHistoryEntry], Field(description="직계가족의 병력 목록.")]
    special_notes: Annotated[str | None, Field(description="특이사항.")]
    other_notes: Annotated[str | None, Field(description="기타.")]

    @computed_field(description="키/체중으로 계산한 체질량지수. 둘 중 하나라도 없으면 null.")  # type: ignore[prop-decorator]
    @property
    def bmi(self) -> float | None:
        if self.height_cm is None or self.weight_kg is None:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m**2), 1)
