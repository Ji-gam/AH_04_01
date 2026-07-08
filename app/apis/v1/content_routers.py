from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.content_dto import HealthContentResponse
from app.models.content import ContentCategory
from app.models.profiles import Profile
from app.services.content_service import ContentService

content_router = APIRouter(prefix="/contents", tags=["Content"])


@content_router.get(
    "/me",
    response_model=list[HealthContentResponse],
    summary="내 질환 기반 건강 콘텐츠 조회",
    description=(
        "로그인한 프로필의 질환(conditions)에 해당하는 오늘자 건강 콘텐츠 카드를 카테고리별로 "
        "누적 피드 형태로 반환한다. 캐시에 없는 조합은 목록에서 제외되며(라이브 생성 없음), "
        "category를 지정하지 않으면 전체 카테고리를 반환한다."
    ),
)
async def get_my_contents(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
    category: Annotated[ContentCategory | None, Query(description="필터링할 카테고리(미지정 시 전체)")] = None,
) -> list[HealthContentResponse]:
    contents = await ContentService().get_contents_for_profile(
        session, profile.id, category=category.value if category else None
    )
    return [HealthContentResponse(**content) for content in contents]
