from __future__ import annotations

from typing import Any, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Chunk


def search_chunks(db: Session, query: str, limit: int = 10) -> List[Any]:
    """Full-text search over chunks, best match first.

    Reused by the Phase 3 Researcher. Returns rows of
    (id, source_id, position, text, rank).
    """
    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank(Chunk.tsv, tsquery).label("rank")

    stmt = (
        select(Chunk.id, Chunk.source_id, Chunk.position, Chunk.text, rank)
        .where(Chunk.tsv.op("@@")(tsquery))
        .order_by(rank.desc(), Chunk.id)
        .limit(limit)
    )

    return db.execute(stmt).all()
