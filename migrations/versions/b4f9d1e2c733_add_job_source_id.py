"""add external job source identifiers

Revision ID: b4f9d1e2c733
Revises: 7e0b3c1a2f44
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4f9d1e2c733"
down_revision: Union[str, Sequence[str], None] = "7e0b3c1a2f44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("source_job_id", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_jobs_source_job_id",
        "jobs",
        ["source_job_id"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_source_job_id", table_name="jobs")
    op.drop_column("jobs", "source_job_id")
