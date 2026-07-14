"""add ON DELETE CASCADE to chat_sessions/chat_messages foreign keys

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-14

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 회원탈퇴 시 Profile을 삭제하려는데, chat_sessions/chat_messages가 CASCADE 없이 profiles/
    # chat_sessions를 참조하고 있어서 "Cannot delete or update a parent row" 외래키 오류로
    # 탈퇴 자체가 500으로 실패하던 문제를 고친다. 다른 테이블들(medication_schedules,
    # notification_schedules, diagnosis_entries, family_history_entries)은 이미 처음부터
    # ondelete="CASCADE"로 만들어져 있었다 - chat 쪽만 빠져있었다.
    op.drop_constraint("fk_chat_sessions_profile_id_profiles", "chat_sessions", type_="foreignkey")
    op.create_foreign_key(
        "fk_chat_sessions_profile_id_profiles",
        "chat_sessions",
        "profiles",
        ["profile_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("fk_chat_messages_session_id_chat_sessions", "chat_messages", type_="foreignkey")
    op.create_foreign_key(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_messages_session_id_chat_sessions", "chat_messages", type_="foreignkey")
    op.create_foreign_key(
        "fk_chat_messages_session_id_chat_sessions",
        "chat_messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
    )
    op.drop_constraint("fk_chat_sessions_profile_id_profiles", "chat_sessions", type_="foreignkey")
    op.create_foreign_key(
        "fk_chat_sessions_profile_id_profiles",
        "chat_sessions",
        "profiles",
        ["profile_id"],
        ["id"],
    )
