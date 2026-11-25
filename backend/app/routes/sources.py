from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingest.chunk import chunk_text
from app.ingest.extract import ExtractionError, UnsupportedFileType, extract_text
from app.models import Chunk, Source

router = APIRouter(prefix="/sources", tags=["sources"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("")
def create_source(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    doc_date: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Extract a document, chunk it, and store source + chunks atomically."""
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 10 MB.")

    filename = file.filename or "untitled"
    try:
        text = extract_text(filename, content)
        if not text.strip():
            raise ExtractionError("File contains no extractable text.")
        chunks = chunk_text(text)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=415, detail=str(exc))
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    parsed_date = None
    if doc_date:
        try:
            parsed_date = date.fromisoformat(doc_date)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="doc_date must be an ISO date (YYYY-MM-DD)."
            )

    source = Source(
        title=title or filename,
        filename=filename,
        doc_date=parsed_date,
        author=author,
    )
    source.chunks = [Chunk(position=i, text=t) for i, t in enumerate(chunks)]

    db.add(source)
    db.commit()
    db.refresh(source)

    return {"id": source.id, "title": source.title, "chunk_count": len(source.chunks)}


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    """All sources with their chunk counts, newest first."""
    rows = db.execute(
        select(Source, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.source_id == Source.id)
        .group_by(Source.id)
        .order_by(Source.uploaded_at.desc(), Source.id.desc())
    ).all()

    return [
        {
            "id": source.id,
            "title": source.title,
            "filename": source.filename,
            "doc_date": source.doc_date,
            "author": source.author,
            "uploaded_at": source.uploaded_at,
            "chunk_count": chunk_count,
        }
        for source, chunk_count in rows
    ]


@router.get("/{source_id}/chunks")
def list_chunks(source_id: int, db: Session = Depends(get_db)):
    """Chunks of one source in position order."""
    if db.get(Source, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found.")

    chunks = db.scalars(
        select(Chunk)
        .where(Chunk.source_id == source_id)
        .order_by(Chunk.position)
    ).all()

    return [
        {
            "id": chunk.id,
            "source_id": chunk.source_id,
            "position": chunk.position,
            "text": chunk.text,
        }
        for chunk in chunks
    ]
