from pydantic import BaseModel


class OcrRequestSchema(BaseModel):
    source_type: str
    file_base64: str


class OcrCandidateSchema(BaseModel):
    drug_name: str
    match_rate: float
    drug_code: str


class OcrResponseSchema(BaseModel):
    status: str
    candidates: list[OcrCandidateSchema]
    extracted_fields: dict
