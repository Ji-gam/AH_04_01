from datetime import datetime

from pydantic import BaseModel, EmailStr


class FamilyLinkCreateRequest(BaseModel):
    email: EmailStr  # 연결을 요청할 가족 구성원(피보호자)의 가입 이메일
    relation_label: str  # 예: "아버지", "어머니", "할머니"


class FamilyLinkResult(BaseModel):
    """연결 요청/응답 공용 결과 - 상대방 프로필 기준으로 표시."""

    link_id: int
    profile_id: int
    name: str
    relation_label: str
    status: str  # PENDING / ACCEPTED
    created_at: datetime


class FamilyMembersResult(BaseModel):
    as_guardian_accepted: list[FamilyLinkResult]  # 내가 관리하는(수락된) 가족
    as_guardian_pending: list[FamilyLinkResult]  # 내가 보냈지만 아직 응답 대기중인 요청
    as_member_accepted: list[FamilyLinkResult]  # 나를 관리하고 있는(수락한) 보호자
    as_member_pending: list[FamilyLinkResult]  # 내가 받은, 아직 응답 안 한 요청 - 여기서 수락/거절


class FamilyInviteCodeCreateRequest(BaseModel):
    relation_label: str  # 예: "아버지", "어머니" - 발급하는 내가, 코드를 받을 사람과의 관계


class FamilyInviteCodeResult(BaseModel):
    code: str
    relation_label: str
    expires_at: datetime


class FamilyInviteCodeRedeemRequest(BaseModel):
    code: str
