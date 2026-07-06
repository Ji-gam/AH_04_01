from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.support_group import GroupCreate, GroupCreateResponse, GroupJoin, GroupJoinResponse, GroupMemberResponse
from app.models.users import User
from app.services.support_group_service import SupportGroupService

support_group_router = APIRouter(prefix="/support-groups", tags=["support-groups"])


@support_group_router.post("", response_model=GroupCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    user: Annotated[User, Depends(get_request_user)],
    support_group_service: Annotated[SupportGroupService, Depends(SupportGroupService)],
) -> Response:
    group = await support_group_service.create_group(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": group.id,
            "group_name": group.group_name,
            "invite_code": group.invite_code,
            "created_at": group.created_at.isoformat(),
        },
        "message": "서포트 그룹을 성공적으로 생성했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_201_CREATED)


@support_group_router.post("/join", response_model=GroupJoinResponse, status_code=status.HTTP_200_OK)
async def join_group(
    data: GroupJoin,
    user: Annotated[User, Depends(get_request_user)],
    support_group_service: Annotated[SupportGroupService, Depends(SupportGroupService)],
) -> Response:
    member = await support_group_service.join_group(user, data)
    response_data = {
        "success": True,
        "data": {
            "id": member.id,
            "group_id": member.group_id,
            "user_id": member.user_id,
            "leaderboard_score": member.leaderboard_score,
            "joined_at": member.joined_at.isoformat(),
        },
        "message": "서포트 그룹에 참여했습니다.",
    }
    return Response(response_data, status_code=status.HTTP_200_OK)


@support_group_router.get(
    "/{group_id}/members", response_model=list[GroupMemberResponse], status_code=status.HTTP_200_OK
)
async def get_group_members(
    group_id: int,
    user: Annotated[User, Depends(get_request_user)],
    support_group_service: Annotated[SupportGroupService, Depends(SupportGroupService)],
) -> Response:
    members = await support_group_service.get_group_members(group_id)
    data_list = []
    for m in members:
        data_list.append(
            {
                "id": m.id,
                "user_id": m.user_id,
                "name": m.user.name if m.user else "알 수 없음",
                "leaderboard_score": m.leaderboard_score,
                "joined_at": m.joined_at.isoformat(),
            }
        )

    response_data = {"success": True, "data": data_list, "message": "그룹 멤버 리스트를 조회했습니다."}
    return Response(response_data, status_code=status.HTTP_200_OK)
