"""unfoldingWord figures-of-speech notes, from the ``bible-figures-of-speech`` package.

Figures of speech are an important translation use case, and the data does not
exist for most languages, which is exactly why it is worth machine-translating
into the LWC rather than leaving it in English.

The dataset (19 figure types, about 27,000 verse-indexed instances) is
unfoldingWord's Translation Notes and translationAcademy content, CC BY-SA 4.0,
reorganised and published on PyPI as ``bible-figures-of-speech``. The data ships
inside that package, so stage 5 needs no checkout or download. This module is a
thin adapter that presents the package's records as :class:`ResourceNote` with
RLR's own :class:`~rlr.types.PassageRef` and :class:`~rlr.types.Provenance`.

Both halves reach the translator: the general information about the type and
the specific information about the verse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import bible_figures_of_speech as bfs

from rlr.resources import NotePart
from rlr.types import LicenseClass, PassageRef, Provenance, VerseRef

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from bible_figures_of_speech import FigureInstance, FigureType

    from rlr.types import LanguageCode

SOURCE_NAME = f"{bfs.SOURCE_NAME} (bible-figures-of-speech {bfs.__version__})"
LICENSE_NAME = bfs.DATA_LICENSE


class _VerseId(Protocol):
    def to_usfm(self) -> str: ...


class _Span(Protocol):
    """The slice of biblelib's ``BCVIDRange`` this module relies on."""

    @property
    def startid(self) -> _VerseId: ...

    @property
    def endid(self) -> _VerseId: ...


def passage_of(span: _Span) -> PassageRef:
    """Convert a biblelib verse range into RLR's :class:`PassageRef`."""
    return PassageRef(
        start=VerseRef.parse(span.startid.to_usfm()),
        end=VerseRef.parse(span.endid.to_usfm()),
    )


@dataclass(frozen=True, slots=True)
class FigureNote:
    """One instance joined with its type: what :class:`ResourceNote` promises.

    A flat record (rather than a wrapper around the package's instance) so the
    JSON the CLI and demo server emit stays the same shape as before.
    """

    passage: PassageRef
    figure: FigureType
    source_text: str
    translation: str
    comment: str
    alternate_translations: tuple[str, ...]
    note_id: str

    @classmethod
    def from_instance(cls, instance: FigureInstance) -> FigureNote:
        """Build a note from a ``bible-figures-of-speech`` instance."""
        return cls(
            passage=passage_of(instance.passage),
            figure=instance.figure,
            source_text=instance.source_text,
            translation=instance.translation,
            comment=instance.comment,
            alternate_translations=instance.alternate_translations,
            note_id=instance.id,
        )

    @property
    def title(self) -> str:
        """The figure-of-speech label."""
        return self.figure.label

    @property
    def parts(self) -> tuple[NotePart, ...]:
        """Summary, quoted text (verbatim), comment, then each alternative."""
        out = [NotePart("summary", f"{self.figure.label}: {self.figure.summary}")]
        if self.translation:
            quoted = f"“{self.translation}”"
            if self.source_text:
                quoted += f" ({self.source_text})"
            out.append(NotePart("quote", quoted, translate=False))
        if self.comment:
            out.append(NotePart("comment", self.comment))
        out.extend(NotePart("alternative", alt) for alt in self.alternate_translations)
        return tuple(out)

    @property
    def body(self) -> str:
        """Type summary, then the verse-specific comment and alternatives."""
        return assemble(self.parts)

    @property
    def provenance(self) -> Provenance:
        """unfoldingWord, CC BY-SA 4.0, via ``bible-figures-of-speech``."""
        return Provenance(
            source=SOURCE_NAME,
            title=f"{self.title} at {self.passage} (note {self.note_id})",
            publisher=bfs.PUBLISHER,
            license_name=LICENSE_NAME,
            license_class=LicenseClass.OPEN,
            url=self.figure.source_url,
        )


ALTERNATIVES_LABEL = "Alternate translation"


def assemble(parts: Sequence[NotePart], label: str = ALTERNATIVES_LABEL) -> str:
    """Join note parts back into display text, alternatives on one line."""
    lines = [p.text for p in parts if p.role != "alternative"]
    alts = [p.text for p in parts if p.role == "alternative"]
    if alts:
        lines.append(f"{label}: {'; '.join(alts)}")
    return "\n".join(lines)


class FiguresOfSpeech:
    """Verse-indexed figure-of-speech notes (stage 5's prototype dataset)."""

    name = "figures of speech (unfoldingWord)"

    def __init__(self, data_dir: Path | None = None) -> None:
        """Load the bundled data, or a different snapshot from ``data_dir``.

        Args:
            data_dir: Directory containing ``figs_types.yaml`` and
                ``figs_instances/``; ``None`` uses the package's own copy.

        Raises:
            FileNotFoundError: If ``data_dir`` is given and has no catalog.
        """
        self.data_dir = data_dir
        try:
            self._fos = bfs.FiguresOfSpeech(data_dir)
        except FileNotFoundError as exc:
            msg = f"{exc}; RLR_FIGURES_DIR must hold figs_types.yaml and figs_instances/"
            raise FileNotFoundError(msg) from exc

    @property
    def types(self) -> dict[str, FigureType]:
        """The figure-type catalog, keyed by slug."""
        return self._fos.types

    def source_language(self) -> LanguageCode:
        """The notes are written in English."""
        return self._fos.source_language()

    def books(self) -> list[str]:
        """USFM codes of books with instance data, in canonical order."""
        return self._fos.books()

    def notes_in(self, book: str) -> Sequence[FigureNote]:
        """Every note for a book (USFM code), in file order."""
        return [FigureNote.from_instance(n) for n in self._fos.instances(book)]

    def notes_for(self, passage: PassageRef) -> Sequence[FigureNote]:
        """Return figure-of-speech notes overlapping ``passage``, in file order."""
        return [FigureNote.from_instance(n) for n in self._fos.notes_for(passage)]
