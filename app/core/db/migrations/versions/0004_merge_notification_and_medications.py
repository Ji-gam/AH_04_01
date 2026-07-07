"""merge: notification_schedules and medications branches

Revision ID: 0004
Revises: 0003, 3d9e8983a475
Create Date: 2026-07-07 18:17:11.303082

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = ("0003", "3d9e8983a475")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
