from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.symptom_log import SymptomLogCreate, SymptomLogResponse
from app.models.users import User
from app.services.symptom_log_service import SymptomLogService

symptom_log_router = APIRouter(prefix="/symptom-logs", tags=["symptom-logs"])


@symptom_log_router.post("", response_model=SymptomLogResponse, status_code=status.HTTP_201_CREATED)
async def create_symptom_log(
    data: SymptomLogCreate,
    user: Annotated[User, Depends(get_request_user)],
    symptom_log_service: Annotated[SymptomLogService, Depends(SymptomLogService)],
) -> Response:
    s = await symptom_log_service.create_symptom_log(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": s.id,
            "symptom_notes": s.symptom_notes,
            "severity_level": s.severity_level,
            "recorded_at": s.recorded_at.isoformat(),
        },
        "message": "증상 기록 및 심각도를 등록했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)
