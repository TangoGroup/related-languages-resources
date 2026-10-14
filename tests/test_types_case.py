"""Passage input is case-insensitive (lower-case book codes were a reported papercut)."""

from __future__ import annotations

from rlr.types import PassageRef, VerseRef


def test_lower_case_references_parse():
    assert VerseRef.parse("mrk 1:3") == VerseRef("MRK", 1, 3)
    assert PassageRef.parse(" mrk 1:4-8 ") == PassageRef.parse("MRK 1:4-8")
    assert PassageRef.parse("1jn 1:1") == PassageRef.parse("1JN 1:1")


def test_language_codes_normalise_case():
    from rlr.types import TranslationContext, normalize_code

    assert normalize_code(" SWH ") == "swh"
    assert normalize_code("Swh") == "swh"
    assert normalize_code("FUL_LATN") == "ful_Latn"
    assert normalize_code("ful_Latn") == "ful_Latn"
    ctx = TranslationContext(
        target_language="NGQ",
        lwc="Swh",
        excluded_languages=frozenset({"WBI"}),
        included_languages=frozenset({"Zga"}),
    )
    assert ctx.target_language == "ngq"
    assert ctx.lwc == "swh"
    assert ctx.excluded_languages == frozenset({"wbi"})
    assert ctx.included_languages == frozenset({"zga"})
