from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies.security import get_current_profile
from app.dtos.family import (
    FamilyInviteCodeCreateRequest,
    FamilyInviteCodeRedeemRequest,
    FamilyInviteCodeResult,
    FamilyLinkCreateRequest,
    FamilyLinkResult,
    FamilyMembersResult,
)
from app.models.profiles import Profile
from app.services.family_service import FamilyService

family_router = APIRouter(prefix="/family", tags=["Family"])


@family_router.post(
    "/link",
    response_model=FamilyLinkResult,
    status_code=201,
    summary="가족 구성원 연결 요청 보내기",
    description=(
        "이메일로 가족 구성원(예: 부모님)을 찾아 연결을 '요청'한다(PENDING). 상대방이 "
        "/family/link/{link_id}/accept 로 수락해야 실제 보호자 권한(약 등록 등)이 생긴다."
    ),
)
async def request_family_link(
    body: FamilyLinkCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FamilyLinkResult:
    service = FamilyService()
    return await service.request_link(session, profile.id, body)


@family_router.post(
    "/link/{link_id}/accept",
    response_model=FamilyLinkResult,
    summary="받은 연결 요청 수락",
    description="나에게 온 연결 요청을 수락한다. 요청받은 사람 본인만 수락할 수 있다.",
)
async def accept_family_link(
    link_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FamilyLinkResult:
    service = FamilyService()
    return await service.accept_request(session, profile.id, link_id)


@family_router.post(
    "/link/{link_id}/reject",
    status_code=204,
    summary="받은 연결 요청 거절",
    description="나에게 온 연결 요청을 거절한다. 요청받은 사람 본인만 거절할 수 있다.",
)
async def reject_family_link(
    link_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = FamilyService()
    await service.reject_request(session, profile.id, link_id)


@family_router.get(
    "/members",
    response_model=FamilyMembersResult,
    summary="가족 연결 목록 조회",
    description="내가 관리(수락됨)/요청 보낸(대기중) 목록과, 나를 관리(수락함)/나에게 요청 온(대기중) 목록을 함께 반환한다.",
)
async def list_family_members(
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FamilyMembersResult:
    service = FamilyService()
    return await service.list_members(session, profile.id)


@family_router.delete(
    "/link/{link_id}",
    status_code=204,
    summary="가족 연결/요청 해제",
    description="요청을 보낸 사람(보호자)만 연결(또는 대기중인 요청)을 해제할 수 있다.",
)
async def delete_family_link(
    link_id: int,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = FamilyService()
    await service.delete_link(session, profile.id, link_id)


@family_router.post(
    "/invite-code",
    response_model=FamilyInviteCodeResult,
    status_code=201,
    summary="가족 초대코드 발급",
    description=(
        "이메일을 모르거나(예: 카카오 임시 가입 계정) 이메일 방식이 번거로울 때 쓰는 대안 경로. "
        "발급된 코드를 카톡/문자 등으로 전달하면, 상대방이 /family/invite-code/redeem 로 "
        "입력하는 즉시 연결된다(승인 절차 없음 - 코드를 안다는 것 자체가 이미 상호 동의로 간주)."
    ),
)
async def create_family_invite_code(
    body: FamilyInviteCodeCreateRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FamilyInviteCodeResult:
    service = FamilyService()
    return await service.create_invite_code(session, profile.id, body)


@family_router.post(
    "/invite-code/redeem",
    response_model=FamilyLinkResult,
    summary="가족 초대코드 사용 (즉시 연결)",
    description="전달받은 초대코드를 입력해 즉시 연결한다. 승인 대기 없이 바로 ACCEPTED 상태가 된다.",
)
async def redeem_family_invite_code(
    body: FamilyInviteCodeRedeemRequest,
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FamilyLinkResult:
    service = FamilyService()
    return await service.redeem_invite_code(session, profile.id, body.code)
