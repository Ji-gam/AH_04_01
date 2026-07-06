# backend/domains/support_group/router.py
# API_Specification_v3.pdf [M3] 서포트 그룹 생성/참여/멤버조회
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import get_current_user
from backend.domains.user.model import User
from .model import SupportGroup, GroupMember
from .schema import GroupCreate, GroupCreateResponse, GroupJoin, GroupJoinResponse, GroupMemberResponse

router = APIRouter()


def _generate_invite_code() -> str:
    # 명세 예시 형태: SG-A7B8-C9D0-E1F2-G3H4
    parts = [uuid.uuid4().hex[:4].upper() for _ in range(4)]
    return "SG-" + "-".join(parts)


@router.post("", response_model=GroupCreateResponse, status_code=201, summary="서포트 그룹 생성")
def create_group(data: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    invite_code = _generate_invite_code()
    group = SupportGroup(group_name=data.group_name, invite_code=invite_code)
    db.add(group)
    db.commit()
    db.refresh(group)

    # 생성 요청자를 첫 멤버(사실상 방장)로 자동 등록
    # [v3 명세 참고사항] SUPPORT_GROUPS에 created_by 컬럼이 없어, 방장 식별은
    # "가장 먼저 등록된 GROUP_MEMBERS 행"으로 간주하는 방식으로 처리했습니다.
    first_member = GroupMember(group_id=group.id, user_id=current_user.id)
    db.add(first_member)
    db.commit()

    return {
        "group_id": group.id,
        "group_name": group.group_name,
        "invite_code": group.invite_code,
        "created_at": group.created_at,
    }


@router.post("/join", response_model=GroupJoinResponse, summary="서포트 그룹 참여 (초대 코드 입력)")
def join_group(data: GroupJoin, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(SupportGroup).filter(SupportGroup.invite_code == data.invite_code).first()
    if not group:
        raise HTTPException(status_code=400, detail="이미 활성화된 초대 코드이거나 연동이 대기 중인 상태입니다.")

    existing = db.query(GroupMember).filter(GroupMember.group_id == group.id, GroupMember.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 참여 중인 그룹입니다.")

    member = GroupMember(group_id=group.id, user_id=current_user.id)
    db.add(member)
    db.commit()
    db.refresh(member)

    return {
        "member_id": member.id,
        "group_id": member.group_id,
        "user_id": member.user_id,
        "leaderboard_score": member.leaderboard_score,
        "joined_at": member.joined_at,
    }


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse], summary="서포트 그룹 멤버 및 리더보드 조회")
def get_group_members(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    members = (
        db.query(GroupMember)
        .filter(GroupMember.group_id == group_id)
        .order_by(GroupMember.leaderboard_score.desc())
        .all()
    )
    return [
        {
            "member_id": m.id,
            "user_id": m.user_id,
            "name": m.user.name,
            "leaderboard_score": m.leaderboard_score,
            "joined_at": m.joined_at,
        }
        for m in members
    ]
