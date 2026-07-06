from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.health_metric import HealthMetricCreate, HealthMetricResponse
from app.models.users import User
from app.services.health_metric_service import HealthMetricService

health_metric_router = APIRouter(prefix="/health-metrics", tags=["health-metrics"])


@health_metric_router.post("", response_model=HealthMetricResponse, status_code=status.HTTP_201_CREATED)
async def create_metric(
    data: HealthMetricCreate,
    user: Annotated[User, Depends(get_request_user)],
    health_metric_service: Annotated[HealthMetricService, Depends(HealthMetricService)],
) -> Response:
    m = await health_metric_service.create_metric(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": m.id,
            "weight": m.weight,
            "height": m.height,
            "blood_pressure_systolic": m.blood_pressure_systolic,
            "blood_pressure_diastolic": m.blood_pressure_diastolic,
            "blood_glucose": m.blood_glucose,
            "source": m.source,
            "recorded_at": m.recorded_at.isoformat(),
        },
        "message": "건강 생체 지표를 등록했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)
