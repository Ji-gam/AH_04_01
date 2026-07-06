import datetime

from app.dtos.base import BaseSerializerModel


class GroupCreate(BaseSerializerModel):
    group_name: str


class GroupCreateResponse(BaseSerializerModel):
    id: int
    group_name: str
    invite_code: str
    created_at: datetime.datetime


class GroupJoin(BaseSerializerModel):
    invite_code: str


class GroupJoinResponse(BaseSerializerModel):
    id: int
    group_id: int
    user_id: int
    leaderboard_score: int
    joined_at: datetime.datetime


class GroupMemberResponse(BaseSerializerModel):
    id: int
    user_id: int
    name: str
    leaderboard_score: int
    joined_at: datetime.datetime
