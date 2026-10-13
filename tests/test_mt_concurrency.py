"""Generation is serialized: concurrent requests must never drive the model at once."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from rlr.mt import MadladTranslator


class _Inputs(dict):
    def to(self, device: str) -> _Inputs:
        return self


class _Tokenizer:
    def __call__(self, texts: list[str], **_: object) -> _Inputs:
        return _Inputs(texts=texts)

    def batch_decode(self, outputs: list[str], **_: object) -> list[str]:
        return outputs

    def get_vocab(self) -> dict[str, int]:
        return {"<2sw>": 1, "<2en>": 2}


class _Model:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self._guard = threading.Lock()

    def generate(self, texts: list[str], max_new_tokens: int) -> list[str]:
        with self._guard:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.05)
        with self._guard:
            self.active -= 1
        return [f"out:{t}" for t in texts]


def test_concurrent_translations_are_serialized(monkeypatch):
    t = MadladTranslator(device="cpu")
    model, tok = _Model(), _Tokenizer()
    monkeypatch.setattr(t, "_load_locked", lambda: (model, tok))
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(lambda i: t.translate(f"text {i}", "eng", "swh"), range(16)))
    assert results == [f"out:<2sw> text {i}" for i in range(16)]
    assert model.peak == 1
    assert t.supports("eng", "swh")
