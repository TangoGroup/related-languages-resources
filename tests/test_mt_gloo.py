"""Gloo AI Studio backend: request shape, auth modes, live-first cache fallback."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from rlr.back_translation import back_translate
from rlr.config import Settings, load_dotenv
from rlr.mt import (
    GLOO_RESPONSES_URL,
    GLOO_TOKEN_URL,
    CachedTranslator,
    GlooTranslator,
    TranslationUnavailable,
    gloo_auth_mode,
    load_backend,
    load_translator,
)
from rlr.renderings import RenderingCache, RenderingFile, file_name, rendering_key, write_file
from rlr.types import LicenseClass, PassageRef, PassageText, Provenance

if TYPE_CHECKING:
    from pathlib import Path

GLOO_VARS = ("GLOO_API_KEY", "GLOO_CLIENT_ID", "GLOO_CLIENT_SECRET", "GLOO_MODEL")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in GLOO_VARS:
        monkeypatch.delenv(name, raising=False)


def _reply(text: str) -> dict[str, object]:
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


def _translator(handler: httpx.MockTransport) -> GlooTranslator:
    return GlooTranslator(client=httpx.Client(transport=handler))


def test_api_key_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOO_API_KEY", "sk-test-123")
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_reply("Yohana alivaa nguo za manyoya ya ngamia."))

    t = _translator(httpx.MockTransport(handle))
    assert t.supports("eng", "swh")
    out = t.translate("John wore clothing made of camel's hair.", "eng", "swh")
    assert out == "Yohana alivaa nguo za manyoya ya ngamia."
    (req,) = seen
    assert str(req.url) == GLOO_RESPONSES_URL
    assert req.headers["Authorization"] == "Bearer sk-test-123"
    body = json.loads(req.content)
    assert body["model"] == "gloo-anthropic-claude-sonnet-4.6"
    assert "Swahili" in body["instructions"]
    assert body["input"] == [
        {"role": "user", "content": "John wore clothing made of camel's hair."}
    ]


def test_auth_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert gloo_auth_mode() is None
    assert not GlooTranslator().supports("eng", "swh")
    monkeypatch.setenv("GLOO_CLIENT_SECRET", "key-in-secret")
    assert gloo_auth_mode() == "api key (GLOO_CLIENT_SECRET)"
    monkeypatch.setenv("GLOO_CLIENT_ID", "apikey")
    assert gloo_auth_mode() == "api key (GLOO_CLIENT_SECRET)"
    monkeypatch.setenv("GLOO_CLIENT_ID", "real-client")
    assert gloo_auth_mode() == "client credentials (GLOO_CLIENT_ID + GLOO_CLIENT_SECRET)"
    monkeypatch.setenv("GLOO_API_KEY", "k")
    assert gloo_auth_mode() == "api key (GLOO_API_KEY)"


def test_client_credentials_exchange_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOO_CLIENT_ID", "cid")
    monkeypatch.setenv("GLOO_CLIENT_SECRET", "csecret")
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if str(request.url) == GLOO_TOKEN_URL:
            assert request.headers["Authorization"].startswith("Basic ")
            assert b"grant_type=client_credentials" in request.content
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json=_reply("ok"))

    t = _translator(httpx.MockTransport(handle))
    assert t.translate("a", "eng", "swh") == "ok"
    assert t.translate("b", "eng", "swh") == "ok"
    assert calls.count(GLOO_TOKEN_URL) == 1  # token reused


def test_http_failure_is_unavailable_without_leaking_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOO_API_KEY", "sk-secret-value")
    t = _translator(httpx.MockTransport(lambda r: httpx.Response(429, json={"error": "slow"})))
    with pytest.raises(TranslationUnavailable, match="HTTP 429") as info:
        t.translate("x", "eng", "swh")
    assert "sk-secret-value" not in str(info.value)

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(TranslationUnavailable, match="ConnectError"):
        _translator(httpx.MockTransport(boom)).translate("x", "eng", "swh")


def _cache(tmp_path: Path, text: str, rendering: str) -> RenderingCache:
    f = RenderingFile(
        backend="madlad400-3b-mt", source="eng", target="swh", derived_from="test", license="MIT"
    )
    f.entries[rendering_key(text, "eng")] = rendering
    write_file(tmp_path / file_name("swh"), f)
    return RenderingCache([tmp_path])


def test_live_first_then_cache_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOO_API_KEY", "k")
    cache = _cache(tmp_path, "Hello", "Habari (cached)")
    up = CachedTranslator(
        _translator(httpx.MockTransport(lambda r: httpx.Response(200, json=_reply("Habari")))),
        cache,
        prefer_live=True,
    )
    up.begin()
    assert up.translate("Hello", "eng", "swh") == "Habari"
    assert up.used() == ["gloo-anthropic-claude-sonnet-4.6 via Gloo AI Studio, live"]

    down = CachedTranslator(
        _translator(httpx.MockTransport(lambda r: httpx.Response(401))), cache, prefer_live=True
    )
    down.begin()
    assert down.translate("Hello", "eng", "swh") == "Habari (cached)"
    (label,) = down.used()
    assert "live MT unavailable (Gloo AI Studio returned HTTP 401), showing cached" in label
    with pytest.raises(TranslationUnavailable, match="live MT unavailable"):
        down.translate("Not cached", "eng", "swh")


def test_back_translation_provenance_names_live_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GLOO_API_KEY", "k")
    t = CachedTranslator(
        _translator(httpx.MockTransport(lambda r: httpx.Response(200, json=_reply("Habari")))),
        RenderingCache([tmp_path]),
        prefer_live=True,
    )
    source = PassageText(
        passage=PassageRef.parse("MRK 1:6"),
        language="eng",
        text="Hello",
        provenance=Provenance(
            source="test", title="T", license_name="CC BY 4.0", license_class=LicenseClass.OPEN
        ),
    )
    out = back_translate(source, "swh", t)
    assert isinstance(out, PassageText)
    assert out.provenance.source.endswith("via Gloo AI Studio, live)")


def test_load_backend_gloo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert isinstance(load_backend(Settings(mt_backend="gloo")), GlooTranslator)
    assert load_backend(Settings(mt_backend="gloo:other-model")).name.startswith("other-model")
    wrapped = load_translator(Settings(mt_backend="gloo", cache_dir=tmp_path))
    assert isinstance(wrapped, CachedTranslator)
    assert wrapped.prefer_live
    assert not load_translator(Settings(mt_backend="none", cache_dir=tmp_path)).prefer_live  # type: ignore[attr-defined]


def test_load_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text('# c\nGLOO_API_KEY="abc"\nexport GLOO_MODEL=m # note\nRLR_MT=already\n')
    monkeypatch.setenv("RLR_MT", "kept")
    assert sorted(load_dotenv(env)) == ["GLOO_API_KEY", "GLOO_MODEL"]
    import os

    assert os.environ["GLOO_API_KEY"] == "abc"
    assert os.environ["GLOO_MODEL"] == "m"
    assert os.environ["RLR_MT"] == "kept"
    monkeypatch.delenv("RLR_MT")
