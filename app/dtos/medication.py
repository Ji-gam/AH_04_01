from app.dtos.base import BaseSerializerModel


class MedicationResponse(BaseSerializerModel):
    id: int
    standard_code: str | None = None
    medication_name: str
    form_type: str | None = None
    dosage_guideline: str | None = None
    side_effects: str | None = None
    precautions: str | None = None
    storage_method: str | None = None


class ImageSearchCandidate(BaseSerializerModel):
    id: int
    medication_name: str
    shape: str | None = None
    color: str | None = None
    letters: str | None = None
    similarity: float


class ImageSearchResponse(BaseSerializerModel):
    candidates: list[ImageSearchCandidate]
