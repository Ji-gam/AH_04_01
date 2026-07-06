from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.generated_guide import GuideCreate, GuideResponse, GuideTaskAccepted
from app.models.users import User
from app.services.generated_guide_service import GeneratedGuideService

generated_guide_router = APIRouter(prefix="/generated-guides", tags=["generated-guides"])


@generated_guide_router.post("", response_model=GuideTaskAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_guide(
    data: GuideCreate,
    user: Annotated[User, Depends(get_request_user)],
    guide_service: Annotated[GeneratedGuideService, Depends(GeneratedGuideService)],
) -> Response:
    # ⚠️ 비동기 작업 큐 도입 전이라 동기적으로 즉시 생성 후 task 반환 형태로 모사
    guide = await guide_service.create_guide(user, data)

    response_data = {
        "success": True,
        "data": {
            "task_id": f"guide_task_{uuid_hex_placeholder()}",
            "status": "PROCESSING",
            "created_at": guide.created_at.isoformat(),
        },
        "message": "LLM 맞춤형 가이드 생성 요청이 수락되었습니다.",
    }
    return Response(response_data, status_code=status.HTTP_202_ACCEPTED)


@generated_guide_router.get("/{guide_id}", response_model=GuideResponse, status_code=status.HTTP_200_OK)
async def get_guide_detail(
    guide_id: int,
    user: Annotated[User, Depends(get_request_user)],
    guide_service: Annotated[GeneratedGuideService, Depends(GeneratedGuideService)],
) -> Response:
    guide = await guide_service.get_guide(user, guide_id)

    response_data = {
        "success": True,
        "data": {
            "id": guide.id,
            "user_id": guide.user_id,
            "record_id": guide.record_id,
            "guide_type": guide.guide_type,
            "content": guide.content,
            "created_at": guide.created_at.isoformat(),
        },
        "message": "맞춤형 가이드 상세 정보를 조회했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)


def uuid_hex_placeholder() -> str:
    import uuid

    return uuid.uuid4().hex[:10]
