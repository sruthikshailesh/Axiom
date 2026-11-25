from __future__ import annotations

from app.ingest.chunk import CHUNK_WORDS, OVERLAP_WORDS, chunk_text


def test_chunk_sizes_are_about_385_words_with_46_word_overlap():
    assert CHUNK_WORDS == 385
    assert OVERLAP_WORDS == 46


def test_thousand_words_produce_three_overlapping_chunks():
    words = ["word{}".format(i) for i in range(1000)]

    chunks = chunk_text(" ".join(words))

    assert len(chunks) == 3
    assert [len(chunk.split()) for chunk in chunks] == [385, 385, 322]

    first, second, third = (chunk.split() for chunk in chunks)
    assert first[-OVERLAP_WORDS:] == second[:OVERLAP_WORDS]
    assert second[-OVERLAP_WORDS:] == third[:OVERLAP_WORDS]
    assert [position for position, _ in enumerate(chunks)] == [0, 1, 2]


def test_short_text_is_a_single_chunk():
    assert chunk_text("one two three") == ["one two three"]


def test_blank_text_has_no_chunks():
    assert chunk_text("   \n\t ") == []
