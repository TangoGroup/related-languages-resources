"""Translator backends: the null default, tags, and backend selection."""

from __future__ import annotations

import pytest

from rlr.back_translation import back_translate, supports
from rlr.config import Settings
from rlr.mt import MadladTranslator, NoTranslator, load_translator, madlad_tag
from rlr.types import LicenseClass, PassageRef, PassageText, Provenance, Unavailable


def test_madlad_tags():
    assert madlad_tag("swh") == "<2sw>"
    assert madlad_tag("por") == "<2pt>"
    assert madlad_tag("ffm_Latn") == "<2ffm>"


def test_load_translator_selects_backend():
    assert isinstance(load_translator(Settings(mt_backend="none")), NoTranslator)
    madlad = load_translator(Settings(mt_backend="madlad:org/model"))
    assert isinstance(madlad, MadladTranslator)
    assert madlad.name == "model"
    default = load_translator(Settings(mt_backend="madlad"))
    assert isinstance(default, MadladTranslator)
    assert default.model_id == "google/madlad400-3b-mt"
    with pytest.raises(ValueError, match="unknown RLR_MT backend"):
        load_translator(Settings(mt_backend="babelfish"))


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
