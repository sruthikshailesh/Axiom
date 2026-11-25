from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Tuple

import pytest

import app.llm as llm

SOURCE_A = (
    "The ionosphere begins at about 48 km altitude over the Earth's surface.\n"
    "It reflects radio waves and makes long distance radio communication possible."
)
SOURCE_B = (
    "The ionosphere begins near 48 km altitude above the ground.\n"
    "At night it reflects long radio waves much further than during the day."
)

TERMINAL_STATUSES = {"completed", "failed"}
CHUNK_PATTERN = re.compile(
    r"--- chunk_id=(\d+) \(source: [^)]*\) ---\n(.*?)(?=\n--- chunk_id=|\Z)", re.S
)


def _chunks_from_prompt(user: str) -> List[Tuple[int, str]]:
    return [
        (int(match.group(1)), match.group(2).strip())
        for match in CHUNK_PATTERN.finditer(user)
    ]


def _wait_for_run(client, run_id: int, timeout: float = 10.0) -> Dict[str, Any]:
    """Poll the run until it leaves the queued/researching/extracting/verifying set."""
    deadline = time.time() + timeout
    detail: Dict[str, Any] = {}
    while time.time() < deadline:
        detail = client.get("/runs/{}".format(run_id)).json()
        if detail.get("status") in TERMINAL_STATUSES:
            return detail
        time.sleep(0.02)
    pytest.fail("run {} never finished: {}".format(run_id, detail))


def fake_llm(relation: str = "supports", paraphrase: bool = False):
    """Returns fixed JSON: one claim per retrieved chunk, quotes verbatim."""

    def complete_json(system: str, user: str, schema_hint: str) -> Dict[str, Any]:
        if "relation" in schema_hint:
            return {
                "relation": relation,
                "reason": "Both describe the same altitude.",
                "newer": None,
            }

        claims = []
        for chunk_id, text in _chunks_from_prompt(user):
            quote = " ".join(text.split()[:10])
            if paraphrase:
                quote = "The ionosphere starts roughly 48 kilometres up."
            claims.append(
                {
                    "text": quote,
                    "claim_date": "2024-01-01",
                    "owner": "Ionosphere Panel",
                    "supporting": [{"chunk_id": chunk_id, "quote": quote}],
                }
            )
        return {"claims": claims}

    return complete_json


def _upload(client, filename: str, text: str, title: str, author: str) -> int:
    response = client.post(
        "/sources",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
        data={"title": title, "doc_date": "2024-01-01", "author": author},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


@pytest.fixture()
def two_sources(client) -> List[int]:
    return [
        _upload(client, "a.txt", SOURCE_A, "Source A", "Panel A"),
        _upload(client, "b.txt", SOURCE_B, "Source B", "Panel B"),
    ]


def test_pipeline_stores_claims_with_evidence(client, two_sources, monkeypatch) -> None:
    monkeypatch.setattr(llm, "complete_json", fake_llm("supports"))

    created = client.post(
        "/runs", json={"question": "At what altitude does the ionosphere begin?"}
    )
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "queued", "the run is queued before the graph runs"

    detail = _wait_for_run(client, created.json()["id"])
    assert detail["status"] == "completed"
    assert detail["claims"], "expected at least one stored claim"

    chunk_texts = {}
    for source_id in two_sources:
        for chunk in client.get("/sources/{}/chunks".format(source_id)).json():
            chunk_texts[chunk["id"]] = chunk["text"]

    # The two sources agree, so the shared-topic pair verifies at 0.9.
    assert {claim["status"] for claim in detail["claims"]} == {"verified"}, [
        (c["text"], c["status"], c["confidence"], c["uncertainty_note"], len(c["evidence"]))
        for c in detail["claims"]
    ]

    for claim in detail["claims"]:
        assert claim["status"] in {"verified", "conflict", "uncertain", "superseded"}
        assert claim["confidence"] in {0.8, 0.9}
        assert 0.0 <= claim["confidence"] <= 1.0
        assert claim["evidence"], "every surviving claim has evidence"
        for evidence in claim["evidence"]:
            assert evidence["quote"] in chunk_texts[evidence["chunk_id"]]


def test_paraphrased_quotes_are_dropped(client, two_sources, monkeypatch) -> None:
    monkeypatch.setattr(llm, "complete_json", fake_llm("supports", paraphrase=True))

    created = client.post(
        "/runs", json={"question": "Why does the ionosphere reflect radio waves?"}
    )
    assert created.status_code == 202, created.text

    detail = _wait_for_run(client, created.json()["id"])
    assert detail["status"] == "completed"
    assert detail["claims"] == []


def test_missing_api_key_fails_the_run(client, two_sources, monkeypatch) -> None:
    # Settings are read once at import (from the environment and backend/.env),
    # so the missing key is simulated on the settings object, not os.environ.
    from app.config import settings
    from app.llm import MISSING_KEY_MESSAGE

    monkeypatch.setattr(settings, "llm_api_key", None)

    created = client.post(
        "/runs", json={"question": "At what altitude does the ionosphere begin?"}
    )
    assert created.status_code == 202, created.text

    detail = _wait_for_run(client, created.json()["id"])
    assert detail["status"] == "failed"
    # The run carries a readable sentence, never the raw provider or config text.
    assert detail["error"] == MISSING_KEY_MESSAGE
    assert "LLM_API_KEY is not set" not in detail["error"]


def test_stages_are_reported_while_the_run_is_in_flight(client, two_sources, monkeypatch) -> None:
    """The graph publishes researching/extracting/verifying before it finishes."""
    from app.db import SessionLocal
    from app.models import Run
    from app.pipeline.graph import run_pipeline

    seen: List[str] = []

    def recording(system: str, user: str, schema_hint: str) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            seen.append(db.get(Run, run_id).status)
        finally:
            db.close()
        return fake_llm("supports")(system, user, schema_hint)

    db = SessionLocal()
    try:
        run = Run(question="At what altitude does the ionosphere begin?", status="queued")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    finally:
        db.close()

    monkeypatch.setattr(llm, "complete_json", recording)

    db = SessionLocal()
    try:
        state = run_pipeline(db, run_id, "At what altitude does the ionosphere begin?")
    finally:
        db.close()

    assert state.get("failed") is not True
    # LLM calls happen in the extractor and the verifier.
    assert seen[0] == "extracting", seen


def test_empty_question_is_rejected(client) -> None:
    assert client.post("/runs", json={"question": ""}).status_code == 422
    assert client.post("/runs", json={"question": "   "}).status_code == 422


def test_unknown_run_is_404(client) -> None:
    assert client.get("/runs/999999").status_code == 404
