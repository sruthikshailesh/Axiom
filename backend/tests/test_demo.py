from __future__ import annotations

import app.llm as llm
from sqlalchemy import func, select

from app.demo import DEMO_DOCUMENTS, DEMO_QUESTION, load_demo
from app.models import Chunk, Source
from app.pipeline.researcher import DEMO_TITLE_PREFIX, researcher_node

# Reuse the fake provider from the pipeline tests: no real LLM call is made.
from test_pipeline import _wait_for_run, fake_llm


def _demo_source_count(db) -> int:
    return db.execute(
        select(func.count())
        .select_from(Source)
        .where(Source.title.like("[SYNTHETIC DEMO DATA]%"))
    ).scalar_one()


def test_load_demo_twice_keeps_four_sources(db) -> None:
    first = load_demo(db)
    second = load_demo(db)

    assert len(first) == 4, first
    assert first == second, "the second load must reuse the existing sources"
    assert _demo_source_count(db) == 4, "four demo sources, not eight"

    titles = db.scalars(
        select(Source.title).where(Source.title.like("[SYNTHETIC DEMO DATA]%"))
    ).all()
    assert sorted(titles) == sorted(document["title"] for document in DEMO_DOCUMENTS)
    assert all(title.startswith("[SYNTHETIC DEMO DATA]") for title in titles)


def test_demo_run_uses_the_preset_question(client, monkeypatch) -> None:
    monkeypatch.setattr(llm, "complete_json", fake_llm("supports"))

    created = client.post("/demo/run")
    assert created.status_code == 202, created.text
    payload = created.json()
    assert payload["status"] == "queued"
    assert payload["demo"] is True

    detail = _wait_for_run(client, payload["id"])
    assert detail["status"] == "completed", detail
    assert detail["question"] == DEMO_QUESTION
    assert detail["demo"] is True

    demo_sources = [
        source
        for source in client.get("/sources").json()
        if source["title"].startswith("[SYNTHETIC DEMO DATA]")
    ]
    assert len(demo_sources) == 4, demo_sources


def test_demo_chunks_exist_and_retrieval_covers_all_four_sources(
    client, db, monkeypatch
) -> None:
    """Every demo document is chunked, and the Researcher returns all four."""
    load_demo(db)

    demo_sources = db.scalars(
        select(Source)
        .where(Source.title.like(DEMO_TITLE_PREFIX + "%"))
        .order_by(Source.id)
    ).all()
    assert len(demo_sources) == 4, [source.title for source in demo_sources]

    stored = db.execute(
        select(Chunk.source_id, func.count())
        .where(Chunk.source_id.in_([source.id for source in demo_sources]))
        .group_by(Chunk.source_id)
    ).all()
    chunk_counts = {source_id: count for source_id, count in stored}
    for source in demo_sources:
        assert chunk_counts.get(source.id, 0) >= 1, source.title
        assert source.chunks, source.title

    state = researcher_node(
        {"run_id": 0, "question": DEMO_QUESTION, "chunks": [], "log": []}, db
    )
    assert state["failed"] is False, state
    retrieved_titles = {chunk["source_title"] for chunk in state["chunks"]}
    for source in demo_sources:
        assert source.title in retrieved_titles, (source.title, sorted(retrieved_titles))

    # The demo run itself still goes through the real graph with the fake LLM.
    monkeypatch.setattr(llm, "complete_json", fake_llm("supports"))
    created = client.post("/demo/run")
    assert created.status_code == 202, created.text
    detail = _wait_for_run(client, created.json()["id"])
    assert detail["status"] == "completed", detail
