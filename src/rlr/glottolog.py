"""Glottolog's genealogical classification, read from its CLDF export.

Glottolog's own git repository is around a gigabyte. Its CLDF export
(``glottolog/glottolog-cldf``) carries everything stage 1 needs in two files:
``languages.csv`` (names, ISO codes, countries, coordinates) and the
``classification`` parameter in ``values.csv``, which is the slash-separated
path of ancestor glottocodes from the top-level family down to the languoid.

The similarity measure here is a classification-path overlap (after Sean Boisen's
language-similarity measure): the length of the shared prefix of two
classification paths, divided by the length of the shorter path. Spanish and
Catalan score about 0.92, English and German about 0.42, and languages in
different families score 0.

A geographic term (after ``langfamilysim``'s ``combined`` score, also Sean
Boisen's) damps that score by the distance between the two Glottolog points:
see :func:`geo_factor`.

The parsed subset is cached as JSON so the 21 MB ``values.csv`` is only read
once per machine.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from rlr.config import fetch_cached

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from rlr.config import Settings

CLDF_BASE = "https://raw.githubusercontent.com/glottolog/glottolog-cldf/master/cldf"
LANGUAGES_URL = f"{CLDF_BASE}/languages.csv"
VALUES_URL = f"{CLDF_BASE}/values.csv"
CACHE_NAME = "glottolog/languoids.json"

#: Score given to a cross-family pair that shares a country, matching the
#: "areal" edges in ``language-similarity``.
AREAL_SCORE = 0.15

#: Distance at which the geographic damping has decayed by a factor of e.
GEO_SCALE_KM = 2000.0
#: Related-but-distant languages keep at least this share of their tree score,
#: so families spread by migration (Bantu, Austronesian) are not erased.
GEO_FLOOR_GENEALOGICAL = 0.3
#: Sharing a country means nothing at long range.
GEO_FLOOR_AREAL = 0.0


@dataclass(frozen=True, slots=True)
class Languoid:
    """One Glottolog languoid with the fields stage 1 uses."""

    glottocode: str
    name: str
    level: str
    iso: str | None
    countries: tuple[str, ...]
    lat: float | None
    lon: float | None
    #: Ancestor glottocodes from the top-level family down, then this one.
    path: tuple[str, ...]

    @property
    def family(self) -> str:
        """The top-level family glottocode (the languoid itself for isolates)."""
        return self.path[0]


def path_similarity(a: Languoid, b: Languoid) -> float:
    """Shared-prefix fraction of two classification paths."""
    shared = 0
    for x, y in zip(a.path, b.path, strict=False):
        if x != y:
            break
        shared += 1
    return shared / min(len(a.path), len(b.path))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(max(0.0, a)))


def geo_factor(distance_km: float, floor: float) -> float:
    """Damping in ``[floor, 1]``: 1 at zero distance, decaying toward ``floor``.

    ``floor + (1 - floor) * exp(-distance_km / GEO_SCALE_KM)``, as in
    ``langfamilysim.geo`` (Apache-2.0).
    """
    return floor + (1.0 - floor) * math.exp(-distance_km / GEO_SCALE_KM)


def combined_similarity(score: float, distance_km: float | None, *, areal: bool) -> float:
    """``score`` damped by distance; unchanged when either point is unknown.

    Areal scores take :data:`GEO_FLOOR_AREAL`, genealogical ones
    :data:`GEO_FLOOR_GENEALOGICAL`. This is ``langfamilysim``'s ``combined``
    column, computed per pair at query time instead of read from its
    ``edges.csv``.
    """
    if distance_km is None:
        return score
    return score * geo_factor(distance_km, GEO_FLOOR_AREAL if areal else GEO_FLOOR_GENEALOGICAL)


class Glottolog:
    """In-memory index of languoids by glottocode and ISO 639-3 code."""

    def __init__(self, languoids: Iterable[Languoid]) -> None:
        """Index ``languoids``. Language-level entries win ISO-code collisions."""
        self._by_gc: dict[str, Languoid] = {}
        self._by_iso: dict[str, Languoid] = {}
        for lg in languoids:
            self._by_gc[lg.glottocode] = lg
            if lg.iso:
                existing = self._by_iso.get(lg.iso)
                if existing is None or (existing.level != "language" and lg.level == "language"):
                    self._by_iso[lg.iso] = lg

    def __len__(self) -> int:
        """Number of languoids indexed."""
        return len(self._by_gc)

    def by_glottocode(self, glottocode: str) -> Languoid | None:
        """Look up a languoid by glottocode."""
        return self._by_gc.get(glottocode)

    def by_iso(self, iso: str) -> Languoid | None:
        """Look up a languoid by ISO 639-3 code (script suffixes ignored)."""
        return self._by_iso.get(iso.split("_", maxsplit=1)[0].lower())

    def resolve(self, code: str) -> Languoid | None:
        """Look up by glottocode or ISO 639-3 code, whichever ``code`` is."""
        return self.by_glottocode(code) or self.by_iso(code)

    def similarity(self, a: Languoid, b: Languoid) -> tuple[float, bool]:
        """Return ``(score, shared_country)`` for two languoids.

        Same-family pairs score by path overlap. Cross-family pairs that share
        a country score :data:`AREAL_SCORE`; otherwise 0.
        """
        shared_country = bool(set(a.countries) & set(b.countries))
        score = path_similarity(a, b) if a.family == b.family else 0.0
        if shared_country:
            score = max(score, AREAL_SCORE)
        return score, shared_country

    def combined(self, a: Languoid, b: Languoid) -> float:
        """:meth:`similarity` damped by distance (see :func:`combined_similarity`)."""
        score, _ = self.similarity(a, b)
        areal = a.family != b.family or path_similarity(a, b) < AREAL_SCORE
        return combined_similarity(score, self.distance_km(a, b), areal=areal)

    def distance_km(self, a: Languoid, b: Languoid) -> float | None:
        """Distance between the two Glottolog points, if both are known."""
        if a.lat is None or a.lon is None or b.lat is None or b.lon is None:
            return None
        return haversine_km(a.lat, a.lon, b.lat, b.lon)

    # -- construction -------------------------------------------------------

    @classmethod
    def from_cldf(cls, languages_csv: Path, values_csv: Path) -> Glottolog:
        """Parse the CLDF ``languages.csv`` and ``values.csv`` files."""
        classification: dict[str, str] = {}
        with values_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row["Parameter_ID"] == "classification":
                    classification[row["Language_ID"]] = row["Value"]
        languoids: list[Languoid] = []
        with languages_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                gc = row["ID"]
                ancestors = classification.get(gc, "")
                path = (*ancestors.split("/"), gc) if ancestors else (gc,)
                countries = tuple(c for c in row["Countries"].split(";") if c)
                languoids.append(
                    Languoid(
                        glottocode=gc,
                        name=row["Name"],
                        level=row["Level"],
                        iso=row["ISO639P3code"] or None,
                        countries=countries,
                        lat=float(row["Latitude"]) if row["Latitude"] else None,
                        lon=float(row["Longitude"]) if row["Longitude"] else None,
                        path=path,
                    ),
                )
        return cls(languoids)

    def save(self, path: Path) -> None:
        """Write the compact JSON cache."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump([asdict(lg) for lg in self._by_gc.values()], fh)

    @classmethod
    def from_json(cls, path: Path) -> Glottolog:
        """Read the compact JSON cache written by :meth:`save`."""
        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        return cls(
            Languoid(
                glottocode=item["glottocode"],
                name=item["name"],
                level=item["level"],
                iso=item["iso"],
                countries=tuple(item["countries"]),
                lat=item["lat"],
                lon=item["lon"],
                path=tuple(item["path"]),
            )
            for item in raw
        )

    @classmethod
    def load(cls, settings: Settings) -> Glottolog:
        """Load from the cache, fetching and parsing the CLDF export if needed."""
        cache = settings.cache_dir / CACHE_NAME
        if cache.exists():
            return cls.from_json(cache)
        languages = fetch_cached(LANGUAGES_URL, "glottolog/languages.csv", settings)
        values = fetch_cached(VALUES_URL, "glottolog/values.csv", settings)
        glottolog = cls.from_cldf(languages, values)
        glottolog.save(cache)
        return glottolog
