from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import Chunk, Claim, Conflict, Run, Source


def _claim(run_id: int, text: str, status: str) -> Claim:
    return Claim(run_id=run_id, text=text, status=status, confidence=0.5)


def test_summary_counts_match_the_database(client, db) -> None:
    source = Source(title="Dashboard Source", filename="dashboard.txt")
    source.chunks = [
        Chunk(position=0, text="The dashboard counts sources and runs.")
    ]
    db.add(source)

    older = Run(
        question="An older question",
        status="completed",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    newest = Run(question="The newest question", status="completed")
    db.add_all([older, newest])
    db.commit()
    db.refresh(older)
    db.refresh(newest)

    claim_a = _claim(newest.id, "Elasticsearch is still used.", "conflict")
    claim_b = _claim(newest.id, "Elasticsearch has been dropped.", "conflict")
    db.add_all([claim_a, claim_b])
    db.commit()
    db.refresh(claim_a)
    db.refresh(claim_b)

    db.add(
        Conflict(
            run_id=newest.id,
            claim_a_id=claim_a.id,
            claim_b_id=claim_b.id,
            reason="They cannot both be true.",
        )
    )
    db.commit()

    response = client.get("/dashboard/summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    expected_sources = db.scalar(select(func.count()).select_from(Source))
    expected_runs = db.scalar(select(func.count()).select_from(Run))
    expected_conflict_runs = db.scalar(
        select(func.count(func.distinct(Conflict.run_id)))
    )

    assert summary["sources"] == expected_sources
    assert summary["runs"] == expected_runs
    assert summary["runs_with_conflict"] == expected_conflict_runs
    assert summary["runs_with_conflict"] >= 1
    assert summary["latest_run_status"] == "completed"

    assert len(summary["recent_runs"]) == min(10, expected_runs)
    assert summary["recent_runs"][0]["id"] == newest.id
    assert summary["recent_runs"][-1]["question"] == "An older question"


def test_summary_returns_no_document_text(client) -> None:
    response = client.get("/dashboard/summary")
    assert response.status_code == 200

    summary = response.json()
    assert set(summary) == {
        "sources",
        "runs",
        "runs_with_conflict",
        "latest_run_status",
        "recent_runs",
        "claim_status_counts",
        "failed_run_count",
        "latest_run",
    }
    assert set(summary["claim_status_counts"]) == {
        "verified",
        "conflict",
        "uncertain",
        "superseded",
    }
    assert summary["latest_run"] is None or set(summary["latest_run"]) == {
        "id",
        "status",
        "question",
        "created_at",
    }
    for run in summary["recent_runs"]:
        assert set(run) == {
            "id",
            "question",
            "status",
            "demo",
            "created_at",
            "finished_at",
        }


def test_summary_claim_statuses_failures_and_latest_run_match_the_database(client, db) -> None:
    finished = Run(question="What search technology is in use?", status="completed")
    broken = Run(
        question="A question whose run failed",
        status="failed",
        error="The run failed while processing its documents.",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    db.add_all([finished, broken])
    db.commit()
    db.refresh(finished)

    db.add_all(
        [
            _claim(finished.id, "PostgreSQL full-text search is in use.", "verified"),
            _claim(finished.id, "Elasticsearch is still used.", "conflict"),
            _claim(finished.id, "An index will be added later.", "uncertain"),
            _claim(finished.id, "Elasticsearch ranked the documents.", "superseded"),
        ]
    )
    db.commit()

    response = client.get("/dashboard/summary")
    assert response.status_code == 200, response.text
    summary = response.json()

    expected_counts = dict(
        db.execute(select(Claim.status, func.count()).group_by(Claim.status)).all()
    )
    for status in ("verified", "conflict", "uncertain", "superseded"):
        assert summary["claim_status_counts"][status] == expected_counts.get(status, 0)
    assert summary["claim_status_counts"]["verified"] >= 1
    assert summary["claim_status_counts"]["conflict"] >= 1
    assert sum(summary["claim_status_counts"].values()) == db.scalar(
        select(func.count()).select_from(Claim)
    )

    expected_failures = db.scalar(
        select(func.count()).select_from(Run).where(Run.status == "failed")
    )
    assert summary["failed_run_count"] == expected_failures
    assert summary["failed_run_count"] >= 1

    newest = db.scalars(
        select(Run).order_by(Run.created_at.desc(), Run.id.desc()).limit(1)
    ).one()
    assert summary["latest_run"]["id"] == newest.id
    assert summary["latest_run"]["status"] == newest.status
    assert summary["latest_run"]["question"] == newest.question
    assert summary["latest_run"]["created_at"] is not None


def test_summary_needs_a_token(anon_client) -> None:
    response = anon_client.get("/dashboard/summary")
    assert response.status_code == 401
