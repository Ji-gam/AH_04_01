from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile_optional
from app.dtos.dur_dto import (
    BasicScreeningResponse,
    DurScreeningRequest,
    IngredientScreeningResponse,
    InteractionScreeningResponse,
)
from app.services.dur_service import DurScreeningService

dur_router = APIRouter(tags=["DUR"])


@dur_router.post("/dur/screening/basic", response_model=BasicScreeningResponse)
async def screen_basic(
    body: DurScreeningRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    profile=Depends(get_current_profile_optional),  # noqa: B008
):
    """
    1단계 스크리닝: 단일 약품에 대한 기본 복용 안내 및 기초 DUR 금기/주의(임부/노인 등) 정보 반환.
    """
    service = DurScreeningService()
    return await service.screen_basic(session, body.drug_names)


@dur_router.post("/dur/screening/interaction", response_model=InteractionScreeningResponse)
async def screen_interaction(
    body: DurScreeningRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    profile=Depends(get_current_profile_optional),  # noqa: B008
):
    """
    2단계 스크리닝: 여러 약품 간의 상호작용(병용금기, 효능군중복) 및 리콜 정보 반환.
    """
    service = DurScreeningService()
    return await service.screen_interactions(session, body.drug_names)


@dur_router.post("/dur/screening/ingredient", response_model=IngredientScreeningResponse)
async def screen_ingredient(
    body: DurScreeningRequest,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    profile=Depends(get_current_profile_optional),  # noqa: B008
):
    """
    3단계 스크리닝: 약품 성분 기준 상세 금기/주의(병용, 노인, 임부, 용량 등 전체) 정보 반환.
    """
    service = DurScreeningService()
    return await service.screen_ingredients(session, body.drug_names)
