from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.drug_interaction import AnalyzeRequest, AnalyzeResponse, InteractionResponse
from app.models.users import User
from app.services.drug_interaction_service import DrugInteractionService

drug_interaction_router = APIRouter(prefix="/drug-interactions", tags=["drug-interactions"])


@drug_interaction_router.get("", response_model=list[InteractionResponse], status_code=status.HTTP_200_OK)
async def get_interactions(
    medication_id: Annotated[int, Query(description="조회할 의약품 ID")],
    user: Annotated[User, Depends(get_request_user)],
    drug_interaction_service: Annotated[DrugInteractionService, Depends(DrugInteractionService)],
) -> Response:
    rules = await drug_interaction_service.get_medication_interactions(medication_id)
    data_list = []
    for r in rules:
        data_list.append(
            {
                "id": r.id,
                "medication_id": r.medication_id,
                "substance_name": r.substance_name,
                "risk_level": r.risk_level,
                "guidance_text": r.guidance_text,
            }
        )

    response_data = {"success": True, "data": data_list, "message": "약물-음식 상호작용 규칙 리스트를 조회했습니다."}
    return Response(response_data, status_code=status.HTTP_200_OK)


@drug_interaction_router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_200_OK)
async def analyze_interaction(
    data: AnalyzeRequest,
    user: Annotated[User, Depends(get_request_user)],
    drug_interaction_service: Annotated[DrugInteractionService, Depends(DrugInteractionService)],
) -> Response:
    analysis = await drug_interaction_service.analyze_food_interaction(user, data)
    response_data = {"success": True, "data": analysis, "message": "식사-투약 통합 위험도를 분석했습니다."}
    return Response(response_data, status_code=status.HTTP_200_OK)
