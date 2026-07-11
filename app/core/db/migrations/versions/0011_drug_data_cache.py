"""drug_data_cache: T-LLM-2-drug-gateway drug_data() 외부 API write-back 캐시 테이블

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drug_data_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("query_name", sa.String(length=150), nullable=False),
        sa.Column("profiles", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_name", name="uq_drug_data_cache_query_name"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("drug_data_cache")
