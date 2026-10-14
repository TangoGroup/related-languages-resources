"""Stage 4 — render related-language text into the LWC.

Where translators understand the LWC better than the related language, a back
translation is more useful than the raw text. Three things gate it:

*   **License.** Back-translation is a derivative work. No-derivatives texts
    (most of eBible) are displayed in stage 3 and refused here, with the
    reason stated.
*   **Capability.** Rendering comes from a pluggable :class:`~rlr.mt.Translator`.
    With none configured, the answer is :class:`~rlr.types.Unavailable`, which
    job 2.4 requires to be said out loud rather than left blank.
*   **Trust.** Even when a backend exists, general NMT models drift toward
    the LWC Bible they were trained on (see :mod:`rlr.mt`). The
    output is labelled as machine-generated and carries the backend name in
    its provenance so a translator can weigh it.

Other systems (Scripture Forge, through the Serval API, for example) can be
added as backends; nothing here depends on any particular one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rlr.mt import TranslationUnavailable
from rlr.types import PassageText, Provenance, Unavailable

if TYPE_CHECKING:
    from rlr.mt import Translator
    from rlr.types import LanguageCode


def supports(language: LanguageCode, lwc: LanguageCode, translator: Translator) -> bool:
    """Whether a rendering from ``language`` into ``lwc`` can be produced."""
    return translator.supports(language, lwc)


def back_translate(
    source: PassageText,
    lwc: LanguageCode,
    translator: Translator,
) -> PassageText | Unavailable:
    """Render ``source`` into ``lwc``, or say why that cannot be done.

    Args:
        source: Retrieved related-language passage text.
        lwc: The Language of Wider Communication to render into.
        translator: The machine-translation backend.

    Returns:
        The rendered passage with ``derived_from`` set to ``source``, or
        :class:`Unavailable` naming the license or capability that is missing.
    """
    if source.language.split("_")[0] == lwc.split("_")[0]:
        return Unavailable(f"{source.language} already is the LWC", lwc)
    if not source.provenance.license_class.permits_derivatives:
        return Unavailable(
            f"{source.provenance.title} is licensed {source.provenance.license_name or 'unknown'}, "
            "which does not permit derivative works such as back-translation",
            lwc,
        )
    if not translator.supports(source.language, lwc):
        return Unavailable(
            f"no back-translation capability from {source.language} into {lwc} "
            f"(backend: {translator.name})",
            lwc,
        )
    try:
        rendered = translator.translate(source.text, source.language, lwc)
    except TranslationUnavailable as exc:
        return Unavailable(str(exc), lwc)
    return PassageText(
        passage=source.passage,
        language=lwc,
        text=rendered,
        provenance=Provenance(
            source=f"machine back-translation ({translator.name})",
            title=f"{source.provenance.title}, rendered into {lwc}",
            publisher=source.provenance.publisher,
            published=source.provenance.published,
            license_name=source.provenance.license_name,
            license_class=source.provenance.license_class,
            url=source.provenance.url,
        ),
        derived_from=source,
    )
