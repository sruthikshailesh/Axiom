"""pipeline

Revision ID: 0003_pipeline
Revises: 0002_ingestion
Create Date: 2026-11-25

Runs, claims, evidence, conflicts and supersessions.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_pipeline"
down_revision = "0002_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "claim",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("claim_date", sa.Date(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("confidence", sa.REAL(), nullable=False),
        sa.Column("uncertainty_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('verified', 'conflict', 'uncertain', 'superseded')",
            name="ck_claim_status",
        ),
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "claim_id",
            sa.BigInteger(),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            sa.BigInteger(),
            sa.ForeignKey("chunk.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "role IN ('supports', 'contradicts')", name="ck_evidence_role"
        ),
    )

    op.create_table(
        "conflict",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "claim_a_id",
            sa.BigInteger(),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "claim_b_id",
            sa.BigInteger(),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
    )

    op.create_table(
        "supersession",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "old_claim_id",
            sa.BigInteger(),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "new_claim_id",
            sa.BigInteger(),
            sa.ForeignKey("claim.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("supersession")
    op.drop_table("conflict")
    op.drop_table("evidence")
    op.drop_table("claim")
    op.drop_table("run")
