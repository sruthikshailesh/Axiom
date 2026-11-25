from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.demo import DEMO_QUESTION, load_demo
from app.models import Run
from app.routes.runs import execute_run

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/run", status_code=202)
def create_demo_run(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Load the synthetic corpus and queue the preset demo question."""
    load_demo(db)

    run = Run(question=DEMO_QUESTION, status="queued", demo=True)
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(execute_run, run.id, DEMO_QUESTION)
    return {"id": run.id, "status": run.status, "demo": True}
