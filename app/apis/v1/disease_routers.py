from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import ORJSONResponse as Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.db.databases import get_db
from app.dependencies.security import get_request_user
from app.dtos.health_info import DiseaseSubtypeSearchResult
from app.models.profiles import Disease
from app.models.users import User
from app.repositories.disease_entry_repository import DiseaseSubtypeRepository

disease_router = APIRouter(prefix="/diseases", tags=["diseases"])


@disease_router.get(
    "/{category}/subtypes",
    response_model=list[DiseaseSubtypeSearchResult],
    summary="구체적 질환명 자동완성 검색",
    description=(
        "개인건강정보에서 대분류(category) 선택 후 세부 질환명을 입력할 때, 원티드 스킬태그처럼 "
        "타이핑하는 대로 기존에 등록된 질환명을 찾아 보여준다. 검색결과에 없으면 그 이름 그대로 "
        "PATCH /users/me/health-info에 보내면 새 항목으로 자동 추가되고, 다음부터는 이 검색에서도 잡힌다."
    ),
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "로그인 필요"}},
)
async def search_disease_subtypes(
    category: Disease,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_request_user)],
    subtype_repo: Annotated[DiseaseSubtypeRepository, Depends(DiseaseSubtypeRepository)],
    q: Annotated[str, Query(description="검색어. 빈 문자열이면 그 대분류의 전체 목록을 보여준다.", max_length=50)] = "",
) -> Response:
    results = await subtype_repo.search(session, category, q)
    body = [DiseaseSubtypeSearchResult(name=r.name, is_custom=r.is_custom) for r in results]
    return Response(content=[item.model_dump() for item in body], status_code=status.HTTP_200_OK)
