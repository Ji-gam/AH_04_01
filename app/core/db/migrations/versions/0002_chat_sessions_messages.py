"""chat: chat_sessions, chat_messages

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], name="fk_chat_sessions_profile_id_profiles"),
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name="fk_chat_messages_session_id_chat_sessions"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
