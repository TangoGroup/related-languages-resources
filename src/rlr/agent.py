"""The agent layer: what the translator actually talks to.

The point of the agentic architecture is that it *hides the underlying
infrastructure* and simply exposes information that is relevant to and
understandable by the user. A translator should never see a source catalogue, a
license class, or a versification rule; they should see verses and notes they
can read, each labelled with where it came from.

This module composes the five stages and enforces the two standing rules:

*   Nothing is presented without its provenance. Every :class:`PassageText`
    carries one by construction, and this layer never strips it.
*   Absence is reported, never silently rendered as an empty result (jobs 2.4
    and 2.5). Every branch that yields nothing yields an :class:`Unavailable`
    with a reason instead.

Composition is deterministic. No language model sits on the request path: the
jobs to be done are retrieval and rendering, and the trust requirement is
easier to meet when every string shown can be traced to a file and a line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rlr import back_translation, catalog, languages, verses
from rlr.config import Settings
from rlr.ebible import EBibleCorpus, vref_path
from rlr.glottolog import Glottolog
from rlr.mt import load_translator
from rlr.resources.figures_of_speech import FiguresOfSpeech
from rlr.types import DISPLAYABLE, PassageText, Provenance, Unavailable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rlr.mt import Translator
    from rlr.resources import ResourceNote, VerseIndexedResource
    from rlr.types import LicenseClass, PassageRef, RelatedLanguage, TranslationContext


@dataclass(frozen=True, slots=True)
class RelatedLanguageReading:
    """One related language's contribution to a briefing."""

    language: RelatedLanguage
    #: The passage as published in the related language.
    original: PassageText
    #: The same passage rendered into the LWC, or why it could not be.
    in_lwc: PassageText | Unavailable


@dataclass(frozen=True, slots=True)
class ResourceReading:
    """One verse-indexed note, in its source language and rendered into the LWC."""

    resource: str
    note: ResourceNote
    original: PassageText
    in_lwc: PassageText | Unavailable


@dataclass(frozen=True, slots=True)
class Briefing:
    """Everything RLR found for one passage, ready to show a translator."""

    context: TranslationContext
    passage: PassageRef
    related: tuple[RelatedLanguage, ...]
    readings: tuple[RelatedLanguageReading, ...]
    notes: tuple[ResourceReading, ...]
    #: Related languages and editions that yielded nothing, with reasons.
    skipped: tuple[Unavailable, ...] = ()
    #: Set when no related language yielded a reading, explaining why.
    nothing_found: Unavailable | None = None
    #: Set when no resource yielded a note, explaining why.
    no_notes: Unavailable | None = None


@dataclass(slots=True)
class Pipeline:
    """The stages and data a briefing is assembled from."""

    settings: Settings
    glottolog: Glottolog
    corpus: EBibleCorpus
    index: verses.VerseIndex
    translator: Translator
    resources: Sequence[VerseIndexedResource] = field(default_factory=tuple)
    permitted_licenses: frozenset[LicenseClass] = DISPLAYABLE
    max_languages: int = languages.DEFAULT_LIMIT
    min_similarity: float = languages.DEFAULT_MIN_SIMILARITY

    def related_languages(self, context: TranslationContext) -> list[RelatedLanguage] | Unavailable:
        """Stage 1 over the languages the corpus actually has."""
        return languages.find_related_languages(
            context,
            self.glottolog,
            self.corpus.languages,
            min_similarity=self.min_similarity,
            limit=self.max_languages,
        )

    def brief(self, context: TranslationContext, passage: PassageRef) -> Briefing:
        """Run the full pipeline and assemble a briefing for ``passage``."""
        related = self.related_languages(context)
        if isinstance(related, Unavailable):
            return Briefing(context, passage, (), (), (), nothing_found=related, no_notes=None)

        skipped: list[Unavailable] = []
        readings: list[RelatedLanguageReading] = []
        for lang in related:
            editions = catalog.available_bibles([lang], self.corpus, self.permitted_licenses)
            if not editions:
                absence = catalog.explain_absence(lang, self.corpus, self.permitted_licenses)
                if absence is not None:
                    skipped.append(absence)
                continue
            for edition in editions:
                text_path = verses.ensure_cached(edition, self.corpus, self.settings)
                original = verses.fetch_passage(edition, passage, self.index, text_path)
                if isinstance(original, Unavailable):
                    skipped.append(original)
                    continue
                in_lwc = back_translation.back_translate(original, context.lwc, self.translator)
                readings.append(RelatedLanguageReading(lang, original, in_lwc))

        nothing_found: Unavailable | None = None
        if not related:
            nothing_found = Unavailable(
                f"no language with a Bible in the eBible Corpus scores at least "
                f"{self.min_similarity} against {context.target_language}",
                context.target_language,
            )
        elif not readings:
            nothing_found = Unavailable(
                f"{len(related)} related language(s) found but none yielded {passage}: "
                + "; ".join(s.reason for s in skipped),
                context.target_language,
            )

        notes = self._notes(context, passage)
        no_notes: Unavailable | None = None
        if not self.resources:
            no_notes = Unavailable("no verse-indexed resources are configured", context.lwc)
        elif not notes:
            names = ", ".join(r.name for r in self.resources)
            no_notes = Unavailable(f"no notes for {passage} in: {names}", context.lwc)

        return Briefing(
            context=context,
            passage=passage,
            related=tuple(related),
            readings=tuple(readings),
            notes=tuple(notes),
            skipped=tuple(skipped),
            nothing_found=nothing_found,
            no_notes=no_notes,
        )

    def _notes(self, context: TranslationContext, passage: PassageRef) -> list[ResourceReading]:
        out: list[ResourceReading] = []
        for resource in self.resources:
            source_lang = resource.source_language()
            for note in resource.notes_for(passage):
                original = PassageText(
                    passage=note.passage,
                    language=source_lang,
                    text=note.body,
                    provenance=note.provenance,
                )
                in_lwc: PassageText | Unavailable
                if source_lang.split("_")[0] == context.lwc.split("_")[0]:
                    in_lwc = original
                elif not note.provenance.license_class.permits_derivatives:
                    in_lwc = Unavailable(
                        f"{note.provenance.license_name or 'the license'} does not permit "
                        "machine translation",
                        context.lwc,
                    )
                elif not self.translator.supports(source_lang, context.lwc):
                    in_lwc = Unavailable(
                        f"no machine translation from {source_lang} into {context.lwc} "
                        f"(backend: {self.translator.name})",
                        context.lwc,
                    )
                else:
                    rendered = self.translator.translate(note.body, source_lang, context.lwc)
                    in_lwc = PassageText(
                        passage=note.passage,
                        language=context.lwc,
                        text=rendered,
                        provenance=Provenance(
                            source=f"machine translation ({self.translator.name}) of "
                            f"{note.provenance.source}",
                            title=note.provenance.title,
                            publisher=note.provenance.publisher,
                            published=note.provenance.published,
                            license_name=note.provenance.license_name,
                            license_class=note.provenance.license_class,
                            url=note.provenance.url,
                        ),
                        derived_from=original,
                    )
                out.append(ResourceReading(resource.name, note, original, in_lwc))
        return out


def build_pipeline(settings: Settings) -> Pipeline:
    """Assemble a :class:`Pipeline` from settings, fetching data as needed."""
    resources: list[VerseIndexedResource] = [FiguresOfSpeech(settings.figures_dir)]
    return Pipeline(
        settings=settings,
        glottolog=Glottolog.load(settings),
        corpus=EBibleCorpus.load(settings),
        index=verses.VerseIndex(vref_path(settings)),
        translator=load_translator(settings),
        resources=tuple(resources),
    )


def brief(
    context: TranslationContext,
    passage: PassageRef,
    settings: Settings | None = None,
) -> Briefing:
    """Convenience wrapper: build a pipeline from the environment and brief."""
    return build_pipeline(settings or Settings.from_env()).brief(context, passage)
