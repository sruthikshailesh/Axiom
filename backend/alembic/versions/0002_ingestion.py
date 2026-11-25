"""ingestion

Revision ID: 0002_ingestion
Revises: 0001_initial
Create Date: 2026-11-25

Source documents and their searchable chunks.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_ingestion"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=True),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "chunk",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey("source.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=False,
        ),
    )

    op.create_index("ix_chunk_tsv", "chunk", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_chunk_source_id_position", "chunk", ["source_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_source_id_position", table_name="chunk")
    op.drop_index("ix_chunk_tsv", table_name="chunk")
    op.drop_table("chunk")
    op.drop_table("source")
