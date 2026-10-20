"""Stage 1 — identify languages closely related to the target language.

Scoring is a classification-path overlap measure (after Sean Boisen's
language-similarity work): the overlap of two languages' Glottolog
classification paths, plus a flat areal score for cross-family neighbours that
share a country. Candidates are ranked by that score damped by geographic
distance (``langfamilysim``'s ``combined`` score, see
:func:`rlr.glottolog.combined_similarity`), so a relative on another
continent falls below a neighbour slightly further away in the tree. The
candidate set is not "every
language" but the languages that actually have a Bible in the eBible Corpus,
so stages 1 and 2 answer one question between them: which *usable* texts are
nearest to the target?

This deliberately differs from a nearest-supported-language search over the
same tree (the question a speech model asks: which supported language is
closest?). Same tree, different target set.

There is no ground truth for "closely related".
Translators decide whether related means useful, with
:attr:`~rlr.types.TranslationContext.excluded_languages` as the escape hatch.
An optional ``lwc.csv`` (probability that a speaker of A also speaks LWC B,
see :func:`suggest_lwcs` for the columns) is exposed through
:func:`suggest_lwcs` when ``RLR_LWC_CSV`` points at one.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, get_args

from rlr.types import Location, RelatedLanguage, Unavailable

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from rlr.glottolog import Glottolog
    from rlr.types import LanguageCode, TranslationContext

#: Minimum similarity to count as "closely related" by default. Same-family
#: neighbours in the Bantu cluster score 0.7-0.85; the areal floor is 0.15.
DEFAULT_MIN_SIMILARITY = 0.5
DEFAULT_LIMIT = 10

#: How candidates are ranked: ``"combined"`` damps the tree score by
#: distance; ``"path"`` is the tree score alone (RLR's original ranking).
Scoring = Literal["combined", "path"]
SCORINGS: tuple[Scoring, ...] = get_args(Scoring)
DEFAULT_SCORING: Scoring = "combined"


def parse_scoring(value: str) -> Scoring:
    """Validate an ``RLR_SIMILARITY`` value."""
    for scoring in SCORINGS:
        if value == scoring:
            return scoring
    raise ValueError(f"unknown similarity scoring {value!r}; expected one of {SCORINGS}")


def _bare(code: str) -> str:
    return code.split("_", maxsplit=1)[0].lower()


def find_related_languages(
    context: TranslationContext,
    glottolog: Glottolog,
    candidates: Iterable[LanguageCode],
    *,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    limit: int = DEFAULT_LIMIT,
    scoring: Scoring = DEFAULT_SCORING,
) -> list[RelatedLanguage] | Unavailable:
    """Return the candidates most closely related to ``context.target_language``.

    Args:
        context: The translation context, including the target language and
            any languages the translator has opted out of.
        glottolog: The Glottolog index.
        candidates: ISO 639-3 codes to consider, typically the eBible languages.
        min_similarity: Drop candidates whose tree score (path overlap or
            areal) is below this. The geographic term orders candidates; it
            does not remove them.
        limit: Keep at most this many.
        scoring: The score to rank by and report as ``similarity``.

    Returns:
        Related languages, most similar first, then nearest by distance; or
        :class:`Unavailable` if the target is unknown to Glottolog.
    """
    target = glottolog.resolve(context.target_language)
    if target is None:
        return Unavailable(
            f"{context.target_language!r} is not a Glottolog language or ISO 639-3 code",
            context.target_language,
        )
    excluded = {_bare(c) for c in context.excluded_languages} | {_bare(context.target_language)}
    if target.iso:
        excluded.add(target.iso)
    requested = {_bare(c) for c in context.included_languages} - excluded
    results: list[RelatedLanguage] = []
    for code in sorted({_bare(c) for c in candidates}):
        if code in excluded:
            continue
        languoid = glottolog.by_iso(code)
        if languoid is None:
            continue
        score, shared_country = glottolog.similarity(target, languoid)
        if score < min_similarity and code not in requested:
            continue
        distance = glottolog.distance_km(target, languoid)
        ranked = glottolog.combined(target, languoid) if scoring == "combined" else score
        location = (
            Location(languoid.lat, languoid.lon)
            if languoid.lat is not None and languoid.lon is not None
            else None
        )
        results.append(
            RelatedLanguage(
                code=code,
                name=languoid.name,
                similarity=round(ranked, 3),
                path_similarity=round(score, 3),
                glottocode=languoid.glottocode,
                shared_country=shared_country,
                distance_km=round(distance) if distance is not None else None,
                location=location,
                requested=code in requested,
            ),
        )
    results.sort(key=lambda r: (-r.similarity, r.distance_km if r.distance_km is not None else 1e9))
    asked = [r for r in results if r.requested]
    found = [r for r in results if not r.requested]
    return asked + found[:limit]


@dataclass(frozen=True, slots=True)
class LWCSuggestion:
    """One likely Language of Wider Communication for a target language."""

    code: LanguageCode
    name: str
    probability: float
    country: str
    basis: str


def suggest_lwcs(
    target_language: LanguageCode,
    lwc_csv: Path,
    limit: int = 3,
    min_probability: float = 0.1,
) -> list[LWCSuggestion]:
    """Read an ``lwc.csv`` and rank likely LWCs for ``target_language``.

    The file is one row per ``(language, LWC)`` pair with a probability of
    bilingualism; rankings are more trustworthy than the absolute values.
    """
    code = _bare(target_language)
    rows: list[LWCSuggestion] = []
    with lwc_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["iso639_3"] != code and row["glottocode"] != target_language:
                continue
            prob = float(row["probability"])
            if prob < min_probability:
                continue
            rows.append(
                LWCSuggestion(
                    code=row["lwc_iso639_3"] or row["lwc_glottocode"],
                    name=row["lwc_name"],
                    probability=prob,
                    country=row["country"],
                    basis=row["basis"],
                ),
            )
    rows.sort(key=lambda s: -s.probability)
    return rows[:limit]
