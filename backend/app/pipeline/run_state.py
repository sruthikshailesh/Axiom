"""Run status transitions, so a run can never be left in "running"."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Run

TERMINAL_STATUSES = ("completed", "failed")


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
