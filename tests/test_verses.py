"""Stage 3: the vref index and verse-per-line retrieval."""

from __future__ import annotations

import pytest

from rlr.config import OfflineError
from rlr.types import PassageRef, PassageText, Unavailable, VerseRef
from rlr.verses import ensure_cached, fetch_passage


def test_index_maps_references_to_lines(index):
    assert len(index) == 9
    assert index.line_number(VerseRef("MRK", 1, 6)) == 5
    assert index.line_numbers(PassageRef.parse("MRK 1:4-8")) == range(3, 8)
    assert index.reference(8) == "MRK 2:1"
    assert VerseRef("MRK", 1, 6) in index
    assert VerseRef("MRK", 9, 9) not in index


def test_index_rejects_backwards_passages(index):
    with pytest.raises(ValueError, match="precedes"):
        index.line_numbers(PassageRef(VerseRef("MRK", 1, 8), VerseRef("MRK", 1, 4)))


def test_fetch_single_verse(corpus, index, settings):
    (kara,) = corpus.editions_for("reg")
    path = ensure_cached(kara, corpus, settings)
    text = fetch_passage(kara, PassageRef.parse("MRK 1:6"), index, path)
    assert isinstance(text, PassageText)
    assert text.text == "reg 1:6 camel hair"
    assert text.language == "reg"
    assert text.provenance is kara.provenance
    assert text.derived_from is None


def test_fetch_range_skips_range_markers(corpus, index, settings):
    (kara,) = corpus.editions_for("reg")
    path = ensure_cached(kara, corpus, settings)
    text = fetch_passage(kara, PassageRef.parse("MRK 1:4-6"), index, path)
    assert isinstance(text, PassageText)
    assert text.text == "reg 1:4 and 1:5 together reg 1:6 camel hair"


def test_missing_verse_is_unavailable_not_empty(corpus, index, settings):
    (kinga,) = corpus.editions_for("zga")
    path = ensure_cached(kinga, corpus, settings)
    result = fetch_passage(kinga, PassageRef.parse("MRK 1:6"), index, path)
    assert isinstance(result, Unavailable)
    assert "no text for MRK 1:6" in result.reason


def test_unknown_reference_is_unavailable(corpus, index, settings):
    (kara,) = corpus.editions_for("reg")
    path = ensure_cached(kara, corpus, settings)
    result = fetch_passage(kara, PassageRef.parse("REV 22:21"), index, path)
    assert isinstance(result, Unavailable)


def test_offline_cache_miss_raises(corpus, settings):
    (swh,) = corpus.editions_for("swh")
    (settings.cache_dir / "ebible" / "corpus" / "swh-swhulb.txt").unlink()
    with pytest.raises(OfflineError):
        ensure_cached(swh, corpus, settings)
