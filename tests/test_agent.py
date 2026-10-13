"""The composed pipeline: provenance everywhere, absence always explained."""

from __future__ import annotations

from rlr.agent import Pipeline
from rlr.types import PassageRef, TranslationContext, Unavailable


def test_brief_without_translation_backend(pipeline):
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    briefing = pipeline.brief(ctx, PassageRef.parse("MRK 1:6"))

    assert briefing.nothing_found is None
    assert [r.language.code for r in briefing.readings] == ["reg", "swh", "wbi"]
    kara = briefing.readings[0]
    assert kara.original.text == "reg 1:6 camel hair"
    assert kara.original.provenance.license_name == "CC BY-SA 4.0"
    assert isinstance(kara.in_lwc, Unavailable)
    assert "backend: none" in kara.in_lwc.reason
    swahili = briefing.readings[1]
    assert isinstance(swahili.in_lwc, Unavailable)
    assert "already is the LWC" in swahili.in_lwc.reason
    # Kinga has no MRK 1:6, so it is skipped with a reason rather than dropped.
    assert any("zgam has no text for MRK 1:6" in s.reason for s in briefing.skipped)
    # The fixture's range note (MRK 1:4-8) overlaps 1:6, so stage 5 has one hit.
    assert briefing.no_notes is None
    assert [n.note.note_id for n in briefing.notes] == ["999"]

    empty = pipeline.brief(ctx, PassageRef.parse("MRK 1:1"))
    assert empty.notes == ()
    assert empty.no_notes is not None
    assert "no notes for MRK 1:1" in empty.no_notes.reason


def test_brief_with_translation_backend_respects_licenses(translating_pipeline):
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    briefing = translating_pipeline.brief(ctx, PassageRef.parse("MRK 1:2-3"))

    by_code = {r.language.code: r for r in briefing.readings}
    kara = by_code["reg"]
    assert kara.in_lwc.text == "[reg->swh] reg 1:2 reg 1:3"
    assert kara.in_lwc.derived_from is kara.original
    assert kara.in_lwc.provenance.source.startswith("machine back-translation (fake)")
    assert kara.in_lwc.provenance.license_name == "CC BY-SA 4.0"
    vwanji = by_code["wbi"]
    assert isinstance(vwanji.in_lwc, Unavailable)
    assert "does not permit derivative works" in vwanji.in_lwc.reason

    assert briefing.no_notes is None
    titles = [n.note.title for n in briefing.notes]
    assert titles == ["Idiom", "Metaphor"]
    idiom = briefing.notes[0]
    assert idiom.original.language == "eng"
    assert idiom.in_lwc.language == "swh"
    assert idiom.in_lwc.text.startswith("[eng->swh] Idiom:")
    assert idiom.in_lwc.derived_from is idiom.original
    assert idiom.in_lwc.provenance.publisher == "unfoldingWord"


def test_notes_in_lwc_are_unavailable_without_backend(pipeline):
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    briefing = pipeline.brief(ctx, PassageRef.parse("MRK 1:2"))
    (idiom,) = briefing.notes
    assert isinstance(idiom.in_lwc, Unavailable)
    assert "no machine translation from eng into swh" in idiom.in_lwc.reason


def test_notes_already_in_lwc_pass_through(pipeline):
    ctx = TranslationContext(target_language="ngq", lwc="eng")
    briefing = pipeline.brief(ctx, PassageRef.parse("MRK 1:2"))
    (idiom,) = briefing.notes
    assert idiom.in_lwc is idiom.original


def test_unknown_target_reports_nothing_found(pipeline):
    ctx = TranslationContext(target_language="zzz", lwc="swh")
    briefing = pipeline.brief(ctx, PassageRef.parse("MRK 1:6"))
    assert briefing.readings == ()
    assert briefing.nothing_found is not None
    assert "zzz" in briefing.nothing_found.reason


def test_no_related_language_reports_threshold(pipeline):
    pipeline.min_similarity = 0.99
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    briefing = pipeline.brief(ctx, PassageRef.parse("MRK 1:6"))
    assert briefing.related == ()
    assert briefing.nothing_found is not None
    assert "0.99" in briefing.nothing_found.reason


def test_no_resources_is_reported(settings, glottolog, corpus, index):
    from rlr.mt import NoTranslator

    pipeline = Pipeline(settings, glottolog, corpus, index, NoTranslator())
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    briefing = pipeline.brief(ctx, PassageRef.parse("MRK 1:6"))
    assert briefing.notes == ()
    assert briefing.no_notes is not None
    assert "no verse-indexed resources" in briefing.no_notes.reason
