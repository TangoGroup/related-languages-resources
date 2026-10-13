"""Tests for the domain types.

These cover the invariants the stage interfaces depend on, chiefly that a
single verse is representable as a passage (decision D3), so no call site needs
a verse-only code path.
"""

from __future__ import annotations

import pytest

import rlr
from rlr.types import DERIVABLE, DISPLAYABLE, LicenseClass, PassageRef, Provenance, VerseRef


def test_version_is_exposed():
    assert rlr.__version__ == "0.0.0"


def test_single_verse_is_a_degenerate_passage():
    ref = VerseRef(book="MRK", chapter=1, verse=6)
    passage = PassageRef.verse(ref)

    assert passage.is_single_verse
    assert passage.start == passage.end == ref


def test_multi_verse_passage_is_not_single():
    passage = PassageRef(
        start=VerseRef(book="MRK", chapter=1, verse=4),
        end=VerseRef(book="MRK", chapter=1, verse=8),
    )

    assert not passage.is_single_verse


@pytest.mark.parametrize(
    ("text", "start", "end", "rendered"),
    [
        ("MRK 1:6", ("MRK", 1, 6), ("MRK", 1, 6), "MRK 1:6"),
        ("MRK 1:4-8", ("MRK", 1, 4), ("MRK", 1, 8), "MRK 1:4-8"),
        ("MRK 1:40-2:3", ("MRK", 1, 40), ("MRK", 2, 3), "MRK 1:40-2:3"),
        (" 1JN 3:1 ", ("1JN", 3, 1), ("1JN", 3, 1), "1JN 3:1"),
    ],
)
def test_passage_parsing_round_trips(text, start, end, rendered):
    passage = PassageRef.parse(text)

    assert passage.start == VerseRef(*start)
    assert passage.end == VerseRef(*end)
    assert str(passage) == rendered


@pytest.mark.parametrize("text", ["Mark 1:6", "MRK 1", "MRK1:6", ""])
def test_passage_parsing_rejects_garbage(text):
    with pytest.raises(ValueError, match="verse reference"):
        PassageRef.parse(text)


def test_provenance_defaults_to_unknown_license():
    # Unknown is the safe default: a source is not usable until proven so.
    assert Provenance(source="ebible", title="Example").license_class is LicenseClass.UNKNOWN


def test_license_classes_separate_display_from_derivatives():
    assert LicenseClass.DERIVATIVES_FORBIDDEN.permits_display
    assert not LicenseClass.DERIVATIVES_FORBIDDEN.permits_derivatives
    assert LicenseClass.OPEN.permits_derivatives
    assert not LicenseClass.UNKNOWN.permits_display
    assert DERIVABLE < DISPLAYABLE


def test_passage_refs_are_hashable():
    # Stages cache by passage, so these must be usable as dict keys.
    a = PassageRef.verse(VerseRef(book="MRK", chapter=1, verse=6))
    b = PassageRef.verse(VerseRef(book="MRK", chapter=1, verse=6))

    assert {a: "x"}[b] == "x"
