"""Passage input is case-insensitive (lower-case book codes were a reported papercut)."""

from __future__ import annotations

from rlr.types import PassageRef, VerseRef


def test_lower_case_references_parse():
    assert VerseRef.parse("mrk 1:3") == VerseRef("MRK", 1, 3)
    assert PassageRef.parse(" mrk 1:4-8 ") == PassageRef.parse("MRK 1:4-8")
    assert PassageRef.parse("1jn 1:1") == PassageRef.parse("1JN 1:1")
