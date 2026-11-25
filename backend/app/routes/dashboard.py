from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Conflict, Run, Source

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

RECENT_RUN_LIMIT = 5


def _run_summary(run: Run) -> dict:
    """Run metadata only: a question, a status and timestamps."""
    return {
        "id": run.id,
        "question": run.question,
        "status": run.status,
        "demo": run.demo,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    """Counts for the dashboard. No document text is returned."""
    source_count = db.scalar(select(func.count()).select_from(Source)) or 0
    run_count = db.scalar(select(func.count()).select_from(Run)) or 0
    runs_with_conflict = (
        db.scalar(select(func.count(func.distinct(Conflict.run_id)))) or 0
    )

    recent = db.scalars(
        select(Run).order_by(Run.created_at.desc(), Run.id.desc()).limit(RECENT_RUN_LIMIT)
    ).all()

    latest_status = recent[0].status if recent else None

    return {
        "sources": source_count,
        "runs": run_count,
        "runs_with_conflict": runs_with_conflict,
        "latest_run_status": latest_status,
        "recent_runs": [_run_summary(run) for run in recent],
    }
