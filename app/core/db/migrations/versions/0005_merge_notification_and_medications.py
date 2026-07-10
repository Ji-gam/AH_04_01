"""merge: notification_schedules and medications branches

Revision ID: 0005
Revises: 0003, 0004
Create Date: 2026-07-07 18:17:11.303082

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = ("0003", "0004")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
