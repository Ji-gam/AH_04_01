from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_admin_user, get_current_profile_optional
from app.dtos.content_dto import (
    ContentsFeedResponse,
    GenerateContentRequest,
    HealthContentResponse,
    RelatedContentResponse,
)
from app.models.content import ContentCategory
from app.models.profiles import Profile
from app.models.users import User
from app.repositories.user_repository import AdminActionRepository
from app.services.ai_worker_gateway import (
    AIWorkerInvalidRequestError,
    AIWorkerProcessingError,
    AIWorkerUnavailableError,
)
from app.services.content_generation_service import ContentGenerationService
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


@content_router.post(
    "/generate",
    response_model=HealthContentResponse,
    summary="[관리자] 건강 콘텐츠 생성",
    description=(
        "실제로 ai_worker의 `/generate-structured`(LLM 생성)를 호출해 콘텐츠 카드 1건을 만들고 "
        "`health_contents`에 즉시 저장한다(더보기 > 관리자 컨텐츠생성 화면 전용). 저장된 카드는 "
        '"정보" 탭(`GET /contents/me`)에도 그대로 반영된다 — 오프라인 배치 생성(`generate_'
        "health_content.py`)을 보완하는 온라인 단건 생성 경로다. "
        "disease_code/category/topic을 생략하면 서버가 무작위로 고른다. 같은 (질환, 카테고리, "
        "오늘 날짜) 캐시가 있으면 새로 만들지 않고 그 카드를 갱신한다. "
        "[2026-07-27] 원래 인증 자체가 전혀 없어서(로그인조차 불필요) 아무나 LLM 생성을 "
        "트리거해 비용을 유발하고 전체 사용자가 보는 콘텐츠를 바꿀 수 있던 문제를 막기 위해 "
        "get_current_admin_user 추가함. 이 행위는 admin_actions에 감사로그로 남는다."
    ),
    responses={
        503: {"description": "ai_worker가 응답하지 않거나 생성 불가 상태(예: API 키 미설정)."},
        400: {"description": "ai_worker에 잘못된 생성 요청을 보냄(내부 버그 가능성)."},
        502: {"description": "ai_worker 응답은 왔으나 형식이 예상과 다름."},
    },
)
async def generate_content(
    payload: GenerateContentRequest,
    admin: Annotated[User, Depends(get_current_admin_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HealthContentResponse:
    try:
        item = await ContentGenerationService().generate_and_save(
            session,
            disease_code=payload.disease_code,
            category=payload.category.value if payload.category else None,
            topic=payload.topic,
        )
    except AIWorkerUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail="상담사가 잠시 자리를 비웠습니다. 조금 뒤에 다시 방문해주세요.",
        ) from e
    except AIWorkerInvalidRequestError as e:
        raise HTTPException(status_code=400, detail=f"잘못된 생성 요청: {e}") from e
    except AIWorkerProcessingError as e:
        raise HTTPException(status_code=502, detail=f"생성 응답 형식 이상: {e}") from e

    await AdminActionRepository().log(
        session,
        actor_user_id=admin.id,
        action="generate_content",
        target=f"content:{item.get('id')}",
        detail=f"{admin.email} generated content (disease_code={payload.disease_code}, category={payload.category})",
    )
    await session.commit()
    return HealthContentResponse(**item)


@content_router.get(
    "/{content_id}",
    response_model=HealthContentResponse,
    summary="건강 콘텐츠 단건 조회",
    description="상세화면 진입/새로고침용 단건 조회다. 라우터 state가 아니라 DB에서 항상 다시 조회하므로 직접 URL 접근에도 동작한다.",
    responses={404: {"description": "해당 id의 콘텐츠가 없음"}},
)
async def get_content_by_id(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HealthContentResponse:
    item = await ContentService().get_content_by_id(session, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")
    return HealthContentResponse(**item)


@content_router.get(
    "/{content_id}/related",
    response_model=RelatedContentResponse,
    summary="관련 콘텐츠 조회",
    description=(
        "같은 질환(disease_code)·다른 콘텐츠 카테고리의 콘텐츠를 최신순 최대 limit개 반환한다. "
        "disease_code/category는 클라이언트 입력을 받지 않고 content_id로 원본을 다시 조회해 서버가 직접 판단한다."
    ),
    responses={404: {"description": "해당 id의 콘텐츠가 없음"}},
)
async def get_related_contents(
    content_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> RelatedContentResponse:
    base = await ContentService().get_content_by_id(session, content_id)
    if base is None:
        raise HTTPException(status_code=404, detail="콘텐츠를 찾을 수 없습니다.")
    items = await ContentService().get_related_contents(
        session, base["disease_code"], base["category"], content_id, limit=limit
    )
    return RelatedContentResponse(items=[HealthContentResponse(**item) for item in items])
