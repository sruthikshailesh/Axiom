from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Claim, Conflict, Run, Source

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# The dashboard's "Recent runs" table lists ten rows.
RECENT_RUN_LIMIT = 10

CLAIM_STATUSES = ("verified", "conflict", "uncertain", "superseded")


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
    failed_run_count = (
        db.scalar(select(func.count()).select_from(Run).where(Run.status == "failed")) or 0
    )

    # One GROUP BY for every claim status, padded with zeros so the four
    # statuses are always present.
    claim_status_counts = {status: 0 for status in CLAIM_STATUSES}
    for status, count in db.execute(
        select(Claim.status, func.count()).group_by(Claim.status)
    ).all():
        if status in claim_status_counts:
            claim_status_counts[status] = count

    recent = db.scalars(
        select(Run).order_by(Run.created_at.desc(), Run.id.desc()).limit(RECENT_RUN_LIMIT)
    ).all()

    latest = recent[0] if recent else None

    return {
        "sources": source_count,
        "runs": run_count,
        "runs_with_conflict": runs_with_conflict,
        "latest_run_status": latest.status if latest else None,
        "recent_runs": [_run_summary(run) for run in recent],
        "claim_status_counts": claim_status_counts,
        "failed_run_count": failed_run_count,
        "latest_run": (
            {
                "id": latest.id,
                "status": latest.status,
                "question": latest.question,
                "created_at": latest.created_at,
            }
            if latest
            else None
        ),
    }
