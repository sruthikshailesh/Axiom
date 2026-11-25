"""Node 1: find the chunks that could answer the question."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk, Source
from app.pipeline.run_state import mark_failed
from app.search import search_chunks

LIMIT = 12

# Fallback for the synthetic demo corpus (NOTES, Phase 5b): if full-text search
# returns fewer than four demo sources, one chunk per missing source is added.
DEMO_TITLE_PREFIX = "[SYNTHETIC DEMO DATA]"
DEMO_SOURCE_TARGET = 4


def _chunk_payload(chunk: Chunk, source: Source) -> Dict[str, Any]:
    return {
        "chunk_id": chunk.id,
        "source_id": chunk.source_id,
        "position": chunk.position,
        "text": chunk.text,
        "source_title": source.title,
        "doc_date": source.doc_date.isoformat() if source.doc_date else None,
        "author": source.author,
    }


def _add_missing_demo_chunks(
    db: Session, chunks: List[Dict[str, Any]]
) -> List[str]:
    """Add the top chunk of every demo source the search did not return."""
    demo_sources = db.scalars(
        select(Source)
        .where(Source.title.like(DEMO_TITLE_PREFIX + "%"))
        .order_by(Source.id)
    ).all()
    if not demo_sources:
        return []

    retrieved = {chunk["source_id"] for chunk in chunks}
    demo_ids = {source.id for source in demo_sources}
    if not retrieved & demo_ids or len(retrieved & demo_ids) >= DEMO_SOURCE_TARGET:
        return []

    added: List[str] = []
    for source in demo_sources:
        if source.id in retrieved:
            continue
        first = db.scalars(
            select(Chunk)
            .where(Chunk.source_id == source.id)
            .order_by(Chunk.position, Chunk.id)
        ).first()
        if first is None:
            continue
        chunks.append(_chunk_payload(first, source))
        added.append(source.title)
    return added


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

    log = ["researcher: retrieved {} chunks".format(len(chunks))]
    added = _add_missing_demo_chunks(db, chunks)
    if added:
        log.append(
            "researcher: demo fallback added the top chunk from {} unretrieved "
            "demo source(s)".format(len(added))
        )

    return {"chunks": chunks, "failed": False, "log": log}
