"""Run status transitions, so a run can never be left in "running"."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Run

TERMINAL_STATUSES = ("completed", "failed")
ACTIVE_STATUSES = ("queued", "researching", "extracting", "verifying")

# A run older than this that is still active is reported as timed out.
RUN_TIMEOUT = timedelta(minutes=10)
TIMEOUT_ERROR = "Run timed out."
INTERRUPTED_ERROR = "Interrupted before completion. Start the run again."


def _finish(db: Session, run: Optional[Run], status: str, error: Optional[str]) -> None:
    if run is None:
        return
    run.status = status
    run.error = error
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def mark_completed(db: Session, run_id: int) -> None:
    _finish(db, db.get(Run, run_id), "completed", None)


def mark_failed(db: Session, run_id: int, error: str) -> None:
    _finish(db, db.get(Run, run_id), "failed", error)


def mark_status(db: Session, run_id: int, status: str) -> None:
    """Record an in-flight stage. A failed or completed run is never reopened."""
    run = db.get(Run, run_id)
    if run is None or run.status in TERMINAL_STATUSES:
        return
    run.status = status
    db.commit()


def sweep_interrupted_runs(db: Session) -> int:
    """Fail runs left active by a process that went away.

    Called once on application startup: a run in an active status at that moment
    lost its background task with the old process, so it can never finish.
    Completed and already-failed runs are never touched.
    """
    stuck = db.scalars(select(Run).where(Run.status.in_(ACTIVE_STATUSES))).all()
    now = datetime.now(timezone.utc)
    for run in stuck:
        run.status = "failed"
        run.error = INTERRUPTED_ERROR
        run.finished_at = now
    if stuck:
        db.commit()
    return len(stuck)


def expire_if_stale(db: Session, run: Run) -> bool:
    """Mark an active run failed once it is older than RUN_TIMEOUT.

    A read-time check, not a background job: the next GET of a stuck run repairs
    it. Returns True when the run was just expired.
    """
    if run.status not in ACTIVE_STATUSES or run.created_at is None:
        return False

    started = run.created_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - started <= RUN_TIMEOUT:
        return False

    _finish(db, run, "failed", TIMEOUT_ERROR)
    return True
