"""Stage 2: eBible metadata, license classes and provenance."""

from __future__ import annotations

import pytest

from rlr.catalog import available_bibles, explain_absence
from rlr.ebible import license_class, license_name
from rlr.types import DERIVABLE, LicenseClass, RelatedLanguage


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("Public Domain", LicenseClass.OPEN),
        ("by", LicenseClass.OPEN),
        ("by-sa", LicenseClass.OPEN),
        ("by-nc", LicenseClass.NONCOMMERCIAL),
        ("by-nd", LicenseClass.DERIVATIVES_FORBIDDEN),
        ("by-nc-nd", LicenseClass.DERIVATIVES_FORBIDDEN),
        ("Unknown", LicenseClass.UNKNOWN),
        ("", LicenseClass.UNKNOWN),
    ],
)
def test_license_type_mapping(kind, expected):
    assert license_class(kind) is expected


def test_license_names():
    assert license_name("by-nc-nd", "4.0") == "CC BY-NC-ND 4.0"
    assert license_name("Public Domain", "") == "Public Domain"
    assert license_name("Unknown", "") is None


def test_corpus_manifest_and_provenance(corpus):
    assert corpus.languages == {"reg", "zga", "wbi", "swh"}
    (kinga,) = corpus.editions_for("zga")
    assert kinga.edition_id == "zgam"
    assert kinga.language_name == "Kinga"
    p = kinga.provenance
    assert p.title == "Kinga New Testament"
    assert p.publisher == "Example Publishers"
    assert p.published == "copyright © 2019"
    assert p.license_name == "CC BY 4.0"
    assert p.license_class is LicenseClass.OPEN
    assert p.url == "http://example.org/zga/"
    assert corpus.corpus_file(kinga).url.endswith("/corpus/zga-zgam.txt")


def _lang(code: str, name: str) -> RelatedLanguage:
    return RelatedLanguage(code=code, name=name, similarity=0.8)


def test_available_bibles_filters_by_license(corpus):
    langs = [_lang("reg", "Kara"), _lang("wbi", "Vwanji"), _lang("xxx", "Nowhere")]
    shown = available_bibles(langs, corpus)
    assert [e.language for e in shown] == ["reg", "wbi"]
    derivable = available_bibles(langs, corpus, DERIVABLE)
    assert [e.language for e in derivable] == ["reg"]


def test_explain_absence_gives_reasons(corpus):
    assert explain_absence(_lang("reg", "Kara"), corpus) is None
    missing = explain_absence(_lang("xxx", "Nowhere"), corpus)
    assert missing is not None
    assert "no Bible text for Nowhere" in missing.reason
    licensed = explain_absence(_lang("wbi", "Vwanji"), corpus, DERIVABLE)
    assert licensed is not None
    assert "derivatives_forbidden" in licensed.reason
    assert licensed.language == "wbi"
