"""Translator backends: the null default, tags, and backend selection."""

from __future__ import annotations

import pytest

from rlr.back_translation import back_translate, supports
from rlr.config import Settings
from rlr.mt import (
    CachedTranslator,
    MadladTranslator,
    NoTranslator,
    load_backend,
    load_translator,
    madlad_tag,
)
from rlr.renderings import RenderingCache
from rlr.types import LicenseClass, PassageRef, PassageText, Provenance, Unavailable


def test_madlad_tags():
    assert madlad_tag("swh") == "<2sw>"
    assert madlad_tag("por") == "<2pt>"
    assert madlad_tag("ffm_Latn") == "<2ffm>"


def test_load_backend_selects_backend():
    assert isinstance(load_backend(Settings(mt_backend="none")), NoTranslator)
    madlad = load_backend(Settings(mt_backend="madlad:org/model"))
    assert isinstance(madlad, MadladTranslator)
    assert madlad.name == "model"
    default = load_backend(Settings(mt_backend="madlad"))
    assert isinstance(default, MadladTranslator)
    assert default.model_id == "google/madlad400-3b-mt"
    with pytest.raises(ValueError, match="unknown RLR_MT backend"):
        load_backend(Settings(mt_backend="babelfish"))


def test_backend_device_override(monkeypatch):
    monkeypatch.setenv("RLR_MT_DEVICE", "cpu")
    forced = load_backend(Settings(mt_backend="madlad"))
    assert isinstance(forced, MadladTranslator)
    assert forced.device == "cpu"
    monkeypatch.delenv("RLR_MT_DEVICE")
    auto = load_backend(Settings(mt_backend="madlad"))
    assert isinstance(auto, MadladTranslator)
    assert auto.device is None


def test_load_translator_wraps_backend_in_the_rendering_cache(tmp_path):
    t = load_translator(
        Settings(mt_backend="none", cache_dir=tmp_path, renderings_dir=tmp_path / "x")
    )
    assert isinstance(t, CachedTranslator)
    assert isinstance(t.inner, NoTranslator)
    # Directories are searched in order: RLR_RENDERINGS_DIR, the cache, the bundled copies.
    dirs = [str(d) for d in t.cache.dirs]
    assert dirs[:2] == [str(tmp_path / "x"), str(tmp_path / "renderings")]
    assert dirs[2].endswith("renderings")
    empty = CachedTranslator(NoTranslator(), RenderingCache([tmp_path / "nothing"]))
    assert empty.name == "none"


def test_no_translator_refuses_loudly():
    with pytest.raises(RuntimeError, match="RLR_MT"):
        NoTranslator().translate("x", "eng", "swh")


def _text(license_class: LicenseClass) -> PassageText:
    return PassageText(
        passage=PassageRef.parse("MRK 1:6"),
        language="reg",
        text="Yohana",
        provenance=Provenance(
            source="t", title="Kara", license_name="L", license_class=license_class
        ),
    )


def test_back_translate_reports_each_gate():
    none = NoTranslator()
    assert not supports("reg", "swh", none)
    blocked = back_translate(_text(LicenseClass.DERIVATIVES_FORBIDDEN), "swh", none)
    assert isinstance(blocked, Unavailable)
    assert "derivative" in blocked.reason
    missing = back_translate(_text(LicenseClass.OPEN), "swh", none)
    assert isinstance(missing, Unavailable)
    assert "backend: none" in missing.reason
    same = back_translate(_text(LicenseClass.OPEN), "reg_Latn", none)
    assert isinstance(same, Unavailable)
    assert "already is the LWC" in same.reason
