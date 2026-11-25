"""Synthetic demo corpus for "Lantern Search", a fictional project.

The four documents are plain .txt files in backend/demo/. They are ingested with
the same extractor and chunker as an upload, so the demo exercises the real
ingestion path. Every title carries the [SYNTHETIC DEMO DATA] marker.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.chunk import chunk_text
from app.ingest.extract import ExtractionError, extract_text
from app.models import Chunk, Source

DEMO_DIR = Path(__file__).resolve().parents[1] / "demo"

DEMO_DOCUMENTS: List[Dict[str, Any]] = [
    {
        "filename": "doc_a_architecture.txt",
        "title": "[SYNTHETIC DEMO DATA] Lantern Architecture v1",
        "doc_date": "2026-01-10",
        "author": "Tech Lead",
    },
    {
        "filename": "doc_b_planning_meeting.txt",
        "title": "[SYNTHETIC DEMO DATA] Lantern Planning Meeting",
        "doc_date": "2026-02-05",
        "author": "Tech Lead",
    },
    {
        "filename": "doc_c_status_note.txt",
        "title": "[SYNTHETIC DEMO DATA] Lantern Status Note",
        "doc_date": "2026-02-05",
        "author": "Developer",
    },
    {
        "filename": "doc_d_open_issue.txt",
        "title": "[SYNTHETIC DEMO DATA] Lantern Open Issue",
        "doc_date": "2026-03-10",
        "author": "QA Lead",
    },
]

DEMO_QUESTION = (
    "What search technology does this project currently use, "
    "and why was the original decision changed?"
)


def load_demo(db: Session) -> List[int]:
    """Ingest the demo documents and return their source ids.

    Idempotent: a source whose title already exists is reused, so running the
    demo twice never duplicates a document.
    """
    source_ids: List[int] = []

    for document in DEMO_DOCUMENTS:
        title = document["title"]
        existing = db.scalars(select(Source).where(Source.title == title)).first()
        if existing is not None:
            source_ids.append(existing.id)
            continue

        path = DEMO_DIR / document["filename"]
        content = path.read_bytes()
        text = extract_text(document["filename"], content)
        if not text.strip():
            raise ExtractionError("Demo file {} has no text.".format(path.name))

        source = Source(
            title=title,
            filename=document["filename"],
            doc_date=date.fromisoformat(document["doc_date"]),
            author=document["author"],
        )
        source.chunks = [
            Chunk(position=position, text=chunk)
            for position, chunk in enumerate(chunk_text(text))
        ]

        db.add(source)
        db.commit()
        db.refresh(source)
        source_ids.append(source.id)

    return source_ids
