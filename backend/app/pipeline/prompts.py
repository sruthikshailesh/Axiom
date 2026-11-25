"""All LLM prompts for the pipeline, kept in one place so they are easy to edit."""

from __future__ import annotations

from typing import Any, Dict, List

EXTRACTOR_SYSTEM = """You are AXIOM's extractor. You turn retrieved document chunks \
into small, checkable claims.

Rules:
- Use only the chunks you are given. Never add outside knowledge.
- Return exactly one claim per chunk: the chunk's central statement that bears on
  the question. Do not return several claims from the same chunk, and do not merge
  statements that come from different chunks or different sources, even when they
  are about the same topic. Two sources saying the same thing produce two claims.
- If a statement says a decision was changed, dropped, replaced or is pending, extract
  it as its own claim, separate from the statement it replaces or refers to. Never
  fold such a statement into the claim it talks about.
- One fact per claim. Prefer short, self-contained sentences, using a sentence the
  chunk actually states rather than a summary of the whole chunk.
- Every claim needs at least one supporting entry. A claim with no support is dropped.
- Cite the chunk ids that support the claim, and only those chunks.
- "quote" must be copied character for character from the chunk text. Never paraphrase,
  never join two sentences with "...", never add or drop words.
- "owner" is the person or organisation the claim is attributed to. When the chunk text
  names no owner, use the author shown in the chunk header of the chunk you cite. Do
  not return null when that header shows an author.
- "claim_date" is the date the claim is about (YYYY-MM-DD). When the chunk text states
  no date, use the date shown in the chunk header of the chunk you cite. Do not return
  null when that header shows a date.
- Skip opinions, questions and vague statements."""

EXTRACTOR_SCHEMA_HINT = """{\
"claims": [{\
"text": "string", \
"claim_date": "YYYY-MM-DD or null", \
"owner": "string or null", \
"supporting": [{"chunk_id": 1, "quote": "verbatim text from that chunk"}]\
}]}"""

COMPARISON_SYSTEM = """You compare two claims taken from different documents.

Choose exactly one relation:
- "contradicts": the claims cannot both be true.
- "supersedes": they describe the same fact, and one replaces the other over time.
- "supports": they agree and reinforce each other.
- "unrelated": they do not speak about the same thing.

For "contradicts", set "newer" to "a" or "b" only when the claims themselves make the
order clear (for example a changed value with a date). Otherwise use null. Never guess.
"reason" must be one short sentence a reader can check."""

COMPARISON_SCHEMA_HINT = """{\
"relation": "contradicts" | "supersedes" | "supports" | "unrelated", \
"reason": "string", \
"newer": "a" | "b" | null\
}"""


def extractor_user(question: str, chunks: List[Dict[str, Any]]) -> str:
    """Prompt body listing each retrieved chunk with its id and metadata."""
    lines = ["Question: {}".format(question), "", "Retrieved chunks:", ""]
    for chunk in chunks:
        lines.append(
            "--- chunk_id={} (source: {}, dated {}, author {}) ---".format(
                chunk["chunk_id"],
                chunk["source_title"],
                chunk.get("doc_date") or "unknown",
                chunk.get("author") or "unknown",
            )
        )
        lines.append(chunk["text"])
        lines.append("")

    lines.append(
        "Cover every chunk: return at least one claim that cites each of these "
        "chunk ids ({}) unless that chunk states no checkable fact.".format(
            ", ".join(str(chunk["chunk_id"]) for chunk in chunks)
        )
    )
    return "\n".join(lines)


def comparison_user(claim_a: Dict[str, Any], claim_b: Dict[str, Any]) -> str:
    """Prompt body for one pairwise comparison."""
    return (
        "Claim A: {}\nclaim_date: {}\nowner: {}\nsources: {}\n\n"
        "Claim B: {}\nclaim_date: {}\nowner: {}\nsources: {}\n"
    ).format(
        claim_a["text"],
        claim_a.get("claim_date") or "unknown",
        claim_a.get("owner") or "unknown",
        ", ".join(claim_a.get("source_titles") or []) or "unknown",
        claim_b["text"],
        claim_b.get("claim_date") or "unknown",
        claim_b.get("owner") or "unknown",
        ", ".join(claim_b.get("source_titles") or []) or "unknown",
    )
