"""Machine translation backends, shared by stages 4 and 5.

The pipeline reaches machine translation through a small :class:`Translator`
protocol, so it can ask two questions, "can you render into this language?"
and "then do so", without knowing what sits behind them. Absence is a
first-class answer: the default backend supports nothing, so every LWC
rendering comes back as
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
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Protocol

import httpx

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
        with self._lock:
            model, tokenizer = self._load_locked()
            tag = madlad_tag(target)
            inputs = tokenizer([f"{tag} {t}" for t in texts], return_tensors="pt", padding=True).to(
                self.device
            )
            outputs = model.generate(**inputs, max_new_tokens=self.max_new_tokens)
            decoded: list[str] = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        return [d.strip() for d in decoded]


GLOO_TOKEN_URL = "https://platform.ai.gloo.com/oauth2/token"
GLOO_RESPONSES_URL = "https://platform.ai.gloo.com/ai/v1/responses"
GLOO_DEFAULT_MODEL = "gloo-anthropic-claude-sonnet-4.6"
#: ``GLOO_CLIENT_ID`` value meaning "``GLOO_CLIENT_SECRET`` holds an API key".
_GLOO_API_KEY_SENTINEL = "apikey"

#: Names for the prompt; any other code is passed as the bare ISO 639-3 code.
_LANGUAGE_NAMES: dict[str, str] = {
    "eng": "English",
    "fra": "French",
    "spa": "Spanish",
    "por": "Portuguese",
    "swh": "Swahili",
    "swa": "Swahili",
    "ind": "Indonesian",
    "hin": "Hindi",
    "rus": "Russian",
    "arb": "Arabic",
    "hau": "Hausa",
    "amh": "Amharic",
    "tpi": "Tok Pisin",
    "tgl": "Tagalog",
    "vie": "Vietnamese",
}


def _env(name: str) -> str | None:
    """An environment value, with empty and ``unset`` treated as absent."""
    value = os.environ.get(name, "").strip()
    return None if value.lower() in ("", "unset") else value


def _language(code: LanguageCode) -> str:
    bare = code.split("_")[0].lower()
    name = _LANGUAGE_NAMES.get(bare)
    return f"{name} (ISO 639-3 {bare})" if name else f"the language with ISO 639-3 code {bare}"


def gloo_auth_mode() -> str | None:
    """Which Gloo credentials the environment holds, never their values.

    Same order as Relay: ``GLOO_API_KEY``; else ``GLOO_CLIENT_SECRET`` holding
    an API key (``GLOO_CLIENT_ID`` unset or ``apikey``); else
    ``GLOO_CLIENT_ID`` + ``GLOO_CLIENT_SECRET`` as OAuth2 client credentials.
    """
    if _env("GLOO_API_KEY"):
        return "api key (GLOO_API_KEY)"
    client_id, secret = _env("GLOO_CLIENT_ID"), _env("GLOO_CLIENT_SECRET")
    if secret and (client_id is None or client_id.lower() == _GLOO_API_KEY_SENTINEL):
        return "api key (GLOO_CLIENT_SECRET)"
    if secret and client_id:
        return "client credentials (GLOO_CLIENT_ID + GLOO_CLIENT_SECRET)"
    return None


class GlooTranslator:
    """Live machine translation through the Gloo AI Studio model router.

    One Responses API call per text. Auth is read from the environment on
    each call (see :func:`gloo_auth_mode`); key values are never logged or put
    in error messages. Every failure (no key, HTTP error, timeout, a reply
    with no text) is raised as :class:`TranslationUnavailable`.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 45.0,
        client: httpx.Client | None = None,
    ) -> None:
        """Bind to a router model; ``GLOO_MODEL`` overrides the default."""
        self.model = model or _env("GLOO_MODEL") or GLOO_DEFAULT_MODEL
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._token: tuple[str, float] | None = None
        self._token_lock = threading.Lock()

    @property
    def name(self) -> str:
        """The router model, marked as Gloo AI Studio."""
        return f"{self.model} via Gloo AI Studio"

    def supports(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Any pair, once credentials are configured (an LLM has no fixed list)."""
        return gloo_auth_mode() is not None

    def _bearer(self) -> str:
        api_key = _env("GLOO_API_KEY")
        if api_key:
            return api_key
        client_id, secret = _env("GLOO_CLIENT_ID"), _env("GLOO_CLIENT_SECRET")
        if secret and (client_id is None or client_id.lower() == _GLOO_API_KEY_SENTINEL):
            return secret
        if not (secret and client_id):
            msg = "Gloo AI Studio is not configured: set GLOO_API_KEY in .env"
            raise TranslationUnavailable(msg)
        with self._token_lock:
            if self._token is not None and self._token[1] > time.monotonic():
                return self._token[0]
            try:
                response = self._client.post(
                    GLOO_TOKEN_URL,
                    auth=(client_id, secret),
                    data={"grant_type": "client_credentials", "scope": "api/access"},
                )
            except httpx.HTTPError as exc:
                msg = f"Gloo token request failed: {type(exc).__name__}"
                raise TranslationUnavailable(msg) from None
            if response.status_code != httpx.codes.OK:
                msg = f"Gloo token endpoint returned HTTP {response.status_code}"
                raise TranslationUnavailable(msg)
            body: Any = response.json()
            token = body.get("access_token") if isinstance(body, dict) else None
            if not isinstance(token, str):
                msg = "Gloo token response had no access_token"
                raise TranslationUnavailable(msg)
            lifetime = float(body.get("expires_in", 3600))
            self._token = (token, time.monotonic() + max(lifetime - 120.0, 60.0))
            return token

    def translate(self, text: str, source: LanguageCode, target: LanguageCode) -> str:
        """One Responses API call; the reply text is the translation."""
        instructions = (
            "You are a machine-translation engine used by Bible translators for quality "
            f"assurance. Translate the user's text from {_language(source)} into "
            f"{_language(target)}. Translate faithfully and completely, keeping the meaning "
            "and structure; keep verse numbers, names and quoted words as they are. Reply "
            "with the translation only: no preamble, notes, explanations or quotation marks."
        )
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": [{"role": "user", "content": text}],
        }
        try:
            response = self._client.post(
                GLOO_RESPONSES_URL,
                headers={"Authorization": f"Bearer {self._bearer()}"},
                json=payload,
            )
        except httpx.HTTPError as exc:
            msg = f"Gloo AI Studio request failed: {type(exc).__name__}"
            raise TranslationUnavailable(msg) from None
        if response.status_code != httpx.codes.OK:
            if response.status_code == httpx.codes.UNAUTHORIZED:
                self._token = None
            msg = f"Gloo AI Studio returned HTTP {response.status_code}"
            raise TranslationUnavailable(msg)
        try:
            body: Any = response.json()
        except ValueError:
            msg = "Gloo AI Studio reply was not JSON"
            raise TranslationUnavailable(msg) from None
        out = _response_text(body)
        if not out:
            msg = "Gloo AI Studio reply had no output text"
            raise TranslationUnavailable(msg)
        return out

    def translate_many(
        self, texts: Sequence[str], source: LanguageCode, target: LanguageCode
    ) -> list[str]:
        """Concurrent calls, results in order."""
        with ThreadPoolExecutor(max_workers=8) as pool:
            return list(pool.map(lambda t: self.translate(t, source, target), texts))


def _response_text(body: Any) -> str:
    """The text of a Responses API reply, joined across output blocks."""
    if not isinstance(body, dict):
        return ""
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts: list[str] = []
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "".join(parts).strip()


def pick_device(torch: Any) -> str:
    """CUDA, then Apple's MPS, then the CPU."""
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


class CachedTranslator:
    """Pre-rendered translations and a live backend.

    By default the cache answers first and the live backend fills gaps. With
    ``prefer_live`` (the Gloo backend) the live backend answers first and the
    cache is the fallback: when a live call fails for any reason, the cached
    rendering is served and its provenance says so ("live MT unavailable,
    showing cached"); a live failure never propagates as anything but
    :class:`TranslationUnavailable`.

    Which backend produced each text is recorded per calling thread; read it
    with :func:`begin_provenance` / :func:`provenance_label`.
    """

    def __init__(
        self, inner: Translator, cache: RenderingCache, *, prefer_live: bool = False
    ) -> None:
        """Wrap ``inner`` with ``cache``."""
        self.inner = inner
        self.cache = cache
        self.prefer_live = prefer_live
        self._local = threading.local()

    @property
    def name(self) -> str:
        """The live backend's name, or the pre-rendering backends' with a marker."""
        if isinstance(self.inner, NoTranslator):
            backends = self.cache.backends()
            return f"{', '.join(sorted(backends))}, pre-rendered" if backends else "none"
        if self.prefer_live:
            return f"{self.inner.name}, live (pre-rendered fallback)"
        return self.inner.name

    def warm_up(self) -> None:
        """Load the live backend now, if it has anything to load."""
        warm = getattr(self.inner, "warm_up", None)
        if callable(warm):
            warm()

    def supports(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Whether renderings exist or the live backend can produce them."""
        return self.cache.has_language(source, target) or self.inner.supports(source, target)

    def begin(self) -> None:
        """Start recording which backends serve this thread's next calls."""
        self._local.used = []

    def used(self) -> list[str]:
        """Backends recorded since :meth:`begin`, in order, deduplicated."""
        return list(dict.fromkeys(getattr(self._local, "used", [])))

    def _record(self, label: str) -> None:
        used = getattr(self._local, "used", None)
        if used is None:
            self._local.used = used = []
        used.append(label)

    def _translate(self, text: str, source: LanguageCode, target: LanguageCode) -> tuple[str, str]:
        """``(rendering, provenance label)``; raises :class:`TranslationUnavailable`."""
        if self.prefer_live and self.inner.supports(source, target):
            try:
                return self.inner.translate(text, source, target), f"{self.inner.name}, live"
            except Exception as exc:
                reason = str(exc) if isinstance(exc, TranslationUnavailable) else type(exc).__name__
                hit = self.cache.lookup(text, source, target)
                if hit is not None:
                    return hit[0], (
                        f"{hit[1]}, pre-rendered; live MT unavailable ({reason}), showing cached"
                    )
                msg = f"live MT unavailable ({reason}) and not pre-rendered into {target}"
                raise TranslationUnavailable(msg) from None
        hit = self.cache.lookup(text, source, target)
        if hit is not None:
            return hit[0], f"{hit[1]}, pre-rendered"
        if self.inner.supports(source, target):
            return self.inner.translate(text, source, target), self.inner.name
        backend = self.cache.backend_for(source, target) or "none"
        msg = (
            f"not pre-rendered into {target} "
            f"(renderings: {backend}; live backend: {self.inner.name})"
        )
        raise TranslationUnavailable(msg)

    def translate(self, text: str, source: LanguageCode, target: LanguageCode) -> str:
        """Serve one text, recording which backend produced it."""
        out, label = self._translate(text, source, target)
        self._record(label)
        return out

    def translate_many(
        self, texts: Sequence[str], source: LanguageCode, target: LanguageCode
    ) -> list[str]:
        """Batch form; live-first calls run concurrently."""
        if self.prefer_live and len(texts) > 1:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda t: self._translate(t, source, target), texts))
        else:
            results = [self._translate(t, source, target) for t in texts]
        for _, label in results:
            self._record(label)
        return [out for out, _ in results]


def begin_provenance(translator: Translator) -> None:
    """Start recording which backends ``translator`` uses on this thread."""
    begin = getattr(translator, "begin", None)
    if callable(begin):
        begin()


def provenance_label(translator: Translator) -> str:
    """The backends used since :func:`begin_provenance`, else the backend name."""
    used = getattr(translator, "used", None)
    labels: list[str] = used() if callable(used) else []
    return "; ".join(labels) if labels else translator.name


def load_translator(settings: Settings) -> Translator:
    """The live backend from ``settings``, behind the rendering cache."""
    from rlr.renderings import RenderingCache, bundled_dir  # noqa: PLC0415

    dirs: list[Any] = []
    if settings.renderings_dir is not None:
        dirs.append(settings.renderings_dir)
    dirs.append(settings.cache_dir / "renderings")
    dirs.append(bundled_dir())
    backend = load_backend(settings)
    return CachedTranslator(
        backend, RenderingCache(dirs), prefer_live=isinstance(backend, GlooTranslator)
    )


def load_backend(settings: Settings) -> Translator:
    """Build the live backend named by ``settings.mt_backend``.

    ``none`` (default) gives :class:`NoTranslator`; ``madlad`` or
    ``madlad:<model-id>`` gives :class:`MadladTranslator`; ``gloo`` or
    ``gloo:<router-model>`` gives :class:`GlooTranslator` (live, cache fallback).
    """
    backend = settings.mt_backend.strip()
    if backend in ("", "none"):
        return NoTranslator()
    kind, _, model_id = backend.partition(":")
    if kind == "madlad":
        device = os.environ.get("RLR_MT_DEVICE") or None
        return MadladTranslator(model_id or "google/madlad400-3b-mt", device=device)
    if kind == "gloo":
        return GlooTranslator(model_id or None)
    msg = (
        f"unknown RLR_MT backend {backend!r} "
        "(expected 'none', 'madlad[:model-id]' or 'gloo[:model]')"
    )
    raise ValueError(msg)
