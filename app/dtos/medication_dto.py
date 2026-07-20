from pydantic import BaseModel, field_validator


class RecognitionJobCreateResult(BaseModel):
    job_id: str
    status: str


class RecognitionCandidate(BaseModel):
    drug_name: str
    match_rate: float
    drug_code: str  # (T-MED-16) item_seq 또는 AUTO_ 더미 코드


class RecognitionResult(BaseModel):
    job_id: str
    status: str
    source_type: str
    candidates: list[RecognitionCandidate] = []
    extracted_fields: dict | None = None


class RecognitionConfirmRequest(BaseModel):
    selected_candidate_drug_code: str | None = None  # (T-MED-16) item_seq 또는 AUTO_ 더미 코드
    confirmed_fields: dict | None = None


class RecognitionConfirmForFamilyRequest(BaseModel):
    """(가족관리) OCR로 인식한 처방전을 본인이 아니라 가족 구성원 몫으로 등록할 때 쓴다.
    RecognitionConfirmRequest와 필드가 거의 같지만 target_profile_id가 추가된 별도 DTO -
    기존 확정등록 흐름(RecognitionConfirmRequest)은 건드리지 않기 위해 분리했다."""

    target_profile_id: int
    selected_candidate_drug_code: str | None = None  # (T-MED-16) item_seq 또는 AUTO_ 더미 코드
    confirmed_fields: dict | None = None


class FoodItem(BaseModel):
    """(T-DOC-4) 음식 상호작용 안내 카드에서 원문 전체를 줄글로 보여주는 대신, 음식명 칩을 먼저
    보여주고 클릭 시 이 음식에 대한 상세(detail)만 펼쳐볼 수 있게 하기 위한 단위.

    (2026-07-15) `polarity`: 원문이 이 음식을 무조건 "피하라"는 게 아닌 경우가 있어 세 가지로
    나눈다.
    - "avoid"(기본값): 함께 섭취를 피해야 함(회피 방법이 없거나 언급되지 않음).
    - "recommend": 오히려 이 약과 함께/식후에 먹으면 좋다는 권장(예: NSAIDs/리튬 + 우유 —
      위장장애 완화 목적).
    - "timing_caution": 동시 섭취는 피해야 하지만, 복용 시간과 일정 간격(1~2시간 등)만 두면
      섭취해도 된다는 구체적인 시차 요령이 있는 경우(예: 자몽주스+칼슘채널차단제 — 복용 후
      2시간 뒤엔 마셔도 됨).
    규칙 기반 추출은 문장에 음식명이 등장하는지만 보고 이런 맥락을 판단하지 못하므로, 자동
    분류 대신 식약처 참조 테이블 빌드 시 사람이 원문을 직접 읽고 확인한 소수의 예외만
    "recommend"/"timing_caution"으로 표시한다(`build_food_drug_interaction_db.py`의
    `_RECOMMEND_OVERRIDES`/`_TIMING_CAUTION_OVERRIDES`). 그 외는 전부 기본값 "avoid" — 잘못
    분류해 실제로 피해야 할 음식을 안전한 것처럼 보여주는 쪽이, 그 반대보다 훨씬 위험하므로
    안전한 기본값을 택했다."""

    name: str
    detail: str
    polarity: str = "avoid"


class GuideCard(BaseModel):
    title: str
    content: str
    severity: str
    disclaimer: str = "본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다. 출처: 식약처 복약지침"
    # (T-DOC-4) 규칙 기반 추출로 음식명이 식별되면 채워진다. 식별 안 되면 None — 이 경우
    # 프론트는 기존처럼 `content` 전체 텍스트를 그대로 보여준다(회귀 없음).
    food_items: list[FoodItem] | None = None


class RecognitionConfirmResult(BaseModel):
    status: str
    guide_cards: list[GuideCard] = []


class MedicationScheduleResponse(BaseModel):
    id: int
    item_seq: str  # (T-MED-16) drugs_data/drug_identification 등 마스터 데이터 조인 키 (또는 AUTO_ 더미 코드)
    drug_name: str
    times: list[str]
    source_job_id: str | None = None
    # 약 카드 표시용 부가 정보 — 마스터 데이터에 값이 없으면 None (T-NTFY-2)
    form_type: str | None = None
    dosage_guideline: str | None = None
    hospital_name: str | None = None  # 처방 병원명 (T-NTFY-2)


class MedicationScheduleCreateRequest(BaseModel):
    drug_code: str  # (T-MED-16) item_seq
    times: list[str]
    hospital_name: str | None = None
    # (가족관리) 이 약을 누가 먹을지 - 생략하면 본인. 본인이 아닌 값은 family_links에서
    # 요청자가 그 프로필의 보호자로 등록되어 있어야만 허용된다(그 외엔 403).
    target_profile_id: int | None = None


class MedicationScheduleUpdateRequest(BaseModel):
    """전달한 필드만 부분 수정한다 (T-NTFY-2 알림 화면 인라인 시간 수정용).

    times는 생략(None)이면 그대로 두지만 빈 리스트([])는 거부한다 - 마지막 시각 하나를
    지우는 걸 이 API로 하면, 약 등록(스케줄)은 그대로 남고 복용 시각만 하나도 없는
    좀비 상태가 된다(복약 알림 화면에는 아예 표시되지 않아 사용자가 되돌릴 방법도 없음).
    등록 자체를 지우고 싶으면 DELETE /medications/{id}를 쓴다."""

    times: list[str] | None = None
    hospital_name: str | None = None

    @field_validator("times")
    @classmethod
    def _times_not_empty(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) == 0:
            raise ValueError("복용 시각은 최소 1개 이상이어야 합니다. 등록 전체 삭제는 DELETE API를 이용하세요.")
        return v


class QuickRegisterRequest(BaseModel):
    drug_name: str
    times: list[str]
    hospital_name: str | None = None
    # (가족관리) 이 약을 누가 먹을지 - 생략하면 본인. 본인이 아닌 값은 family_links에서
    # 요청자가 그 프로필의 보호자로 등록되어 있어야만 허용된다(그 외엔 403).
    target_profile_id: int | None = None


class QuickRegisterCandidate(BaseModel):
    drug_code: str  # (T-MED-16) item_seq
    medication_name: str
    form_type: str | None = None


class QuickRegisterResult(BaseModel):
    status: str  # "registered" | "multiple_matches"
    schedule: MedicationScheduleResponse | None = None
    candidates: list[QuickRegisterCandidate] = []
    auto_created: bool = False


class InteractionWarning(BaseModel):
    """등록약 두 개가 식약처 병용금기 DUR 데이터에서 페어로 확인된 경우의 경고 항목 (T-MED-2-2)."""

    drug_a_name: str
    drug_b_name: str
    description: str
    disclaimer: str = (
        "본 서비스는 정보 제공 도구이며, 의학적 진단·처방을 대체하지 않습니다. 출처: 식약처 의약품안전나라(DUR)"
    )


class InteractionCheckResult(BaseModel):
    warnings: list[InteractionWarning] = []
    checked_count: int  # item_seq가 있어 실제로 비교 대상이 된 등록약 수


class FoodInteractionCheckResult(BaseModel):
    """(T-DOC-2) 등록된 모든 약 기준으로 음식/음주 주의사항을 모아온 결과.

    confirm_recognition_job의 guide_cards(문서 등록 확정 직후 1회성 안내)와 달리, 이 결과는
    등록 방식(OCR/수동 등록)과 무관하게 "음식(13번)" 탭을 열 때마다 현재 등록약 전체를 대상으로
    조회한다."""

    guide_cards: list[GuideCard] = []
    checked_count: int  # 대상이 된 등록약 수(중복 제거)
