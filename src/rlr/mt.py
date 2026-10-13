"""Machine translation backends, shared by stages 4 and 5.

Machine translation for RLR comes from XRI's own models. The interface is a
small :class:`Translator` protocol so the pipeline can ask two questions,
"can you render into this language?" and "then do so", without knowing what
sits behind them. Absence is a first-class answer: the default backend
supports nothing, so every LWC rendering comes back as
:class:`~rlr.types.Unavailable` until a real backend is configured.

The one concrete backend is MADLAD-400 (``google/madlad400-3b-mt``,
Apache-2.0), a multilingual NMT model. It runs locally through
``transformers`` and is installed with the ``mt`` extra. One caution applies:
MADLAD's training data includes a Swahili Bible, so when back-translating
scripture it tends to drift toward that text rather than the source. Treat
stage 4 output as a reading aid, not a literal back-translation.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rlr.config import Settings
    from rlr.renderings import RenderingCache
    from rlr.types import LanguageCode

#: ISO 639-3 codes whose MADLAD language tag is the two-letter ISO 639-1 code.
_ISO3_TO_MADLAD: dict[str, str] = {
    "eng": "en",
    "fra": "fr",
    "spa": "es",
    "por": "pt",
    "swh": "sw",
    "swa": "sw",
    "hau": "ha",
    "ind": "id",
    "zsm": "ms",
    "hin": "hi",
    "nep": "ne",
    "rus": "ru",
    "arb": "ar",
    "amh": "am",
    "som": "so",
    "yor": "yo",
    "ibo": "ig",
    "lug": "lg",
    "lin": "ln",
    "kin": "rw",
    "run": "rn",
    "nya": "ny",
    "sna": "sn",
    "zul": "zu",
    "xho": "xh",
    "tgl": "tl",
    "ceb": "ceb",
    "vie": "vi",
    "tha": "th",
    "khm": "km",
    "mya": "my",
    "ben": "bn",
    "urd": "ur",
    "tpi": "tpi",
}


def madlad_tag(code: LanguageCode) -> str:
    """The MADLAD target-language tag for an ISO 639-3 code, e.g. ``<2sw>``."""
    bare = code.split("_")[0].lower()
    return f"<2{_ISO3_TO_MADLAD.get(bare, bare)}>"


class TranslationUnavailable(RuntimeError):
    """Raised when a backend cannot produce a particular translation."""


class Translator(Protocol):
    """Anything that can render text from one language into another."""

    @property
    def name(self) -> str:
        """Short backend name for provenance, e.g. ``madlad400-3b-mt``."""
        ...

    def supports(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Whether this backend can translate ``source`` into ``target``."""
        ...

    def translate(self, text: str, source: LanguageCode, target: LanguageCode) -> str:
        """Translate ``text``. Only valid when :meth:`supports` is true."""
        ...


class NoTranslator:
    """The default backend: supports nothing, so absence is reported honestly."""

    name = "none"

    def supports(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Always ``False``."""
        return False

    def translate(self, text: str, source: LanguageCode, target: LanguageCode) -> str:
        """Never valid."""
        msg = "no machine translation backend is configured (set RLR_MT)"
        raise TranslationUnavailable(msg)


class MadladTranslator:
    """MADLAD-400 through ``transformers``. Loaded lazily on first use."""

    def __init__(
        self,
        model_id: str = "google/madlad400-3b-mt",
        max_new_tokens: int = 256,
        device: str | None = None,
    ) -> None:
        """Bind to a model id; nothing is downloaded until the first call.

        Args:
            model_id: Hugging Face model id.
            max_new_tokens: Generation cap per call.
            device: ``"cuda"``, ``"cpu"`` or ``None`` to pick CUDA when present.
        """
        self.model_id = model_id
        self.max_new_tokens = max_new_tokens
        self.device = device
        self._model: Any = None
        self._tokenizer: Any = None
        # One generation at a time. The demo server handles requests on a
        # thread pool, and a page reload (or Back) starts a new briefing while
        # the abandoned one is still generating; two threads driving the same
        # model concurrently crashes Metal on Apple silicon outright
        # ("A command encoder is already encoding to this command buffer")
        # and gains nothing elsewhere.
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        """The model id's final path component."""
        return self.model_id.rsplit("/", 1)[-1]

    def _load(self) -> tuple[Any, Any]:
        with self._lock:
            return self._load_locked()

    def _load_locked(self) -> tuple[Any, Any]:
        if self._model is None or self._tokenizer is None:
            try:
                import torch  # type: ignore[import-not-found,unused-ignore]  # noqa: PLC0415
                from transformers import (  # type: ignore[import-not-found,unused-ignore]  # noqa: PLC0415
                    AutoTokenizer,
                    T5ForConditionalGeneration,
                )
            except ImportError as exc:  # pragma: no cover - depends on extras
                msg = "MADLAD backend needs the 'mt' extra: uv sync --extra mt"
                raise RuntimeError(msg) from exc
            if self.device is None:
                self.device = pick_device(torch)
            # bfloat16 everywhere: half the memory of float32 (about 6 GB for
            # the 3B model), correct output on CUDA, Apple MPS and CPU, and
            # unlike float16 it does not overflow T5's activations.
            dtype = torch.bfloat16
            load_model: Any = T5ForConditionalGeneration.from_pretrained
            load_tokenizer: Any = AutoTokenizer.from_pretrained
            self._tokenizer = load_tokenizer(self.model_id)
            self._model = load_model(self.model_id, dtype=dtype).to(self.device).eval()
        return self._model, self._tokenizer

    def warm_up(self) -> None:
        """Download and load the model now rather than on the first request."""
        self._load()

    def supports(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Whether MADLAD was trained on both languages.

        The model detects the source language itself, but on a language it
        was never trained on it echoes or hallucinates rather than failing, so
        an unknown source is reported as unsupported.
        """
        _, tokenizer = self._load()
        vocab = tokenizer.get_vocab()
        return madlad_tag(source) in vocab and madlad_tag(target) in vocab

    def translate(self, text: str, source: LanguageCode, target: LanguageCode) -> str:
        """Run one generation with the ``<2xx>`` target prefix."""
        return self.translate_many([text], source, target)[0]

    def translate_many(
        self, texts: Sequence[str], source: LanguageCode, target: LanguageCode
    ) -> list[str]:
        """Translate a batch in one padded generation (much faster on a GPU)."""
        model, tokenizer = self._load()
        tag = madlad_tag(target)
        inputs = tokenizer([f"{tag} {t}" for t in texts], return_tensors="pt", padding=True).to(
            self.device
        )
        outputs = model.generate(**inputs, max_new_tokens=self.max_new_tokens)
        decoded: list[str] = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        return [d.strip() for d in decoded]


def pick_device(torch: Any) -> str:
    """CUDA, then Apple's MPS, then the CPU."""
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


class CachedTranslator:
    """Pre-rendered translations first, a live backend second.

    ``supports`` is true when either side can serve the pair; ``translate``
    raises :class:`TranslationUnavailable` for a text that is not pre-rendered
    when no live backend can produce it, which the pipeline reports as absence.
    """

    def __init__(self, inner: Translator, cache: RenderingCache) -> None:
        """Wrap ``inner`` with ``cache``."""
        self.inner = inner
        self.cache = cache

    @property
    def name(self) -> str:
        """The live backend's name, or the pre-rendering backends' with a marker."""
        if isinstance(self.inner, NoTranslator):
            backends = self.cache.backends()
            return f"{', '.join(sorted(backends))}, pre-rendered" if backends else "none"
        return self.inner.name

    def warm_up(self) -> None:
        """Load the live backend now, if it has anything to load."""
        warm = getattr(self.inner, "warm_up", None)
        if callable(warm):
            warm()

    def supports(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Whether renderings exist or the live backend can produce them."""
        return self.cache.has_language(source, target) or self.inner.supports(source, target)

    def translate(self, text: str, source: LanguageCode, target: LanguageCode) -> str:
        """Serve from the cache, else the live backend."""
        hit = self.cache.lookup(text, source, target)
        if hit is not None:
            return hit[0]
        if self.inner.supports(source, target):
            return self.inner.translate(text, source, target)
        backend = self.cache.backend_for(source, target) or "none"
        msg = (
            f"not pre-rendered into {target} "
            f"(renderings: {backend}; live backend: {self.inner.name})"
        )
        raise TranslationUnavailable(msg)

    def translate_many(
        self, texts: Sequence[str], source: LanguageCode, target: LanguageCode
    ) -> list[str]:
        """Batch form, cache hits served inline."""
        return [self.translate(t, source, target) for t in texts]


def load_translator(settings: Settings) -> Translator:
    """The live backend from ``settings``, behind the rendering cache."""
    from rlr.renderings import RenderingCache, bundled_dir  # noqa: PLC0415

    dirs: list[Any] = []
    if settings.renderings_dir is not None:
        dirs.append(settings.renderings_dir)
    dirs.append(settings.cache_dir / "renderings")
    dirs.append(bundled_dir())
    return CachedTranslator(load_backend(settings), RenderingCache(dirs))


def load_backend(settings: Settings) -> Translator:
    """Build the live backend named by ``settings.mt_backend``.

    ``none`` (default) gives :class:`NoTranslator`; ``madlad`` or
    ``madlad:<model-id>`` gives :class:`MadladTranslator`.
    """
    backend = settings.mt_backend.strip()
    if backend in ("", "none"):
        return NoTranslator()
    kind, _, model_id = backend.partition(":")
    if kind == "madlad":
        device = os.environ.get("RLR_MT_DEVICE") or None
        return MadladTranslator(model_id or "google/madlad400-3b-mt", device=device)
    msg = f"unknown RLR_MT backend {backend!r} (expected 'none' or 'madlad[:model-id]')"
    raise ValueError(msg)
