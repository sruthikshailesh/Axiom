"""Node 2: turn retrieved chunks into claims with verbatim supporting quotes."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app import llm
from app.llm import LLMError
from app.models import Claim, Evidence
from app.pipeline import prompts

logger = logging.getLogger("axiom.pipeline")


def _parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _clean_owner(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _raw_claims(question: str, chunks: List[Dict[str, Any]]) -> List[Any]:
    """One extractor call; returns its unvalidated claim items."""
    data = llm.complete_json(
        prompts.EXTRACTOR_SYSTEM,
        prompts.extractor_user(question, chunks),
        prompts.EXTRACTOR_SCHEMA_HINT,
    )
    raw_claims = data.get("claims")
    if not isinstance(raw_claims, list):
        raise LLMError("Extractor response has no 'claims' list.")
    return raw_claims


def _covered_chunk_ids(raw_claims: List[Any], valid_chunk_ids: Set[int]) -> Set[int]:
    """Chunk ids that at least one returned claim cites."""
    covered: Set[int] = set()
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        for entry in item.get("supporting") or []:
            if not isinstance(entry, dict):
                continue
            chunk_id = entry.get("chunk_id")
            if isinstance(chunk_id, bool) or not isinstance(chunk_id, int):
                continue
            if chunk_id in valid_chunk_ids:
                covered.add(chunk_id)
    return covered


def extractor_node(state: Dict[str, Any], db: Session) -> Dict[str, Any]:
    chunks = state.get("chunks") or []
    valid_chunk_ids: Set[int] = {chunk["chunk_id"] for chunk in chunks}
    log: List[str] = []

    raw_claims = _raw_claims(state["question"], chunks)

    # Coverage repair (NOTES, Phase 5b): the model sometimes returns claims for
    # only the chunks it finds most relevant. A chunk with no claim at all is
    # re-extracted on its own, so no source is silently skipped.
    missing = [
        chunk
        for chunk in chunks
        if chunk["chunk_id"] not in _covered_chunk_ids(raw_claims, valid_chunk_ids)
    ]
    if missing:
        for chunk in missing:
            raw_claims = raw_claims + _raw_claims(state["question"], [chunk])
        log.append(
            "extractor: coverage repair re-extracted {} chunk(s)".format(len(missing))
        )

    kept: List[int] = []
    dropped = 0

    for item in raw_claims:
        if not isinstance(item, dict):
            dropped += 1
            continue
        text = (item.get("text") or "").strip()
        supporting = item.get("supporting")
        if not text or not isinstance(supporting, list):
            dropped += 1
            continue

        usable: List[Dict[str, Any]] = []
        for entry in supporting:
            if not isinstance(entry, dict):
                continue
            chunk_id = entry.get("chunk_id")
            quote = (entry.get("quote") or "").strip()
            if isinstance(chunk_id, bool) or not isinstance(chunk_id, int):
                continue
            if chunk_id in valid_chunk_ids and quote:
                usable.append({"chunk_id": chunk_id, "quote": quote})

        if not usable:
            dropped += 1
            continue

        claim = Claim(
            run_id=state["run_id"],
            text=text,
            claim_date=_parse_date(item.get("claim_date")),
            owner=_clean_owner(item.get("owner")),
            status="uncertain",
            confidence=0.5,
        )
        db.add(claim)
        db.flush()
        for entry in usable:
            db.add(
                Evidence(
                    claim_id=claim.id,
                    chunk_id=entry["chunk_id"],
                    quote=entry["quote"],
                    role="supports",
                )
            )
        kept.append(claim.id)

    db.commit()

    message = "extractor: kept {} claims, dropped {} without supporting evidence".format(
        len(kept), dropped
    )
    logger.info(message)
    return {"claims": kept, "log": (state.get("log") or []) + log + [message]}
