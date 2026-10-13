"""Device selection and warm-up for the live backend."""

from __future__ import annotations

from types import SimpleNamespace

from rlr.mt import CachedTranslator, NoTranslator, pick_device
from rlr.renderings import RenderingCache


def _torch(cuda: bool, mps: bool | None) -> SimpleNamespace:
    backends = SimpleNamespace()
    if mps is not None:
        backends.mps = SimpleNamespace(is_available=lambda: mps)
    return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: cuda), backends=backends)


def test_pick_device_prefers_cuda_then_mps_then_cpu():
    assert pick_device(_torch(cuda=True, mps=True)) == "cuda"
    assert pick_device(_torch(cuda=False, mps=True)) == "mps"
    assert pick_device(_torch(cuda=False, mps=False)) == "cpu"
    assert pick_device(_torch(cuda=False, mps=None)) == "cpu"


def test_warm_up_is_a_no_op_without_a_live_backend(tmp_path):
    CachedTranslator(NoTranslator(), RenderingCache([tmp_path])).warm_up()
