from pydantic import BaseModel, Field


class DurScreeningRequest(BaseModel):
    drug_names: list[str] = Field(default_factory=list, description="스크리닝할 약품명 목록")


# --- 공통 ---


class DrugRef(BaseModel):
    """다른 약을 이름 문자열이 아니라 item_seq로 참조하기 위한 최소 식별 정보."""

    item_seq: str
    item_name: str


# --- 1단계: 기본 스크리닝 (단일 약품) ---


class DurSimpleFlag(BaseModel):
    """항상 6개 고정 순서(PWNM/ODSN/SPCIFY_AGRDE/MDCTN/SEOBANG/CPCTY)로 내려간다 - 프론트가
    "없으면 표시 안 함" 판단을 할 필요 없이 배열을 그대로 pill 6개에 매핑하면 된다."""

    rule_code: str = Field(..., description="PWNM/ODSN/SPCIFY_AGRDE/MDCTN/SEOBANG/CPCTY")
    rule_label: str = Field(..., description="임부금기/노인주의/특정연령대금기/투여기간주의/분할주의/용량주의")
    present: bool = Field(..., description="이 약품에 해당 규칙이 실제로 걸리는지 여부")
    prohbt_content: str | None = Field(None, description="금기/주의 내용 (present=false면 항상 null)")
    remark: str | None = Field(None, description="비고 (present=false면 항상 null)")


class DrugIdentification(BaseModel):
    shape: str | None = Field(None, description="알약 모양")
    color: str | None = Field(None, description="알약 색상")
    mark: str | None = Field(None, description="알약에 새겨진 마크")


class DrugDetail(BaseModel):
    item_seq: str
    item_name: str
    entp_name: str | None = None
    etc_otc_name: str | None = Field(None, description="전문의약품/일반의약품 구분")
    form_name: str | None = Field(None, description="제형 (정제 등)")
    efcy_qesitm: str | None = Field(None, description="효능/효과")
    use_method_qesitm: str | None = Field(None, description="용법/용량")
    atpn_warn_qesitm: str | None = Field(None, description="사용상 주의사항(경고)")
    se_qesitm: str | None = Field(None, description="부작용")
    deposit_method_qesitm: str | None = Field(None, description="보관방법")
    item_image: str | None = Field(None, description="약품 이미지 URL")
    identification: DrugIdentification | None = Field(None, description="알약 외형 식별 정보")
    atc_code: str | None = Field(None, description="WHO ATC 분류코드 (T-MED-14-1)")
    is_rare_drug: bool | None = Field(None, description="희귀의약품 여부 (T-MED-14-1)")
    narcotic_kind_name: str | None = Field(
        None, description="마약류 구분(마약/향정/한외마약 등, 해당 없으면 null) (T-MED-14-1)"
    )


class BasicScreeningResult(BaseModel):
    drug_detail: DrugDetail
    dur_simple: list[DurSimpleFlag] = Field(default_factory=list)


class BasicScreeningResponse(BaseModel):
    results: list[BasicScreeningResult] = Field(default_factory=list)
    unmatched_drug_names: list[str] = Field(default_factory=list, description="매칭되지 않은 약품명 목록")


# --- 2단계: 상호작용 스크리닝 (약품 목록 간) ---


class DurInteractionWarning(BaseModel):
    rule_type: str = Field(..., description="규칙 타입 (병용금기/효능군중복주의)")
    drug_a: DrugRef
    drug_b: DrugRef
    prohbt_content: str | None = Field(None, description="상호작용 금기/주의 내용")
    remark: str | None = None


class RecallInfo(BaseModel):
    item_seq: str
    item_name: str
    entp_name: str | None = Field(None, description="제조사")
    recall_reason: str | None = Field(None, description="회수 사유")
    recall_command_date: str | None = Field(None, description="회수 명령 일자")
    enforced: bool | None = Field(None, description="강제 회수 여부 (True=강제, False=자율)")


class DrugIntrc(BaseModel):
    interactions: list[DurInteractionWarning] = Field(default_factory=list)
    recalls: list[RecallInfo] = Field(default_factory=list)


class InteractionScreeningResponse(BaseModel):
    drug_intrc: DrugIntrc
    unmatched_drug_names: list[str] = Field(default_factory=list)


# --- 3단계: 성분 기준 심층 스크리닝 ---


class IngredientRuleDetail(BaseModel):
    rule_type: str
    prohbt_content: str | None = None
    remark: str | None = None


class IngredientSourceDrug(BaseModel):
    """이 성분을 가진 입력 약품 - item_seq로 상세화면에 바로 링크 가능하고, 실제 이 약에서의
    함량(qnt/unit)을 함께 내려줘 같은 성분이라도 약마다 다른 용량을 구분할 수 있다 (T-MED-14-1).
    qnt/unit은 drug_prdt_mcpn_detail 기반일 때만 채워지고, MATERIAL_NAME 텍스트 폴백 매칭인
    경우 null."""

    item_seq: str
    item_name: str
    qnt: str | None = Field(None, description="이 약에서 이 성분의 함량 (예: '60')")
    unit: str | None = Field(None, description="함량 단위 (예: '밀리그램')")


class IngredientDetail(BaseModel):
    ingr_code: str
    ingr_name: str
    source_drugs: list[IngredientSourceDrug] = Field(default_factory=list, description="이 성분을 가진 입력 약품 목록")
    rules: list[IngredientRuleDetail] = Field(default_factory=list, description="성분 기준 DUR 규칙 목록")


class IngredientScreeningResponse(BaseModel):
    ingredients: list[IngredientDetail] = Field(default_factory=list, description="성분별 금기/주의 사항 디테일")
    unmatched_drug_names: list[str] = Field(default_factory=list)
