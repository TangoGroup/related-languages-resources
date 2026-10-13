"""Stage 1 scoring over a tiny Glottolog slice."""

from __future__ import annotations

import pytest

from rlr.glottolog import AREAL_SCORE, Glottolog, path_similarity
from rlr.languages import find_related_languages
from rlr.types import TranslationContext, Unavailable


def test_cldf_parse_builds_paths(glottolog):
    ngq = glottolog.by_iso("ngq")
    assert ngq is not None
    assert ngq.path == ("atla1278", "bant1000", "lacu1000", "ngor1000")
    assert ngq.family == "atla1278"
    assert ngq.countries == ("TZ",)
    assert glottolog.resolve("ngor1000") is ngq


def test_path_similarity_is_shared_prefix_over_shorter_path(glottolog):
    ngq, reg, zga = (glottolog.by_iso(c) for c in ("ngq", "reg", "zga"))
    assert path_similarity(ngq, reg) == pytest.approx(3 / 4)
    assert path_similarity(ngq, zga) == pytest.approx(2 / 4)
    assert path_similarity(ngq, ngq) == 1.0


def test_cross_family_neighbours_get_only_the_areal_score(glottolog):
    ngq, sad, eng = (glottolog.by_iso(c) for c in ("ngq", "sad", "eng"))
    assert glottolog.similarity(ngq, sad) == (AREAL_SCORE, True)
    assert glottolog.similarity(ngq, eng) == (0.0, False)


def test_json_cache_round_trips(glottolog, tmp_path):
    path = tmp_path / "languoids.json"
    glottolog.save(path)
    again = Glottolog.from_json(path)
    assert len(again) == len(glottolog)
    assert again.by_iso("swh") == glottolog.by_iso("swh")


def test_language_level_entry_wins_iso_collision(glottolog):
    # rwl is a dialect in the fixture; it still resolves, and kcz is language-level.
    assert glottolog.by_iso("rwl").level == "dialect"
    assert glottolog.by_iso("kcz").level == "language"


def test_related_languages_are_ranked_and_filtered(glottolog, corpus):
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    related = find_related_languages(ctx, glottolog, corpus.languages, min_similarity=0.5)
    assert not isinstance(related, Unavailable)
    assert [r.code for r in related] == ["reg", "swh", "wbi", "zga"]
    kara = related[0]
    assert kara.similarity == pytest.approx(0.75)
    assert kara.shared_country
    assert kara.distance_km is not None
    assert kara.location is not None


def test_related_languages_honour_exclusions_and_script_suffixes(glottolog, corpus):
    ctx = TranslationContext(
        target_language="ngq_Latn", lwc="swh", excluded_languages=frozenset({"reg_Latn"})
    )
    related = find_related_languages(ctx, glottolog, corpus.languages, min_similarity=0.5)
    assert not isinstance(related, Unavailable)
    assert [r.code for r in related] == ["swh", "wbi", "zga"]


def test_unknown_target_is_unavailable(glottolog, corpus):
    ctx = TranslationContext(target_language="zzz", lwc="swh")
    result = find_related_languages(ctx, glottolog, corpus.languages)
    assert isinstance(result, Unavailable)
    assert "zzz" in result.reason


def test_limit_and_threshold(glottolog, corpus):
    ctx = TranslationContext(target_language="ngq", lwc="swh")
    one = find_related_languages(ctx, glottolog, corpus.languages, limit=1)
    assert not isinstance(one, Unavailable)
    assert len(one) == 1
    assert find_related_languages(ctx, glottolog, corpus.languages, min_similarity=0.99) == []
