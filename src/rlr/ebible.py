"""The eBible Corpus: metadata, licenses and verse-per-line text files.

``BibleNLP/ebible`` publishes three metadata files this module reads:

* ``translations.csv`` — one row per translation with title, copyright,
  publication URL and update date.
* ``licences.tsv`` — the license type per translation (``Public Domain``,
  ``by``, ``by-sa``, ``by-nd``, ``by-nc-nd``, ``Unknown``…), the copyright
  holder and years.
* ``lang_details.tsv`` — the corpus manifest: which ``<lang>-<id>.txt`` files
  actually exist, with language name, family and country.

The license data is carried through the pipeline into
:class:`~rlr.types.Provenance`, because job 2.2 makes it a user-facing answer
and because stages 4 and 5 must refuse derivative work on no-derivatives
texts.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from rlr.config import fetch_cached
from rlr.types import BibleEdition, LicenseClass, Provenance

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from rlr.config import Settings
    from rlr.types import LanguageCode

RAW_BASE = "https://raw.githubusercontent.com/BibleNLP/ebible/main"
TRANSLATIONS_URL = f"{RAW_BASE}/metadata/translations.csv"
LICENCES_URL = f"{RAW_BASE}/metadata/licences.tsv"
LANG_DETAILS_URL = f"{RAW_BASE}/metadata/lang_details.tsv"
VREF_URL = f"{RAW_BASE}/metadata/vref.txt"

SOURCE_NAME = "eBible Corpus (BibleNLP/ebible)"

_LICENSE_CLASSES: dict[str, LicenseClass] = {
    "public domain": LicenseClass.OPEN,
    "by": LicenseClass.OPEN,
    "by-sa": LicenseClass.OPEN,
    "by-nc": LicenseClass.NONCOMMERCIAL,
    "by-nc-sa": LicenseClass.NONCOMMERCIAL,
    "by-nd": LicenseClass.DERIVATIVES_FORBIDDEN,
    "by-nc-nd": LicenseClass.DERIVATIVES_FORBIDDEN,
}


def license_class(licence_type: str) -> LicenseClass:
    """Map an eBible ``Licence Type`` value onto :class:`LicenseClass`."""
    return _LICENSE_CLASSES.get(licence_type.strip().lower(), LicenseClass.UNKNOWN)


def license_name(licence_type: str, version: str) -> str | None:
    """Render ``by-nc-nd`` / ``4.0`` as ``CC BY-NC-ND 4.0``."""
    kind = licence_type.strip()
    if not kind or kind.lower() == "unknown":
        return None
    if kind.lower() == "public domain":
        return "Public Domain"
    label = f"CC {kind.upper()}"
    return f"{label} {version.strip()}" if version.strip() else label


@dataclass(frozen=True, slots=True)
class CorpusFile:
    """One verse-per-line file in the corpus manifest."""

    filename: str
    language: LanguageCode
    translation_id: str
    language_name: str
    family: str
    country: str

    @property
    def url(self) -> str:
        """Raw download URL on GitHub."""
        return f"{RAW_BASE}/corpus/{self.filename}"


class EBibleCorpus:
    """Metadata index over the eBible Corpus."""

    def __init__(
        self,
        files: Iterable[CorpusFile],
        translations: dict[str, dict[str, str]],
        licences: dict[str, dict[str, str]],
    ) -> None:
        """Index the manifest, ``translations.csv`` rows and ``licences.tsv`` rows."""
        self._files = list(files)
        self._by_language: dict[str, list[CorpusFile]] = {}
        for f in self._files:
            self._by_language.setdefault(f.language, []).append(f)
        self._translations = translations
        self._licences = licences

    @property
    def languages(self) -> frozenset[LanguageCode]:
        """ISO 639-3 codes with at least one corpus file."""
        return frozenset(self._by_language)

    def files_for(self, language: LanguageCode) -> list[CorpusFile]:
        """Corpus files for ``language`` (bare ISO 639-3 code)."""
        return list(self._by_language.get(language.split("_")[0], []))

    def edition(self, corpus_file: CorpusFile) -> BibleEdition:
        """Build a :class:`BibleEdition` with full provenance for a corpus file."""
        tid = corpus_file.translation_id
        meta = self._translations.get(tid, {})
        lic = self._licences.get(tid) or self._licences.get(corpus_file.language, {})
        licence_type = lic.get("Licence Type", "")
        holder = lic.get("Copyright Holder", "").strip() or meta.get("Copyright", "").strip()
        years = lic.get("Copyright Years", "").strip()
        title = meta.get("title", "").strip() or corpus_file.language_name
        return BibleEdition(
            language=corpus_file.language,
            edition_id=tid,
            language_name=corpus_file.language_name,
            provenance=Provenance(
                source=SOURCE_NAME,
                title=title,
                publisher=holder or None,
                published=years or meta.get("UpdateDate", "").strip() or None,
                license_name=license_name(licence_type, lic.get("Licence Version", "")),
                license_class=license_class(licence_type),
                url=meta.get("publicationURL", "").strip() or None,
            ),
        )

    def editions_for(self, language: LanguageCode) -> list[BibleEdition]:
        """All editions for ``language``, with provenance."""
        return [self.edition(f) for f in self.files_for(language)]

    def corpus_file(self, edition: BibleEdition) -> CorpusFile | None:
        """The manifest entry behind ``edition``."""
        for f in self._by_language.get(edition.language, []):
            if f.translation_id == edition.edition_id:
                return f
        return None

    # -- construction -------------------------------------------------------

    @classmethod
    def from_files(cls, translations_csv: Path, licences_tsv: Path, lang_details_tsv: Path) -> Self:
        """Parse the three metadata files."""
        with translations_csv.open(encoding="utf-8-sig", newline="") as fh:
            translations = {row["translationId"]: row for row in csv.DictReader(fh)}
        with licences_tsv.open(encoding="utf-8", newline="") as fh:
            licences = {row["ID"]: row for row in csv.DictReader(fh, delimiter="\t")}
        files: list[CorpusFile] = []
        with lang_details_tsv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                filename = row["file"]
                stem = filename.rsplit(".", 1)[0]
                _, _, tid = stem.partition("-")
                files.append(
                    CorpusFile(
                        filename=filename,
                        language=row["code"],
                        translation_id=tid or row["code"],
                        language_name=row["lang"],
                        family=row["family"],
                        country=row["country"],
                    ),
                )
        return cls(files, translations, licences)

    @classmethod
    def load(cls, settings: Settings) -> Self:
        """Fetch the metadata files into the cache (once) and parse them."""
        return cls.from_files(
            fetch_cached(TRANSLATIONS_URL, "ebible/translations.csv", settings),
            fetch_cached(LICENCES_URL, "ebible/licences.tsv", settings),
            fetch_cached(LANG_DETAILS_URL, "ebible/lang_details.tsv", settings),
        )


def vref_path(settings: Settings) -> Path:
    """Local path of ``vref.txt``, fetched into the cache if needed."""
    return fetch_cached(VREF_URL, "ebible/vref.txt", settings)
