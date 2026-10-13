"""Pre-rendered translations: the cache, the cached translator, and the batch renderer."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rlr.mt import CachedTranslator, NoTranslator, TranslationUnavailable
from rlr.renderings import (
    RenderingCache,
    RenderingFile,
    file_name,
    note_texts,
    read_file,
    render_texts,
    rendering_key,
    write_file,
)
from rlr.resources.figures_of_speech import ALTERNATIVES_LABEL
from rlr.types import PassageRef, PassageText, TranslationContext, Unavailable


def _file(entries: dict[str, str], backend: str = "madlad400-3b-mt") -> RenderingFile:
    f = RenderingFile(
        backend=backend, source="eng", target="swh", derived_from="uW", license="CC BY-SA 4.0"
    )
    for text, out in entries.items():
        f.entries[rendering_key(text, "eng")] = out
    return f


def test_file_roundtrip(tmp_path):
    f = _file({"Hello": "Jambo", "Alternate translation": "Tafsiri mbadala"})
    path = tmp_path / file_name("swh_Latn")
    write_file(path, f)
    assert path.name == "swh.json.gz"
    back = read_file(path)
    assert back.backend == "madlad400-3b-mt"
    assert back.lookup("Hello", "eng") == "Jambo"
    assert back.lookup("Hello", "fra") is None
    assert back.lookup("Missing", "eng") is None
    # deterministic bytes: writing twice gives the same file
    before = path.read_bytes()
    write_file(path, read_file(path))
    assert path.read_bytes() == before


def test_cache_searches_directories_in_order(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    write_file(first / "swh.json.gz", _file({"Hello": "Jambo (a)"}, backend="x"))
    write_file(second / "swh.json.gz", _file({"Hello": "Jambo (b)", "Bye": "Kwaheri"}, backend="y"))
    cache = RenderingCache([first, second, tmp_path / "missing"])
    assert cache.has_language("eng", "swh")
    assert not cache.has_language("eng", "ind")
    assert not cache.has_language("fra", "swh")
    assert cache.lookup("Hello", "eng", "swh") == ("Jambo (a)", "x")
    assert cache.lookup("Bye", "eng", "swh") == ("Kwaheri", "y")
    assert cache.lookup("Nope", "eng", "swh") is None
    assert cache.backend_for("eng", "swh") == "x"


def test_cached_translator_over_no_backend(tmp_path):
    write_file(tmp_path / "swh.json.gz", _file({"Hello": "Jambo"}))
    t = CachedTranslator(NoTranslator(), RenderingCache([tmp_path]))
    assert t.name == "madlad400-3b-mt (pre-rendered)"
    assert t.supports("eng", "swh")
    assert not t.supports("eng", "por")
    assert t.translate("Hello", "eng", "swh") == "Jambo"
    with pytest.raises(TranslationUnavailable, match="not pre-rendered into swh"):
        t.translate("Nope", "eng", "swh")


class Batchy:
    name = "batchy"

    def __init__(self) -> None:
        self.calls: list[int] = []

    def supports(self, source: str, target: str) -> bool:
        return True

    def translate(self, text: str, source: str, target: str) -> str:
        return f"<{text}>"

    def translate_many(self, texts: list[str], source: str, target: str) -> list[str]:
        self.calls.append(len(texts))
        return [f"<{t}>" for t in texts]


def test_render_texts_batches_and_skips_existing():
    existing = _file({"already": "<already>"})
    b = Batchy()
    added = render_texts(
        ["already", "one", "two", "three"], b, "eng", "swh", existing, batch_size=2
    )
    assert added == 3
    assert b.calls == [2, 1]
    assert existing.lookup("three", "eng") == "<three>"
    assert existing.generated


def test_note_texts_collects_translatable_parts(figures):
    notes = list(figures.notes_in("MRK"))
    texts = note_texts(notes)
    assert texts[0] == ALTERNATIVES_LABEL
    assert "Idiom: A phrase whose meaning differs from the meanings of its words." in texts
    assert "in front of you" in texts
    # Quoted source text is never sent to a translator.
    assert not any("πρὸ προσώπου σου" in t for t in texts)
    assert len(texts) == len(set(texts))


def test_pipeline_renders_notes_from_the_cache(pipeline, figures, tmp_path):
    f = _file({t: f"[sw] {t}" for t in note_texts(figures.notes_in("MRK"))})
    write_file(tmp_path / "r" / "swh.json.gz", f)
    translator = CachedTranslator(NoTranslator(), RenderingCache([tmp_path / "r"]))
    p = replace(pipeline, translator=translator, resources=(figures,))
    briefing = p.brief(
        TranslationContext(target_language="ngq", lwc="swh"), PassageRef.parse("MRK 1:2")
    )
    (idiom,) = briefing.notes
    assert isinstance(idiom.in_lwc, PassageText)
    lines = idiom.in_lwc.text.split("\n")
    assert lines[0].startswith("[sw] Idiom:")
    assert lines[1] == "“before your face” (πρὸ προσώπου σου)"
    assert lines[-1] == "[sw] Alternate translation: [sw] in front of you; [sw] before I send you"
    assert "pre-rendered" in idiom.in_lwc.provenance.source
    # A passage whose note parts are not in the file is reported, not invented.
    f2 = _file({"nothing relevant": "x"})
    write_file(tmp_path / "r" / "swh.json.gz", f2)
    p2 = replace(
        pipeline,
        translator=CachedTranslator(NoTranslator(), RenderingCache([tmp_path / "r"])),
        resources=(figures,),
    )
    b2 = p2.brief(TranslationContext(target_language="ngq", lwc="swh"), PassageRef.parse("MRK 1:2"))
    assert isinstance(b2.notes[0].in_lwc, Unavailable)
    assert "not pre-rendered" in b2.notes[0].in_lwc.reason
