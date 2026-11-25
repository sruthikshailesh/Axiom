from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi.testclient import TestClient

import app.llm as llm
from app.llm import (
    BAD_KEY_MESSAGE,
    BAD_RESPONSE_MESSAGE,
    DEFAULT_PUBLIC_MESSAGE,
    RATE_LIMIT_MESSAGE,
    UNAVAILABLE_MESSAGE,
    _public_message_for,
)
from app.main import UNHANDLED_ERROR_MESSAGE, app
from app.models import Run
from app.pipeline.run_state import INTERRUPTED_ERROR, TIMEOUT_ERROR


def _make_run(db, status: str, created_at: Optional[datetime] = None) -> int:
    run = Run(question="Hardening check question", status=status)
    if created_at is not None:
        run.created_at = created_at
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.id


def test_startup_sweep_fails_only_interrupted_runs(db) -> None:
    """Runs left active by a dead process fail on startup; finished ones do not."""
    extracting_id = _make_run(db, "extracting")
    queued_id = _make_run(db, "queued")
    completed_id = _make_run(db, "completed")
    failed_id = _make_run(db, "failed")

    # A new process start is exactly what the lifespan hook sees on uvicorn boot.
    with TestClient(app):
        pass

    db.expire_all()
    extracting = db.get(Run, extracting_id)
    queued = db.get(Run, queued_id)
    completed = db.get(Run, completed_id)
    failed = db.get(Run, failed_id)

    assert extracting.status == "failed"
    assert extracting.error == INTERRUPTED_ERROR
    assert extracting.finished_at is not None

    assert queued.status == "failed"
    assert queued.error == INTERRUPTED_ERROR

    assert completed.status == "completed"
    assert completed.error is None

    assert failed.status == "failed"


def test_stale_run_is_failed_when_read(client, db) -> None:
    """A run active for over 10 minutes is reported failed by GET /runs/{id}."""
    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    stale_id = _make_run(db, "researching", created_at=old)
    fresh_id = _make_run(db, "researching")

    stale = client.get("/runs/{}".format(stale_id)).json()
    assert stale["status"] == "failed"
    assert stale["error"] == TIMEOUT_ERROR
    assert stale["finished_at"] is not None

    fresh = client.get("/runs/{}".format(fresh_id)).json()
    assert fresh["status"] == "researching"
    assert fresh["error"] is None


def test_completed_run_is_never_timed_out(client, db) -> None:
    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    completed_id = _make_run(db, "completed", created_at=old)

    detail = client.get("/runs/{}".format(completed_id)).json()
    assert detail["status"] == "completed"
    assert detail["error"] is None


def test_llm_failure_stores_only_the_readable_message(client, monkeypatch) -> None:
    """The run's error is the user-facing sentence; the provider body stays logged."""
    from test_pipeline import _upload, _wait_for_run

    # Its own vocabulary, so this source cannot be retrieved by another test's
    # question (the test database is only truncated once per session).
    _upload(
        client,
        "zeppelin.txt",
        "The zeppelin hangar is 210 metres wide and stands beside the airfield.",
        "Zeppelin note",
        "Panel Z",
    )

    def boom(system: str, user: str, schema_hint: str):
        raise llm.LLMError(
            "LLM provider returned HTTP 401: {'error': 'invalid api key sk-should-not-leak'}",
            BAD_KEY_MESSAGE,
        )

    monkeypatch.setattr(llm, "complete_json", boom)

    created = client.post(
        "/runs", json={"question": "How wide is the zeppelin hangar?"}
    )
    detail = _wait_for_run(client, created.json()["id"])

    assert detail["status"] == "failed"
    assert detail["error"] == BAD_KEY_MESSAGE
    assert "sk-should-not-leak" not in detail["error"]
    assert "HTTP 401" not in detail["error"]


def test_provider_failures_map_to_readable_messages() -> None:
    assert _public_message_for(401, "") == BAD_KEY_MESSAGE
    assert _public_message_for(403, "") == BAD_KEY_MESSAGE
    assert _public_message_for(429, "") == RATE_LIMIT_MESSAGE
    assert _public_message_for(500, "") == UNAVAILABLE_MESSAGE
    assert _public_message_for(400, "json_validate_failed") == BAD_RESPONSE_MESSAGE
    assert _public_message_for(400, "other problem") == DEFAULT_PUBLIC_MESSAGE


def test_unhandled_exception_returns_readable_json(monkeypatch) -> None:
    import app.routes.search as search_routes

    def boom(*args, **kwargs):
        raise RuntimeError("database exploded at 127.0.0.1:5432")

    monkeypatch.setattr(search_routes, "search_chunks", boom)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/search", params={"q": "ionosphere"})

    assert response.status_code == 500
    assert response.json() == {"detail": UNHANDLED_ERROR_MESSAGE}
    assert "exploded" not in response.text
    assert "Traceback" not in response.text
