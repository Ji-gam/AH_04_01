# backend/domains/medication/router.py
# API_Specification_v3.pdf [M5-4] 의약품 마스터 조회, [M5-5] 알약 이미지 검색(보류)
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import Medication
from .schema import MedicationResponse, ImageSearchResponse

router = APIRouter()


@router.get("/{medication_id}", response_model=MedicationResponse, summary="의약품 마스터 조회")
def get_medication(medication_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    med = db.query(Medication).filter(Medication.id == medication_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="의약품 정보를 찾을 수 없습니다.")
    return {
        "medication_id": med.id,
        "standard_code": med.standard_code,
        "medication_name": med.medication_name,
        "form_type": med.form_type,
        "dosage_guideline": med.dosage_guideline,
        "side_effects": med.side_effects,
        "precautions": med.precautions,
        "storage_method": med.storage_method,
    }


@router.post("/search-by-image", response_model=ImageSearchResponse, summary="알약 이미지 기반 의약품 검색 [보류: pgvector 미도입]")
def search_by_image(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # ⚠️ [보류] 이 엔드포인트는 PostgreSQL + pgvector + CLIP 임베딩이 필요한 기능입니다.
    # 현재 DB가 MySQL로 유지되기로 결정되어 실제 벡터 유사도 검색은 구현하지 않았습니다.
    # 나중에 pgvector 도입이 결정되면: 1) Medication에 embedding VECTOR(512) 컬럼 추가
    # 2) 이미지 -> CLIP 인코딩 -> 코사인 유사도 검색 로직을 여기에 구현하면 됩니다.
    return {"candidates": []}
