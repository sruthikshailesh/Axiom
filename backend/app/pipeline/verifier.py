"""Node 3: check quotes, compare claims, and apply the status rules.

The status rules live in one function, decide_status(), so they can be tested
without a database or an LLM.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import llm
from app.models import Chunk, Claim, Conflict, Evidence, Source, Supersession
from app.pipeline import prompts

MAX_PAIRWISE_COMPARISONS = 10
MIN_TOPIC_WORD_LENGTH = 4

STOPWORDS = {
    "about", "after", "also", "because", "been", "before", "being", "between",
    "both", "could", "does", "each", "from", "have", "into", "more", "most",
    "other", "over", "same", "should", "such", "than", "that", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "under",
    "until", "very", "were", "what", "when", "where", "which", "while", "with",
    "would", "your",
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_appears(quote: str, text: str) -> bool:
    """True when the quote is copied verbatim (whitespace-insensitive)."""
    if not quote or not quote.strip():
        return False
    return _normalise(quote) in _normalise(text)


def decide_status(
    source_count: int,
    mutual_support: bool,
    in_conflict: bool,
    superseded: bool,
    missing_fields: List[str],
) -> Tuple[str, float, str]:
    """The single source of truth for a claim's status, confidence and note."""
    notes: List[str] = []
    if missing_fields:
        notes.extend(missing_fields)
    if source_count <= 1:
        notes.append("Supported by one source only.")
    note = " ".join(notes)

    if superseded:
        return "superseded", 0.5, note
    if in_conflict:
        return "conflict", 0.5, note
    # Two claims from different sources confirming each other beat a lone claim
    # even though each of the two is backed by a single source on its own.
    if mutual_support and not missing_fields:
        return "verified", 0.9, ""
    if source_count >= 2 and not missing_fields:
        return "verified", 0.8, ""
    return "uncertain", 0.4, note or "Not enough independent support."


def _topic_words(text: str) -> Set[str]:
    words = re.findall(r"[a-z]{4,}", text.lower())
    return {word for word in words if word not in STOPWORDS}


def _topic_pairs(claims: Iterable[Claim]) -> List[Tuple[Claim, Claim]]:
    """Pairs of claims that share a topic word, capped to keep the run bounded."""
    items = list(claims)
    pairs: List[Tuple[Claim, Claim]] = []
    for i, first in enumerate(items):
        words_a = _topic_words(first.text)
        for second in items[i + 1 :]:
            if words_a & _topic_words(second.text):
                pairs.append((first, second))
    return pairs


def _newer_claim(
    a: Claim,
    b: Claim,
    source_dates: Dict[int, Optional[date]],
    claim_sources: Dict[int, Set[int]],
) -> Optional[str]:
    """Which claim is newer, from claim dates first, then source document dates."""
    if a.claim_date and b.claim_date and a.claim_date != b.claim_date:
        return "a" if a.claim_date > b.claim_date else "b"

    def newest_source_date(claim_id: int) -> Optional[date]:
        dates = [
            source_dates[source_id]
            for source_id in claim_sources.get(claim_id, set())
            if source_dates.get(source_id)
        ]
        return max(dates) if dates else None

    date_a, date_b = newest_source_date(a.id), newest_source_date(b.id)
    if date_a and date_b and date_a != date_b:
        return "a" if date_a > date_b else "b"
    return None


def _missing_fields(claim: Claim, evidence_count: int) -> List[str]:
    notes: List[str] = []
    if claim.claim_date is None:
        notes.append("Missing claim date.")
    if not claim.owner:
        notes.append("Missing owner.")
    if evidence_count == 0:
        notes.append("No usable evidence.")
    return notes


def verifier_node(state: Dict[str, Any], db: Session) -> Dict[str, Any]:
    run_id = state["run_id"]
    log: List[str] = list(state.get("log") or [])

    claims = db.scalars(
        select(Claim).where(Claim.run_id == run_id).order_by(Claim.id)
    ).all()
    claim_ids = [claim.id for claim in claims]
    evidences = db.scalars(
        select(Evidence).where(Evidence.claim_id.in_(claim_ids))
    ).all()

    chunk_rows = db.execute(
        select(Chunk.id, Chunk.text, Chunk.source_id).where(
            Chunk.id.in_({evidence.chunk_id for evidence in evidences})
        )
    ).all()
    chunk_text = {row.id: row.text for row in chunk_rows}
    chunk_source = {row.id: row.source_id for row in chunk_rows}

    # 1. Quote check: drop evidence whose quote is not verbatim.
    failing = [
        evidence
        for evidence in evidences
        if not quote_appears(evidence.quote, chunk_text.get(evidence.chunk_id, ""))
    ]
    for evidence in failing:
        db.delete(evidence)
    db.flush()
    log.append("verifier: dropped {} evidence entries failing the quote check".format(len(failing)))

    remaining = db.scalars(
        select(Evidence).where(Evidence.claim_id.in_(claim_ids))
    ).all()
    by_claim: Dict[int, List[Evidence]] = {claim_id: [] for claim_id in claim_ids}
    for evidence in remaining:
        by_claim[evidence.claim_id].append(evidence)

    # 2. Claims left with no evidence are deleted.
    orphans = [claim for claim in claims if not by_claim.get(claim.id)]
    for claim in orphans:
        db.delete(claim)
    db.flush()
    claims = [claim for claim in claims if claim.id not in {c.id for c in orphans}]
    log.append("verifier: deleted {} claims with no surviving evidence".format(len(orphans)))

    claim_sources: Dict[int, Set[int]] = {
        claim.id: {chunk_source[evidence.chunk_id] for evidence in by_claim.get(claim.id, [])}
        for claim in claims
    }
    source_ids = {source_id for ids in claim_sources.values() for source_id in ids}
    sources = {
        source.id: source
        for source in db.scalars(select(Source).where(Source.id.in_(source_ids))).all()
    }
    source_dates = {source.id: source.doc_date for source in sources.values()}
    source_titles = {source.id: source.title for source in sources.values()}

    def claim_view(claim: Claim) -> Dict[str, Any]:
        return {
            "text": claim.text,
            "claim_date": claim.claim_date.isoformat() if claim.claim_date else None,
            "owner": claim.owner,
            "source_titles": sorted(
                source_titles.get(source_id, "unknown")
                for source_id in claim_sources.get(claim.id, set())
            ),
        }

    # 3. Pairwise comparison of claims sharing a topic.
    pairs = _topic_pairs(claims)
    if len(pairs) > MAX_PAIRWISE_COMPARISONS:
        log.append(
            "verifier: compared the first {} of {} topical claim pairs".format(
                MAX_PAIRWISE_COMPARISONS, len(pairs)
            )
        )
        pairs = pairs[:MAX_PAIRWISE_COMPARISONS]

    in_conflict: Set[int] = set()
    superseded: Set[int] = set()
    mutual_support: Set[int] = set()

    for first, second in pairs:
        result = llm.complete_json(
            prompts.COMPARISON_SYSTEM,
            prompts.comparison_user(claim_view(first), claim_view(second)),
            prompts.COMPARISON_SCHEMA_HINT,
        )
        relation = (result.get("relation") or "").strip().lower()
        reason = (result.get("reason") or "").strip() or "No reason given."
        newer = result.get("newer")

        different_sources = bool(
            claim_sources.get(first.id, set()) - claim_sources.get(second.id, set())
        )

        if relation == "supports":
            if different_sources:
                mutual_support.update({first.id, second.id})
            continue

        if relation == "supersedes":
            if newer not in ("a", "b"):
                newer = _newer_claim(first, second, source_dates, claim_sources)
        elif relation == "contradicts":
            newer = newer if newer in ("a", "b") else _newer_claim(
                first, second, source_dates, claim_sources
            )
        else:
            continue

        if relation == "supersedes" or relation == "contradicts":
            if newer in ("a", "b"):
                old, new = (first, second) if newer == "b" else (second, first)
                db.add(
                    Supersession(
                        run_id=run_id,
                        old_claim_id=old.id,
                        new_claim_id=new.id,
                        reason=reason,
                    )
                )
                superseded.add(old.id)
                continue

        db.add(
            Conflict(
                run_id=run_id,
                claim_a_id=first.id,
                claim_b_id=second.id,
                reason=reason,
            )
        )
        in_conflict.update({first.id, second.id})

    # 4. Apply the status rules.
    statuses = {}
    for claim in claims:
        evidence_count = len(by_claim.get(claim.id, []))
        status, confidence, note = decide_status(
            source_count=len(claim_sources.get(claim.id, set())),
            mutual_support=claim.id in mutual_support,
            in_conflict=claim.id in in_conflict,
            superseded=claim.id in superseded,
            missing_fields=_missing_fields(claim, evidence_count),
        )
        claim.status = status
        claim.confidence = confidence
        claim.uncertainty_note = note or None
        statuses[claim.id] = status

    db.commit()
    log.append("verifier: finalised {} claims".format(len(statuses)))

    return {
        "verification": {
            "statuses": statuses,
            "conflicts": len(in_conflict),
            "supersessions": len(superseded),
        },
        "log": log,
    }
