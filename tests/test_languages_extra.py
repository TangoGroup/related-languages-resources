"""LWC suggestions from an lwc.csv, and settings from the environment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rlr.config import Settings
from rlr.languages import suggest_lwcs

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

LWC_CSV = """glottocode,iso639_3,name,lwc_glottocode,lwc_iso639_3,lwc_name,probability,country,basis,distance_km
isan1240,isn,Isanzu,swah1253,swh,Swahili,0.9,TZ,national,
isan1240,isn,Isanzu,stan1293,eng,English,0.69,TZ,national,
isan1240,isn,Isanzu,gand1255,lug,Ganda,0.05,TZ,regional,300
"""


def test_suggest_lwcs_ranks_by_probability(tmp_path: Path) -> None:
    csv_path = tmp_path / "lwc.csv"
    csv_path.write_text(LWC_CSV, encoding="utf-8")
    top = suggest_lwcs("isn", csv_path)
    assert [(s.code, s.probability) for s in top] == [("swh", 0.9), ("eng", 0.69)]
    assert top[0].name == "Swahili"
    assert suggest_lwcs("isan1240", csv_path, limit=1)[0].code == "swh"
    assert suggest_lwcs("zzz", csv_path) == []


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RLR_CACHE_DIR", str(tmp_path / "c"))
    monkeypatch.setenv("RLR_FIGURES_DIR", str(tmp_path / "figs"))
    monkeypatch.setenv("RLR_LWC_CSV", str(tmp_path / "lwc.csv"))
    monkeypatch.setenv("RLR_MT", "madlad")
    monkeypatch.setenv("RLR_OFFLINE", "1")
    s = Settings.from_env()
    assert s.cache_dir == tmp_path / "c"
    assert s.figures_dir == tmp_path / "figs"
    assert s.lwc_csv == tmp_path / "lwc.csv"
    assert s.mt_backend == "madlad"
    assert s.offline


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("RLR_CACHE_DIR", "RLR_FIGURES_DIR", "RLR_LWC_CSV", "RLR_MT", "RLR_OFFLINE"):
        monkeypatch.delenv(var, raising=False)
    s = Settings.from_env()
    assert s.cache_dir.name == "rlr"
    assert s.figures_dir is None
    assert s.mt_backend == "none"
    assert not s.offline
