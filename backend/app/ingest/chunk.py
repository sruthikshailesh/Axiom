from __future__ import annotations

from typing import List

TARGET_TOKENS = 500
OVERLAP_TOKENS = 60
TOKENS_PER_WORD = 1.3

# 500 tokens / 1.3 ~= 385 words; 60 tokens / 1.3 ~= 46 words.
CHUNK_WORDS = int(round(TARGET_TOKENS / TOKENS_PER_WORD))
OVERLAP_WORDS = int(round(OVERLAP_TOKENS / TOKENS_PER_WORD))


def chunk_text(text: str) -> List[str]:
    """Split text into ~385-word chunks that overlap by ~46 words.

    Pure function: no database or I/O. Position is the index in the result.
    """
    words = text.split()
    if not words:
        return []

    step = CHUNK_WORDS - OVERLAP_WORDS
    chunks = []
    start = 0

    while start < len(words):
        chunks.append(" ".join(words[start : start + CHUNK_WORDS]))
        if start + CHUNK_WORDS >= len(words):
            break
        start += step

    return chunks
