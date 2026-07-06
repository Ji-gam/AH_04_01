# backend/domains/medication/schema.py
from typing import Optional, List
from pydantic import BaseModel


class MedicationResponse(BaseModel):
    medication_id: int
    standard_code: Optional[str] = None
    medication_name: str
    form_type: Optional[str] = None
    dosage_guideline: Optional[str] = None
    side_effects: Optional[str] = None
    precautions: Optional[str] = None
    storage_method: Optional[str] = None


class ImageSearchCandidate(BaseModel):
    medication_id: int
    medication_name: str
    shape: Optional[str] = None
    color: Optional[str] = None
    letters: Optional[str] = None
    similarity: float


class ImageSearchResponse(BaseModel):
    candidates: List[ImageSearchCandidate]
