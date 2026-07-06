# backend/domains/drug_food_interaction/schema.py
from typing import Optional, List
from pydantic import BaseModel


class InteractionResponse(BaseModel):
    interaction_id: int
    medication_id: int
    substance_name: str
    risk_level: str
    guidance_text: Optional[str] = None


class AnalyzeRequest(BaseModel):
    food_log_id: int


class AnalyzeResponse(BaseModel):
    food_log_id: int
    matched_rules: List[int]
    interaction_notes: str
