"""CLI surface: argument parsing and rendering against the offline pipeline."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from rlr import cli
from rlr.cli import app
from rlr.config import Settings

runner = CliRunner()


@pytest.fixture
def offline_cli(monkeypatch, pipeline):
    monkeypatch.setattr(cli, "build_pipeline", lambda settings: pipeline)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: pipeline.settings))
    return pipeline


def test_languages_lists_scores_and_licenses(offline_cli):
    result = runner.invoke(app, ["languages", "--target", "ngq"])
    assert result.exit_code == 0, result.output
    assert "0.75  reg   Kara (Tanzania) (shared country)" in result.output
    assert "CC BY-NC-ND 4.0" in result.output


def test_languages_json(offline_cli):
    result = runner.invoke(app, ["languages", "--target", "ngq", "--json", "--limit", "2"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [d["code"] for d in data] == ["reg", "swh"]


def test_languages_unknown_target_exits_nonzero(offline_cli):
    result = runner.invoke(app, ["languages", "--target", "zzz"])
    assert result.exit_code == 1
    assert "Nothing:" in result.output


def test_brief_renders_readings_and_absence(offline_cli):
    result = runner.invoke(
        app, ["brief", "--target", "ngq", "--lwc", "swh", "--passage", "MRK 1:6"]
    )
    assert result.exit_code == 0, result.output
    assert result.output.index("== In swh") < result.output.index("== Kara")
    assert "== Kara (Tanzania) (reg, similarity 0.75)" in result.output
    assert "reg 1:6 camel hair" in result.output
    assert (
        "Kara New Testament · Example Publishers · copyright © 2020 · CC BY-SA 4.0" in result.output
    )
    assert "no back-translation capability" not in result.output  # Swahili has an open Bible
    assert "Not shown: zgam has no text for MRK 1:6" in result.output
    assert "-- Metaphor (figures of speech (unfoldingWord))" in result.output
    assert "in swh: not available. no machine translation from eng into swh" in result.output


def test_brief_reports_absent_notes(offline_cli):
    result = runner.invoke(
        app, ["brief", "--target", "ngq", "--lwc", "swh", "--passage", "MRK 1:1"]
    )
    assert result.exit_code == 0, result.output
    assert "== Notes\nNone. no notes for MRK 1:1" in result.output


def test_brief_json_is_serialisable(offline_cli):
    result = runner.invoke(
        app, ["brief", "--target", "ngq", "--lwc", "swh", "--passage", "MRK 1:2", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["passage"]["start"]["book"] == "MRK"
    assert data["readings"][0]["original"]["provenance"]["license_class"] == "open"
    assert data["notes"][0]["note"]["figure"]["id"] == "figs-idiom"


def test_brief_rejects_bad_reference(offline_cli):
    result = runner.invoke(app, ["brief", "--target", "ngq", "--lwc", "swh", "--passage", "Mark 1"])
    assert result.exit_code == 2
