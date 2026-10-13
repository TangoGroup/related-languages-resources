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

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from rlr.config import Settings
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
        raise RuntimeError(msg)


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

    @property
    def name(self) -> str:
        """The model id's final path component."""
        return self.model_id.rsplit("/", 1)[-1]

    def _load(self) -> tuple[Any, Any]:
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
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
            load_model: Any = T5ForConditionalGeneration.from_pretrained
            load_tokenizer: Any = AutoTokenizer.from_pretrained
            self._tokenizer = load_tokenizer(self.model_id)
            self._model = load_model(self.model_id, torch_dtype=dtype).to(self.device).eval()
        return self._model, self._tokenizer

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
        model, tokenizer = self._load()
        inputs = tokenizer(f"{madlad_tag(target)} {text}", return_tensors="pt").to(self.device)
        outputs = model.generate(**inputs, max_new_tokens=self.max_new_tokens)
        decoded: str = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        return decoded.strip()


def load_translator(settings: Settings) -> Translator:
    """Build the backend named by ``settings.mt_backend``.

    ``none`` (default) gives :class:`NoTranslator`; ``madlad`` or
    ``madlad:<model-id>`` gives :class:`MadladTranslator`.
    """
    backend = settings.mt_backend.strip()
    if backend in ("", "none"):
        return NoTranslator()
    kind, _, model_id = backend.partition(":")
    if kind == "madlad":
        return MadladTranslator(model_id) if model_id else MadladTranslator()
    msg = f"unknown RLR_MT backend {backend!r} (expected 'none' or 'madlad[:model-id]')"
    raise ValueError(msg)
