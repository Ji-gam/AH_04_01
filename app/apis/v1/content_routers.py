from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile_optional
from app.dtos.content_dto import ContentsFeedResponse, HealthContentResponse
from app.models.content import ContentCategory
from app.models.profiles import Profile
from app.services.content_personalization_service import ContentPersonalizationService
from app.services.content_service import ContentService

content_router = APIRouter(prefix="/contents", tags=["Content"])


@content_router.get(
    "/me",
    response_model=ContentsFeedResponse,
    summary="건강 콘텐츠 피드 조회",
    description=(
        '"정보" 탭 콘텐츠 피드. 로그인 없이도 조회 가능한 공개 엔드포인트다. '
        "로그인한 프로필에 질환(diagnosis_history)이 등록되어 있으면 그 질환들의 콘텐츠만(personalized=true), "
        "비로그인이거나 등록된 질환이 없으면 전체 질환의 콘텐츠를 누적 피드(최신순)로 반환한다(personalized=false). "
        "category를 지정하지 않으면 전체 카테고리를 반환하고, limit을 지정하면 최신순으로 그 개수만큼만 반환한다."
    ),
)
async def get_my_contents(
    profile: Annotated[Profile | None, Depends(get_current_profile_optional)],
    session: Annotated[AsyncSession, Depends(get_db)],
    category: Annotated[ContentCategory | None, Query(description="필터링할 카테고리(미지정 시 전체)")] = None,
    limit: Annotated[int | None, Query(ge=1, description="반환 개수 제한(미지정 시 전체)")] = None,
) -> ContentsFeedResponse:
    personalized, diseases = ContentPersonalizationService().resolve(profile)
    items = await ContentService().get_contents(
        session, diseases, category=category.value if category else None, limit=limit
    )
    return ContentsFeedResponse(
        personalized=personalized,
        items=[HealthContentResponse(**item) for item in items],
    )
