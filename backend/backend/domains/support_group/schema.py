# backend/domains/support_group/schema.py
import datetime
from pydantic import BaseModel


class GroupCreate(BaseModel):
    group_name: str


class GroupCreateResponse(BaseModel):
    group_id: int
    group_name: str
    invite_code: str
    created_at: datetime.datetime


class GroupJoin(BaseModel):
    invite_code: str


class GroupJoinResponse(BaseModel):
    member_id: int
    group_id: int
    user_id: int
    leaderboard_score: int
    joined_at: datetime.datetime


class GroupMemberResponse(BaseModel):
    member_id: int
    user_id: int
    name: str
    leaderboard_score: int
    joined_at: datetime.datetime
