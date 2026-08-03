"""add chat_messages.trace_id and chat_message_feedbacks table (T-LLM-2-langfuse-user-feedback)

Revision ID: 0062
Revises: 0061
Create Date: 2026-08-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.create_table(
        "chat_message_feedbacks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("value", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_chat_message_feedbacks_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("message_id", name="uq_chat_message_feedbacks_message_id"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("chat_message_feedbacks")
    op.drop_column("chat_messages", "trace_id")
