from __future__ import annotations

from sqlalchemy import select

from app.models import Chunk, Source
from pdf_utils import make_blank_pdf, make_text_pdf

TXT_BODY = (
    b"AXIOM ingestion test. The quick brown fox jumps over the lazy dog. "
    b"A zephyrology note follows."
)


def _upload(client, filename, content, content_type, **fields):
    return client.post(
        "/sources",
        files={"file": (filename, content, content_type)},
        data=fields,
    )


def test_upload_txt_stores_source_and_chunks(client, db):
    response = _upload(
        client,
        "notes.txt",
        TXT_BODY,
        "text/plain",
        title="Field Notes",
        doc_date="2026-01-15",
        author="Tester",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] > 0
    assert body["title"] == "Field Notes"
    assert body["chunk_count"] > 0

    source = db.get(Source, body["id"])
    assert source is not None
    assert source.filename == "notes.txt"
    assert source.doc_date.isoformat() == "2026-01-15"
    assert source.author == "Tester"

    chunks = db.scalars(
        select(Chunk).where(Chunk.source_id == source.id).order_by(Chunk.position)
    ).all()
    assert len(chunks) == body["chunk_count"]


def test_upload_pdf_stores_source_and_chunks(client, db):
    pdf = make_text_pdf("Zephyrology is the study of the west wind.")

    response = _upload(client, "paper.pdf", pdf, "application/pdf")

    assert response.status_code == 200
    body = response.json()
    assert body["chunk_count"] >= 1
    assert db.get(Source, body["id"]) is not None


def test_search_returns_chunk_from_uploaded_text(client, db):
    _upload(client, "notes.txt", TXT_BODY, "text/plain")

    response = client.get("/search", params={"q": "zephyrology"})

    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert results[0]["source_id"] > 0
    assert "zephyrology" in results[0]["text"]


def test_blank_pdf_is_rejected_with_422(client):
    response = _upload(client, "scanned.pdf", make_blank_pdf(), "application/pdf")

    assert response.status_code == 422
    assert "no extractable text" in response.json()["detail"]


def test_unsupported_extension_is_rejected_with_415(client):
    response = _upload(client, "memo.docx", b"PK\x03\x04", "application/msword")

    assert response.status_code == 415


def test_missing_source_chunks_is_404(client):
    response = client.get("/sources/999999/chunks")

    assert response.status_code == 404
