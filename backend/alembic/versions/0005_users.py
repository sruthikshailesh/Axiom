"""local user accounts

Revision ID: 0005_users
Revises: 0004_demo_flag
Create Date: 2026-11-26

Adds the accounts created from the sign-in screen. The account in `.env` keeps
working as a fallback and is not stored here.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_users"
down_revision = "0004_demo_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("app_user")
