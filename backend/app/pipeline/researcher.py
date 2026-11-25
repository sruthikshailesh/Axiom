"""Node 1: find the chunks that could answer the question."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source
from app.pipeline.run_state import mark_failed
from app.search import search_chunks

LIMIT = 12


def researcher_node(state: Dict[str, Any], db: Session) -> Dict[str, Any]:
    rows = search_chunks(db, state["question"], limit=LIMIT)
    if not rows:
        mark_failed(db, state["run_id"], "No relevant documents found")
        return {
            "chunks": [],
            "failed": True,
            "log": ["researcher: no chunks matched the question"],
        }

    source_ids = {row.source_id for row in rows}
    sources = {
        source.id: source
        for source in db.scalars(select(Source).where(Source.id.in_(source_ids))).all()
    }

    chunks: List[Dict[str, Any]] = []
    for row in rows:
        source = sources.get(row.source_id)
        chunks.append(
            {
                "chunk_id": row.id,
                "source_id": row.source_id,
                "position": row.position,
                "text": row.text,
                "source_title": source.title if source else "unknown",
                "doc_date": source.doc_date.isoformat() if source and source.doc_date else None,
                "author": source.author if source else None,
            }
        )

    return {
        "chunks": chunks,
        "failed": False,
        "log": ["researcher: retrieved {} chunks".format(len(chunks))],
    }
