from pydantic import BaseModel


class RecognitionJobCreateResult(BaseModel):
    job_id: str
    status: str


class RecognitionCandidate(BaseModel):
    drug_name: str
    match_rate: float
    drug_code: str


class RecognitionResult(BaseModel):
    job_id: str
    status: str
    source_type: str
    candidates: list[RecognitionCandidate] = []
    extracted_fields: dict | None = None


class RecognitionConfirmRequest(BaseModel):
    selected_candidate_drug_code: str | None = None
    confirmed_fields: dict | None = None


class GuideCard(BaseModel):
    title: str
    content: str
    severity: str
    disclaimer: str = "본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다. 출처: 식약처 복약지침"


class RecognitionConfirmResult(BaseModel):
    status: str
    guide_cards: list[GuideCard] = []


class MedicationScheduleResponse(BaseModel):
    id: int
    medication_id: int
    drug_name: str
    times: list[str]
    source_job_id: str | None = None
    # 약 카드 표시용 부가 정보 — 마스터 데이터에 값이 없으면 None (T-NTFY-2)
    form_type: str | None = None
    dosage_guideline: str | None = None
    hospital_name: str | None = None  # 처방 병원명 (T-NTFY-2)


class MedicationScheduleCreateRequest(BaseModel):
    drug_code: str  # standard_code
    times: list[str]
    hospital_name: str | None = None


class MedicationScheduleUpdateRequest(BaseModel):
    """전달한 필드만 부분 수정한다 (T-NTFY-2 알림 화면 인라인 시간 수정용)."""

    times: list[str] | None = None
    hospital_name: str | None = None


class QuickRegisterRequest(BaseModel):
    drug_name: str
    times: list[str]
    hospital_name: str | None = None


class QuickRegisterCandidate(BaseModel):
    drug_code: str
    medication_name: str
    form_type: str | None = None


class QuickRegisterResult(BaseModel):
    status: str  # "registered" | "multiple_matches"
    schedule: MedicationScheduleResponse | None = None
    candidates: list[QuickRegisterCandidate] = []
    auto_created: bool = False
