from app.dtos.base import BaseSerializerModel


class InteractionResponse(BaseSerializerModel):
    id: int
    medication_id: int
    substance_name: str
    risk_level: str
    guidance_text: str | None = None


class AnalyzeRequest(BaseSerializerModel):
    food_log_id: int


class AnalyzeResponse(BaseSerializerModel):
    food_log_id: int
    matched_rules: list[int]
    interaction_notes: str
