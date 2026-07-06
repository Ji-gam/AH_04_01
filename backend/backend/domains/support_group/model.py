# backend/domains/support_group/model.py
# API_Specification_v3.pdf [M3] SUPPORT_GROUPS, GROUP_MEMBERS
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base


class SupportGroup(Base):
    __tablename__ = "support_groups"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_name = Column(String(100), nullable=False)
    invite_code = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("support_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    leaderboard_score = Column(Integer, default=0)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)

    group = relationship("SupportGroup", back_populates="members")
    user = relationship("User", back_populates="group_memberships")
