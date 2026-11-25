from __future__ import annotations

import app.llm as llm
from sqlalchemy import func, select

from app.demo import DEMO_DOCUMENTS, DEMO_QUESTION, load_demo
from app.models import Source

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
