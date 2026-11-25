from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.search import search_chunks

router = APIRouter(tags=["search"])


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Testing surface for the full-text search helper."""
    return [
        {
            "chunk_id": row.id,
            "source_id": row.source_id,
            "position": row.position,
            "text": row.text,
            "rank": float(row.rank),
        }
        for row in search_chunks(db, q, limit)
    ]
