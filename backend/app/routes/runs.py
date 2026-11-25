from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.llm import LLMError
from app.models import Chunk, Claim, Conflict, Evidence, Run, Source, Supersession
from app.pipeline.graph import run_pipeline
from app.pipeline.run_state import mark_completed, mark_failed

router = APIRouter(prefix="/runs", tags=["runs"])


class RunRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


def execute_run(run_id: int, question: str) -> None:
    """Run the pipeline on its own session; any failure ends the run `failed`."""
    db = SessionLocal()
    try:
        try:
            state = run_pipeline(db, run_id, question)
        except LLMError as exc:
            db.rollback()
            mark_failed(db, run_id, "LLM error: {}".format(exc))
        except Exception as exc:  # noqa: BLE001 - a pipeline failure must fail the run
            db.rollback()
            mark_failed(db, run_id, "Pipeline error: {}".format(exc))
        else:
            if not state.get("failed"):
                mark_completed(db, run_id)
    except Exception as exc:  # noqa: BLE001 - never leave a run in flight
        db.rollback()
        mark_failed(db, run_id, "Pipeline error: {}".format(exc))
    finally:
        db.close()


@router.post("", status_code=202)
def create_run(
    body: RunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Queue a run and return its id immediately; the graph runs in the background."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")

    run = Run(question=question, status="queued")
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(execute_run, run.id, question)
    return {"id": run.id, "status": run.status}


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    """A run with its claims, evidence, conflicts and supersessions."""
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    claims = db.scalars(
        select(Claim).where(Claim.run_id == run_id).order_by(Claim.id)
    ).all()
    claim_ids = [claim.id for claim in claims]

    evidence_rows = db.execute(
        select(Evidence, Chunk.source_id, Source.title)
        .join(Chunk, Chunk.id == Evidence.chunk_id)
        .join(Source, Source.id == Chunk.source_id)
        .where(Evidence.claim_id.in_(claim_ids))
        .order_by(Evidence.claim_id, Evidence.id)
    ).all()

    evidence_by_claim: Dict[int, List[Dict[str, Any]]] = {claim_id: [] for claim_id in claim_ids}
    for evidence, source_id, source_title in evidence_rows:
        evidence_by_claim[evidence.claim_id].append(
            {
                "chunk_id": evidence.chunk_id,
                "source_id": source_id,
                "source_title": source_title,
                "quote": evidence.quote,
                "role": evidence.role,
            }
        )

    conflicts = db.scalars(select(Conflict).where(Conflict.run_id == run_id)).all()
    supersessions = db.scalars(
        select(Supersession).where(Supersession.run_id == run_id)
    ).all()

    return {
        "id": run.id,
        "question": run.question,
        "status": run.status,
        "demo": run.demo,
        "error": run.error,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "claims": [
            {
                "id": claim.id,
                "text": claim.text,
                "claim_date": claim.claim_date,
                "owner": claim.owner,
                "status": claim.status,
                "confidence": claim.confidence,
                "uncertainty_note": claim.uncertainty_note,
                "evidence": evidence_by_claim.get(claim.id, []),
            }
            for claim in claims
        ],
        "conflicts": [
            {
                "claim_a_id": conflict.claim_a_id,
                "claim_b_id": conflict.claim_b_id,
                "reason": conflict.reason,
            }
            for conflict in conflicts
        ],
        "supersessions": [
            {
                "old_claim_id": supersession.old_claim_id,
                "new_claim_id": supersession.new_claim_id,
                "reason": supersession.reason,
            }
            for supersession in supersessions
        ],
    }
