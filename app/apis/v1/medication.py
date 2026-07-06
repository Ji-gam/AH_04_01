from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.medication import ImageSearchResponse, MedicationResponse
from app.models.users import User
from app.services.medication_service import MedicationService

medication_router = APIRouter(prefix="/medications", tags=["medications"])


@medication_router.get("/{medication_id}", response_model=MedicationResponse, status_code=status.HTTP_200_OK)
async def get_medication(
    medication_id: int,
    user: Annotated[User, Depends(get_request_user)],
    med_service: Annotated[MedicationService, Depends(MedicationService)],
) -> Response:
    med = await med_service.get_medication_by_id(medication_id)
    # CONVENTIONS.md 공통 응답 규격 적용
    response_data = {
        "success": True,
        "data": {
            "id": med.id,
            "standard_code": med.standard_code,
            "medication_name": med.medication_name,
            "form_type": med.form_type,
            "dosage_guideline": med.dosage_guideline,
            "side_effects": med.side_effects,
            "precautions": med.precautions,
            "storage_method": med.storage_method,
        },
        "message": "의약품 마스터 정보를 조회했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)


@medication_router.post("/search-by-image", response_model=ImageSearchResponse, status_code=status.HTTP_200_OK)
async def search_by_image(
    user: Annotated[User, Depends(get_request_user)],
    file: Annotated[UploadFile, File()],
) -> Response:
    # CLIP 임베딩/pgvector 미도입으로 스텁 처리 유지
    response_data = {
        "success": True,
        "data": {"candidates": []},
        "message": "알약 이미지 검색 엔드포인트 (현재 pgvector 미도입으로 스텁 처리됨)",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)
