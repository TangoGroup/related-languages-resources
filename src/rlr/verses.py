"""Stage 3 — retrieve passage text from the corpus.

The eBible Corpus presents each Bible verse-per-line, aligned to a canonical
book/chapter/verse list based on the Original versification. The reference list
lives in ``vref.txt``; reference and text are correlated by iterating the two
files in parallel. Extraction has already normalised each edition to that
versification, so a line number is a verse.

Two corpus conventions matter:

*   A blank line means the verse is not in that edition.
*   A verse range in the source (say Gen 1:1-3) puts all the text on the first
    verse's line and the token ``<range>`` on the others.

Pericopes (decision D3) are simply multi-verse :class:`~rlr.types.PassageRef`
values; retrieval already handles them. What is still missing is a pericope
dataset to pick ranges from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rlr.config import fetch_cached
from rlr.types import PassageText, Unavailable

if TYPE_CHECKING:
    from pathlib import Path

    from rlr.config import Settings
    from rlr.ebible import EBibleCorpus
    from rlr.types import BibleEdition, PassageRef, VerseRef

RANGE_MARKER = "<range>"


#: The 66 books of the Protestant canon, in USFM order. ``vref.txt`` also lists
#: deuterocanonical books, which most translation agencies do not translate, so
#: user-facing verse counts are taken over this set.
PROTESTANT_BOOKS: frozenset[str] = frozenset(
    [
        "GEN",
        "EXO",
        "LEV",
        "NUM",
        "DEU",
        "JOS",
        "JDG",
        "RUT",
        "1SA",
        "2SA",
        "1KI",
        "2KI",
        "1CH",
        "2CH",
        "EZR",
        "NEH",
        "EST",
        "JOB",
        "PSA",
        "PRO",
        "ECC",
        "SNG",
        "ISA",
        "JER",
        "LAM",
        "EZK",
        "DAN",
        "HOS",
        "JOL",
        "AMO",
        "OBA",
        "JON",
        "MIC",
        "NAM",
        "HAB",
        "ZEP",
        "HAG",
        "ZEC",
        "MAL",
        "MAT",
        "MRK",
        "LUK",
        "JHN",
        "ACT",
        "ROM",
        "1CO",
        "2CO",
        "GAL",
        "EPH",
        "PHP",
        "COL",
        "1TH",
        "2TH",
        "1TI",
        "2TI",
        "TIT",
        "PHM",
        "HEB",
        "JAS",
        "1PE",
        "2PE",
        "1JN",
        "2JN",
        "3JN",
        "JUD",
        "REV",
    ]
)


class VerseIndex:
    """A ``vref.txt``-backed index mapping references to corpus line numbers."""

    def __init__(self, vref_path: Path) -> None:
        """Load the canonical verse reference list.

        Args:
            vref_path: Path to ``vref.txt``.
        """
        self._refs: list[str] = vref_path.read_text(encoding="utf-8").splitlines()
        self._index: dict[str, int] = {ref: i for i, ref in enumerate(self._refs)}

    def __len__(self) -> int:
        """Number of verse references, deuterocanon included."""
        return len(self._refs)

    def count_in(self, books: frozenset[str] = PROTESTANT_BOOKS) -> int:
        """Number of verse references whose book is in ``books``."""
        return sum(1 for ref in self._refs if ref.split(" ", 1)[0] in books)

    def __contains__(self, ref: VerseRef) -> bool:
        """Whether ``ref`` is in the canonical list."""
        return str(ref) in self._index

    def line_number(self, ref: VerseRef) -> int:
        """0-based corpus line for a single verse."""
        try:
            return self._index[str(ref)]
        except KeyError:
            msg = f"{ref} is not in the canonical verse list"
            raise KeyError(msg) from None

    def line_numbers(self, passage: PassageRef) -> range:
        """Return the corpus line numbers covering ``passage``.

        Args:
            passage: The passage of interest, in Original versification.

        Returns:
            The half-open range of 0-based line numbers.
        """
        start = self.line_number(passage.start)
        end = self.line_number(passage.end)
        if end < start:
            msg = f"passage end {passage.end} precedes start {passage.start}"
            raise ValueError(msg)
        return range(start, end + 1)

    def reference(self, line: int) -> str:
        """The ``BOOK C:V`` reference at a 0-based line."""
        return self._refs[line]


def ensure_cached(edition: BibleEdition, corpus: EBibleCorpus, settings: Settings) -> Path:
    """Download ``edition``'s verse-per-line file into the cache if absent.

    Args:
        edition: The Bible edition to cache.
        corpus: The corpus metadata, used to find the file name.
        settings: Runtime settings (cache location, offline flag).

    Returns:
        Path to the local verse-per-line file.

    Raises:
        KeyError: If the edition is not in the corpus manifest.
    """
    corpus_file = corpus.corpus_file(edition)
    if corpus_file is None:
        msg = f"{edition.edition_id} is not in the eBible corpus manifest"
        raise KeyError(msg)
    return fetch_cached(corpus_file.url, f"ebible/corpus/{corpus_file.filename}", settings)


def read_passage_lines(text_path: Path, lines: range) -> list[str]:
    """Return the raw lines of ``text_path`` at ``lines`` (0-based, half-open)."""
    out: list[str] = []
    with text_path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= lines.stop:
                break
            if i >= lines.start:
                out.append(line.rstrip("\n"))
    return out


def fetch_passage(
    edition: BibleEdition,
    passage: PassageRef,
    index: VerseIndex,
    text_path: Path,
) -> PassageText | Unavailable:
    """Retrieve the text of ``passage`` from ``edition``.

    Args:
        edition: The Bible edition to read from.
        passage: The passage of interest.
        index: The canonical verse index.
        text_path: The edition's local verse-per-line file.

    Returns:
        The passage text with provenance attached, or :class:`Unavailable`
        explaining why there is none.
    """
    try:
        lines = index.line_numbers(passage)
    except KeyError as exc:
        return Unavailable(str(exc), edition.language)
    raw = read_passage_lines(text_path, lines)
    if len(raw) < len(lines):
        return Unavailable(
            f"{edition.edition_id} is shorter than the canonical verse list at {passage}",
            edition.language,
        )
    verses = [v.strip() for v in raw if v.strip() and v.strip() != RANGE_MARKER]
    if not verses:
        return Unavailable(f"{edition.edition_id} has no text for {passage}", edition.language)
    return PassageText(
        passage=passage,
        language=edition.language,
        text=" ".join(verses),
        provenance=edition.provenance,
    )
