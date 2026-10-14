"""Stage 5 data: the figures-of-speech adapter over ``bible-figures-of-speech``."""

from __future__ import annotations

import pytest
from bible_figures_of_speech import parse_ref

from rlr.resources.figures_of_speech import FiguresOfSpeech, passage_of
from rlr.types import LicenseClass, PassageRef


def test_catalog_loads(figures):
    assert set(figures.types) == {"figs-metaphor", "figs-idiom"}
    assert figures.source_language() == "eng"
    assert figures.types["figs-idiom"].label == "Idiom"


def test_passage_of_converts_biblelib_ranges():
    assert passage_of(parse_ref("MRK 1:2")) == PassageRef.parse("MRK 1:2")
    assert passage_of(parse_ref("ROM 3:1-ROM 3:9")) == PassageRef.parse("ROM 3:1-9")


def test_notes_for_single_verse(figures):
    (note,) = figures.notes_for(PassageRef.parse("MRK 1:2"))
    assert note.title == "Idiom"
    assert note.alternate_translations == ("in front of you", "before I send you")
    assert "Idiom: A phrase" in note.body
    assert "“before your face” (πρὸ προσώπου σου)" in note.body
    assert "Alternate translation: in front of you; before I send you" in note.body
    assert note.provenance.license_class is LicenseClass.OPEN
    assert note.provenance.license_name == "CC BY-SA 4.0"
    assert note.provenance.publisher == "unfoldingWord"
    assert "140949" in note.provenance.title


def test_range_notes_overlap_passages(figures):
    ids = [n.note_id for n in figures.notes_for(PassageRef.parse("MRK 1:3-5"))]
    assert ids == ["140955", "999"]
    assert figures.notes_for(PassageRef.parse("MRK 1:9")) == []


def test_unknown_types_and_books_are_skipped(figures):
    assert figures.notes_for(PassageRef.parse("MRK 2:1")) == []
    assert figures.notes_for(PassageRef.parse("GEN 1:1")) == []


def test_bundled_data_is_the_default():
    bundled = FiguresOfSpeech()
    assert bundled.data_dir is None
    assert len(bundled.types) == 19
    assert [n.title for n in bundled.notes_for(PassageRef.parse("MRK 1:3"))]


def test_missing_catalog_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="RLR_FIGURES_DIR"):
        FiguresOfSpeech(tmp_path)
