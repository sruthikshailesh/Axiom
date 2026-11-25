from __future__ import annotations

from app.pipeline.verifier import decide_status


def test_single_source_claim_is_uncertain() -> None:
    status, confidence, note = decide_status(
        source_count=1,
        mutual_support=False,
        in_conflict=False,
        superseded=False,
        missing_fields=[],
    )
    assert status == "uncertain"
    assert confidence == 0.4
    assert "one source only" in note.lower()


def test_two_sources_supporting_each_other_are_verified() -> None:
    # Each claim rests on one source; the other source agrees with it.
    status, confidence, note = decide_status(
        source_count=1,
        mutual_support=True,
        in_conflict=False,
        superseded=False,
        missing_fields=[],
    )
    assert status == "verified"
    assert confidence == 0.9
    assert note == ""


def test_multi_source_without_conflict_is_verified() -> None:
    status, confidence, _ = decide_status(
        source_count=2,
        mutual_support=False,
        in_conflict=False,
        superseded=False,
        missing_fields=[],
    )
    assert status == "verified"
    assert confidence == 0.8


def test_missing_owner_adds_uncertainty_note() -> None:
    status, confidence, note = decide_status(
        source_count=2,
        mutual_support=False,
        in_conflict=False,
        superseded=False,
        missing_fields=["Missing owner."],
    )
    assert status == "uncertain"
    assert confidence == 0.4
    assert "Missing owner." in note


def test_conflict_and_supersession_win_over_metadata() -> None:
    conflict = decide_status(2, True, True, False, ["Missing claim date."])
    superseded = decide_status(2, False, False, True, [])
    assert conflict[0] == "conflict"
    assert "Missing claim date." in conflict[2]
    assert superseded[0] == "superseded"
