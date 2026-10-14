"""Stage 2 — which related languages actually have a usable Bible.

"Usable" is two questions, not one: does a text exist, and may we do what we
intend to do with it. Back-translation and machine translation are derivative
works, so a source that forbids derivatives fails stage 2 for stages 4 and 5
even though its text can be displayed verbatim.

The source is the eBible Corpus, whose ``licences.tsv`` supplies the license
per translation directly. No-derivatives texts may be retrieved and shown;
they are never back-translated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rlr.types import DISPLAYABLE, BibleEdition, Unavailable

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rlr.ebible import EBibleCorpus
    from rlr.types import LicenseClass, RelatedLanguage


def available_bibles(
    languages: Iterable[RelatedLanguage],
    corpus: EBibleCorpus,
    permitted_licenses: frozenset[LicenseClass] = DISPLAYABLE,
) -> list[BibleEdition]:
    """Return the Bible editions available for ``languages``, in input order.

    Args:
        languages: Candidate related languages from stage 1.
        corpus: The eBible metadata index.
        permitted_licenses: License classes to accept. Defaults to everything
            that may be displayed; pass :data:`rlr.types.DERIVABLE` to keep only
            texts that may also be back-translated.

    Returns:
        One or more editions per language that has any; languages with none
        are simply absent. Use :func:`explain_absence` to say why.
    """
    editions: list[BibleEdition] = []
    for lang in languages:
        editions.extend(
            e
            for e in corpus.editions_for(lang.code)
            if e.provenance.license_class in permitted_licenses
        )
    return editions


def explain_absence(
    language: RelatedLanguage,
    corpus: EBibleCorpus,
    permitted_licenses: frozenset[LicenseClass] = DISPLAYABLE,
) -> Unavailable | None:
    """Say why ``language`` contributed no edition, or ``None`` if it did."""
    editions = corpus.editions_for(language.code)
    if not editions:
        return Unavailable(f"no Bible text for {language.name} in the eBible Corpus", language.code)
    if all(e.provenance.license_class not in permitted_licenses for e in editions):
        classes = sorted({e.provenance.license_class.value for e in editions})
        return Unavailable(
            f"{language.name} has {len(editions)} edition(s) but none with a permitted "
            f"license (found: {', '.join(classes)})",
            language.code,
        )
    return None
