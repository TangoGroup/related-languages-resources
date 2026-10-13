"""Stage 5 — verse-indexed resources available only in English.

The prototype dataset is unfoldingWord's figures-of-speech notes, shipped in
the ``bible-figures-of-speech`` package, but the shape generalises: many
datasets carry
verse-level information and could be delivered the same way.
:class:`VerseIndexedResource` is the interface that makes figures of speech one
implementation rather than a special case.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rlr.types import LanguageCode, PassageRef, Provenance


@dataclass(frozen=True, slots=True)
class NotePart:
    """One translatable unit of a note.

    Sentence-level MT models degrade badly on a whole note (several sentences,
    quoted source text in Greek or Hebrew, lists of alternatives), so a note
    exposes its parts and the pipeline renders each separately. ``translate``
    is False for parts that must stay verbatim, such as quoted scripture.
    """

    role: Literal["summary", "quote", "comment", "alternative"]
    text: str
    translate: bool = True


class ResourceNote(Protocol):
    """A single piece of verse-indexed commentary."""

    @property
    def passage(self) -> PassageRef:
        """The passage the note is attached to."""
        ...

    @property
    def title(self) -> str:
        """A short heading, e.g. the figure-of-speech type."""
        ...

    @property
    def body(self) -> str:
        """The note text, in its source language."""
        ...

    @property
    def parts(self) -> Sequence[NotePart]:
        """The note broken into units for rendering into another language."""
        ...

    @property
    def provenance(self) -> Provenance:
        """Where this note came from and how it may be used."""
        ...


class VerseIndexedResource(Protocol):
    """Any dataset that can answer "what do you have for this passage?"."""

    @property
    def name(self) -> str:
        """Short dataset name for display."""
        ...

    def notes_for(self, passage: PassageRef) -> Sequence[ResourceNote]:
        """Return notes covering ``passage``, possibly empty."""
        ...

    def source_language(self) -> LanguageCode:
        """The language the notes are written in, typically English."""
        ...


__all__ = ["NotePart", "ResourceNote", "VerseIndexedResource"]
