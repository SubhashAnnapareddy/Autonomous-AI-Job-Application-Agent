"""improve application tracking and job uniqueness

Revision ID: c1a2b3c4d5e6
Revises: b4f9d1e2c733
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "b4f9d1e2c733"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "applications",
        "applied_at",
        existing_type=sa.DateTime(),
        nullable=True,
    )
    op.create_unique_constraint(
        "uq_jobs_platform_source_id",
        "jobs",
        ["platform", "source_job_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_jobs_platform_source_id",
        "jobs",
        type_="unique",
    )
    op.alter_column(
        "applications",
        "applied_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )
