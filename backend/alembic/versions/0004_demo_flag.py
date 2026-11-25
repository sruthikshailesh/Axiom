"""demo flag on run

Revision ID: 0004_demo_flag
Revises: 0003_pipeline
Create Date: 2026-11-25

Marks a run that was created from the synthetic demo corpus.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_demo_flag"
down_revision = "0003_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run",
        sa.Column("demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("run", "demo")
