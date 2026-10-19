"""Stage 1 scoring over a tiny Glottolog slice."""

from __future__ import annotations

import math

import pytest

from rlr.glottolog import (
    AREAL_SCORE,
    GEO_FLOOR_GENEALOGICAL,
    GEO_SCALE_KM,
    Glottolog,
    Languoid,
    combined_similarity,
    geo_factor,
    path_similarity,
)
from rlr.languages import find_related_languages, parse_scoring
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
    assert kara.path_similarity == pytest.approx(0.75)
    assert kara.distance_km is not None
    assert kara.similarity == pytest.approx(0.75 * geo_factor(kara.distance_km, 0.3), abs=1e-3)
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


def test_geo_factor_decays_to_its_floor():
    assert geo_factor(0, 0.3) == 1.0
    assert geo_factor(GEO_SCALE_KM, 0.0) == pytest.approx(math.exp(-1))
    assert geo_factor(1e6, 0.3) == pytest.approx(0.3)
    assert geo_factor(500, 0.3) > geo_factor(5000, 0.3)


def test_combined_similarity_floors_and_missing_coordinates():
    # Genealogical relatives keep the floor; areal contact fades to nothing.
    assert combined_similarity(0.8, 1e6, areal=False) == pytest.approx(0.8 * GEO_FLOOR_GENEALOGICAL)
    assert combined_similarity(AREAL_SCORE, 1e6, areal=True) == pytest.approx(0.0)
    # No coordinates is no information, not a penalty.
    assert combined_similarity(0.8, None, areal=False) == 0.8


def test_cross_family_neighbour_is_damped_as_areal(glottolog):
    ngq, sad = glottolog.by_iso("ngq"), glottolog.by_iso("sad")
    distance = glottolog.distance_km(ngq, sad)
    assert distance is not None
    assert glottolog.combined(ngq, sad) == pytest.approx(AREAL_SCORE * geo_factor(distance, 0.0))


def _languoid(code: str, path: tuple[str, ...], lat: float, lon: float) -> Languoid:
    return Languoid(code, code, "language", code, (), lat, lon, (*path, code))


def test_distant_relative_ranks_below_a_near_one():
    tree = ("fam", "a", "b", "c")
    target = _languoid("tgt", tree, 0.0, 0.0)
    far = _languoid("far", tree, 0.0, 100.0)  # tree score 0.8, ~11,000 km away
    near = _languoid("nea", tree[:3], 0.0, 1.0)  # tree score 0.75, ~110 km away
    glottolog = Glottolog([target, far, near])
    ctx = TranslationContext(target_language="tgt", lwc="eng")
    combined = find_related_languages(ctx, glottolog, ["far", "nea"])
    path = find_related_languages(ctx, glottolog, ["far", "nea"], scoring="path")
    assert not isinstance(combined, Unavailable)
    assert not isinstance(path, Unavailable)
    assert [r.code for r in combined] == ["nea", "far"]
    assert [r.code for r in path] == ["far", "nea"]
    # The threshold is on the tree score, so the distant relative is kept.
    assert combined[1].similarity < 0.5 <= combined[1].path_similarity  # type: ignore[operator]
    assert all(r.similarity == r.path_similarity for r in path)


def test_parse_scoring():
    assert parse_scoring("combined") == "combined"
    assert parse_scoring("path") == "path"
    with pytest.raises(ValueError, match="geo"):
        parse_scoring("geo")
