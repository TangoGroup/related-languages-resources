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

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from rlr import back_translation, catalog, languages, verses
from rlr.config import Settings
from rlr.ebible import EBibleCorpus, vref_path
from rlr.glottolog import Glottolog
from rlr.mt import load_translator
from rlr.resources import NotePart
from rlr.resources.figures_of_speech import ALTERNATIVES_LABEL, FiguresOfSpeech, assemble
from rlr.types import DISPLAYABLE, LicenseClass, PassageText, Provenance, Unavailable

#: Preference order when an LWC has several editions: most open first.
_LICENSE_RANK: dict[LicenseClass, int] = {
    LicenseClass.OPEN: 0,
    LicenseClass.NONCOMMERCIAL: 1,
    LicenseClass.DERIVATIVES_FORBIDDEN: 2,
    LicenseClass.UNKNOWN: 3,
}

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rlr.mt import Translator
    from rlr.resources import ResourceNote, VerseIndexedResource
    from rlr.types import LanguageCode, PassageRef, RelatedLanguage, TranslationContext


@dataclass(frozen=True, slots=True)
class RelatedLanguageReading:
    """One related language's contribution to a briefing."""

    language: RelatedLanguage
    #: The passage as published in the related language.
    original: PassageText
    #: The same passage rendered into the LWC, why it could not be, or ``None``
    #: when no rendering was attempted because the LWC has an open Bible of its
    #: own (:attr:`Briefing.lwc_reading`), which the translator can read directly.
    in_lwc: PassageText | Unavailable | None


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
    #: The passage in the LWC's own Bible, shown before the related readings:
    #: the LWC is almost always the translator's source text (2026-09-25).
    lwc_reading: PassageText | Unavailable | None = None


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
        """Stage 1 over the languages the corpus actually has.

        The LWC itself is never a *related* language: its text is shown
        separately as :attr:`Briefing.lwc_reading`.
        """
        context = replace(context, excluded_languages=context.excluded_languages | {context.lwc})
        return languages.find_related_languages(
            context,
            self.glottolog,
            self.corpus.languages,
            min_similarity=self.min_similarity,
            limit=self.max_languages,
        )

    def lwc_reading(
        self, context: TranslationContext, passage: PassageRef
    ) -> PassageText | Unavailable:
        """The passage in the LWC's own Bible, from its most openly licensed edition."""
        editions = [
            e
            for e in self.corpus.editions_for(context.lwc)
            if e.provenance.license_class in self.permitted_licenses
        ]
        if not editions:
            return Unavailable(
                f"no Bible in {context.lwc} in the eBible Corpus with a displayable license",
                context.lwc,
            )
        edition = min(
            editions, key=lambda e: (_LICENSE_RANK[e.provenance.license_class], e.edition_id)
        )
        text_path = verses.ensure_cached(edition, self.corpus, self.settings)
        return verses.fetch_passage(edition, passage, self.index, text_path)

    def brief(self, context: TranslationContext, passage: PassageRef) -> Briefing:
        """Run the full pipeline and assemble a briefing for ``passage``."""
        lwc_reading = self.lwc_reading(context, passage)
        related = self.related_languages(context)
        if isinstance(related, Unavailable):
            return Briefing(
                context,
                passage,
                (),
                (),
                (),
                nothing_found=related,
                no_notes=None,
                lwc_reading=lwc_reading,
            )

        skipped: list[Unavailable] = []
        found = {r.code for r in related}
        for code in sorted(context.included_languages):
            if code.split("_")[0] not in found and code.split("_")[0] != context.lwc.split("_")[0]:
                skipped.append(
                    Unavailable(f"{code} was requested but has no Bible in the eBible Corpus", code)
                )
        readings: list[RelatedLanguageReading] = []
        has_lwc_bible = isinstance(lwc_reading, PassageText)
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
                in_lwc = (
                    None
                    if has_lwc_bible
                    else back_translation.back_translate(original, context.lwc, self.translator)
                )
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
            lwc_reading=lwc_reading,
        )

    def _render_note(self, note: ResourceNote, source: LanguageCode, target: LanguageCode) -> str:
        """Translate a note part by part; quoted source text stays verbatim."""
        rendered = [
            NotePart(
                p.role, self.translator.translate(p.text, source, target) if p.translate else p.text
            )
            for p in note.parts
        ]
        label = self.translator.translate(ALTERNATIVES_LABEL, source, target).rstrip(":")
        return assemble(rendered, label)

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
                    rendered = self._render_note(note, source_lang, context.lwc)
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
