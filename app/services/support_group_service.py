import uuid

from fastapi import HTTPException, status

from app.dtos.support_group import GroupCreate, GroupJoin
from app.models.support_groups import GroupMember, SupportGroup
from app.models.users import User


class SupportGroupService:
    def _generate_invite_code(self) -> str:
        parts = [uuid.uuid4().hex[:4].upper() for _ in range(4)]
        return "SG-" + "-".join(parts)

    async def create_group(self, user: User, data: GroupCreate) -> SupportGroup:
        invite_code = self._generate_invite_code()
        group = await SupportGroup.create(group_name=data.group_name, invite_code=invite_code)

        # 생성자를 첫 멤버로 자동 등록
        await GroupMember.create(group=group, user=user)
        return group

    async def join_group(self, user: User, data: GroupJoin) -> GroupMember:
        group = await SupportGroup.get_or_none(invite_code=data.invite_code)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 활성화된 초대 코드이거나 연동이 대기 중인 상태입니다.",
            )

        existing = await GroupMember.get_or_none(group=group, user=user)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 참여 중인 그룹입니다.")

        member = await GroupMember.create(group=group, user=user)
        return member

    async def get_group_members(self, group_id: int) -> list[GroupMember]:
        return await GroupMember.filter(group_id=group_id).order_by("-leaderboard_score").prefetch_related("user").all()
