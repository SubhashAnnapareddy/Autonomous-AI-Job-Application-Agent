"""normalize application tracking status

Revision ID: d7f8a9b0c1d2
Revises: c1a2b3c4d5e6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "c1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE applications SET status = 'ready' WHERE status = 'review'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE applications SET status = 'review' WHERE status = 'ready'"
        )
    )
