"""add resume analysis fields

Revision ID: 7e0b3c1a2f44
Revises: 29f50952c674
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e0b3c1a2f44"
down_revision: Union[str, Sequence[str], None] = "29f50952c674"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("analysis_json", sa.JSON(), nullable=True))
    op.add_column("resumes", sa.Column("analyzed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("resumes", "analyzed_at")
    op.drop_column("resumes", "analysis_json")
