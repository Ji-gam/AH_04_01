from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"


class GuideCard(BaseModel):
    """
    api_spec_core_v1.yaml의 GuideCard 스키마와 1:1 대응.
    Tier 2 stub이든 RAG 완성 후든, 이 응답 형태는 절대 바뀌지 않는다.
    (바뀌면 프론트가 다시 작업해야 하므로 — 이게 스키마를 먼저 고정하는 이유)
    """

    title: str
    content: str
    severity: Severity
    disclaimer: str = "이 정보는 의학적 조언이 아니며, 정확한 진단은 반드시 의료진과 상담하세요."


class RecognitionConfirmResult(BaseModel):
    status: str
    guide_cards: list[GuideCard]
