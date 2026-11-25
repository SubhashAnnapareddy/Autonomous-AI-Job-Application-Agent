"""add full name to applicant profile

Revision ID: e8f1a2b3c4d5
Revises: d7f8a9b0c1d2
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("full_name", sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "full_name")
