"""Core domain types shared across the pipeline stages.

Two conventions are load-bearing and deliberate:

*   Retrieval is addressed by :class:`PassageRef`, never by a bare verse.
    Decision D3 broadens the unit of interest to "verse or pericope"; only the
    single-verse case is implemented first, but the interface must not assume
    it.
*   Every text that reaches a translator carries a :class:`Provenance`.
    "Providing trusted information is a high priority" is a requirement, so
    provenance is a constructor argument, not an optional annotation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# ISO 639-3 code, optionally suffixed with a script subtag as some sources
# emit it (e.g. "ful_Latn"). Stage functions normalise to the bare code.
LanguageCode = str

_REF_RE = re.compile(r"^\s*([1-4]?[A-Z]{2,3})\s+(\d+):(\d+)\s*$")
_RANGE_RE = re.compile(
    r"^\s*([1-4]?[A-Z]{2,3})\s+(\d+):(\d+)\s*-\s*(?:(\d+):)?(\d+)\s*$",
)


@dataclass(frozen=True, slots=True)
class Location:
    """A point used to weight geographic proximity between languages."""

    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class TranslationContext:
    """What the translator is working on, and what they can read."""

    target_language: LanguageCode
    lwc: LanguageCode
    location: Location | None = None
    #: Languages the translator has asked never to be shown again (Q4).
    excluded_languages: frozenset[LanguageCode] = field(default_factory=frozenset)
    #: Languages the translator says they know, to consult whether or not the
    #: tree says they are related (review feedback, 2026-10-13).
    included_languages: frozenset[LanguageCode] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class RelatedLanguage:
    """A language identified as closely related to the target language.

    ``similarity`` is the Glottolog classification-path overlap used by
    the in-house language-similarity measure: the fraction of the shorter path shared
    with the target, so 1.0 is the same language and 0.0 a different family.
    ``shared_country`` records the areal signal separately, since a neighbour
    across a family boundary can still be a useful Language of Wider
    Communication.
    """

    code: LanguageCode
    name: str
    similarity: float
    glottocode: str | None = None
    shared_country: bool = False
    #: Great-circle distance between the Glottolog points, when both are known.
    distance_km: float | None = None
    location: Location | None = None
    #: True when the translator asked for this language rather than the tree
    #: proposing it; such languages bypass the similarity threshold.
    requested: bool = False


@dataclass(frozen=True, slots=True)
class VerseRef:
    """A single verse in the Original versification used by ``vref.txt``."""

    book: str
    chapter: int
    verse: int

    @classmethod
    def parse(cls, text: str) -> VerseRef:
        """Parse a ``BOOK C:V`` reference such as ``MRK 1:6`` (case-insensitive)."""
        m = _REF_RE.match(text.strip().upper())
        if not m:
            msg = f"not a verse reference: {text!r} (expected e.g. 'MRK 1:6')"
            raise ValueError(msg)
        return cls(book=m.group(1), chapter=int(m.group(2)), verse=int(m.group(3)))

    def __str__(self) -> str:
        """Render in ``vref.txt`` form."""
        return f"{self.book} {self.chapter}:{self.verse}"


@dataclass(frozen=True, slots=True)
class PassageRef:
    """An inclusive verse range.

    A single verse is the degenerate case where ``start == end``; use
    :meth:`verse` to build one rather than special-casing at call sites.
    """

    start: VerseRef
    end: VerseRef

    @classmethod
    def verse(cls, ref: VerseRef) -> PassageRef:
        """Build a single-verse passage."""
        return cls(start=ref, end=ref)

    @classmethod
    def parse(cls, text: str) -> PassageRef:
        """Parse ``MRK 1:6``, ``MRK 1:4-8`` or ``MRK 1:40-2:3`` (case-insensitive)."""
        m = _RANGE_RE.match(text.strip().upper())
        if m:
            book, chapter, verse = m.group(1), int(m.group(2)), int(m.group(3))
            end_chapter = int(m.group(4)) if m.group(4) else chapter
            end_verse = int(m.group(5))
            return cls(
                start=VerseRef(book, chapter, verse),
                end=VerseRef(book, end_chapter, end_verse),
            )
        return cls.verse(VerseRef.parse(text))

    @property
    def is_single_verse(self) -> bool:
        """Whether this passage covers exactly one verse."""
        return self.start == self.end

    @property
    def book(self) -> str:
        """The USFM book code the passage starts in."""
        return self.start.book

    def __str__(self) -> str:
        """Render as ``MRK 1:6`` or ``MRK 1:4-8`` / ``MRK 1:40-2:3``."""
        if self.is_single_verse:
            return str(self.start)
        if self.start.book == self.end.book and self.start.chapter == self.end.chapter:
            return f"{self.start}-{self.end.verse}"
        return f"{self.start}-{self.end.chapter}:{self.end.verse}"


class LicenseClass(Enum):
    """How freely a source may be used, in decreasing order of freedom.

    ``DERIVATIVES_FORBIDDEN`` matters more than it looks: back-translation and
    machine translation are both derivative works, so sources in that class are
    unusable for stages 4 and 5 even when they are readable in stage 3. Per
    decision D8 (2026-09-23) that is acceptable: no-derivatives texts may be
    retrieved and shown, just not rendered into the LWC.
    """

    OPEN = "open"
    #: Derivatives allowed, commercial use not (CC BY-NC). Fine for this
    #: prototype, which is non-commercial, but flagged rather than folded in.
    NONCOMMERCIAL = "noncommercial"
    AGREEMENT_REQUIRED = "agreement_required"
    DERIVATIVES_FORBIDDEN = "derivatives_forbidden"
    AI_USE_FORBIDDEN = "ai_use_forbidden"
    UNKNOWN = "unknown"

    @property
    def permits_display(self) -> bool:
        """Whether the text itself may be shown to a translator verbatim."""
        return self in DISPLAYABLE

    @property
    def permits_derivatives(self) -> bool:
        """Whether back-translation or machine translation is permitted."""
        return self in DERIVABLE


#: License classes whose texts may be retrieved and displayed (stage 3).
DISPLAYABLE: frozenset[LicenseClass] = frozenset(
    {LicenseClass.OPEN, LicenseClass.NONCOMMERCIAL, LicenseClass.DERIVATIVES_FORBIDDEN},
)
#: License classes whose texts may be back- or machine-translated (stages 4, 5).
DERIVABLE: frozenset[LicenseClass] = frozenset({LicenseClass.OPEN, LicenseClass.NONCOMMERCIAL})


@dataclass(frozen=True, slots=True)
class Provenance:
    """Answers job-to-be-done 2.2: what is this, who made it, may I use it."""

    source: str
    title: str
    publisher: str | None = None
    published: str | None = None
    license_name: str | None = None
    license_class: LicenseClass = LicenseClass.UNKNOWN
    url: str | None = None


@dataclass(frozen=True, slots=True)
class BibleEdition:
    """A specific Bible text available in a specific language."""

    language: LanguageCode
    edition_id: str
    provenance: Provenance
    #: Human-readable language name from the corpus metadata.
    language_name: str | None = None


@dataclass(frozen=True, slots=True)
class PassageText:
    """Retrieved text for a passage, in some language, with its provenance."""

    passage: PassageRef
    language: LanguageCode
    text: str
    provenance: Provenance
    #: Set when this text was produced by back-translation or machine
    #: translation rather than retrieved as-published.
    derived_from: PassageText | None = None


@dataclass(frozen=True, slots=True)
class Unavailable:
    """An explicit "nothing here", which is a result and not an error.

    Jobs 2.4 and 2.5 require the translator to be told when nothing is
    available. Returning an empty collection loses the reason, so stages return
    this instead.
    """

    reason: str
    language: LanguageCode | None = None
