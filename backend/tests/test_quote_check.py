from __future__ import annotations

from app.pipeline.verifier import quote_appears

CHUNK = (
    "The ionosphere is a shell of electrons and electrically charged atoms.\n"
    "It begins at about 48 km altitude and reflects radio waves."
)


def test_verbatim_quote_passes() -> None:
    assert quote_appears("The ionosphere is a shell of electrons", CHUNK)


def test_quote_spanning_a_line_break_passes() -> None:
    assert quote_appears("charged atoms. It begins at about 48 km", CHUNK)


def test_paraphrase_fails() -> None:
    assert not quote_appears("The ionosphere is a layer of charged particles.", CHUNK)


def test_empty_quote_fails() -> None:
    assert not quote_appears("   ", CHUNK)
