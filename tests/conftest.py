"""Shared fixtures: an offline pipeline built from tiny data files."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rlr.config import Settings

if TYPE_CHECKING:
    from rlr.agent import Pipeline
    from rlr.ebible import EBibleCorpus
    from rlr.glottolog import Glottolog
    from rlr.resources.figures_of_speech import FiguresOfSpeech
    from rlr.verses import VerseIndex

# Stage modules are imported inside the fixtures so this file loads even when
# only some stages exist, which keeps per-stage commits self-contained.

FIXTURES = Path(__file__).parent / "fixtures"


class FakeTranslator:
    """Supports English and Swahili targets; wraps text so tests can see it ran."""

    name = "fake"

    def supports(self, source: str, target: str) -> bool:
        return target in {"swh", "eng"}

    def translate(self, text: str, source: str, target: str) -> str:
        return f"[{source}->{target}] {text}"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Offline settings whose cache is pre-seeded with the fixture corpus files."""
    cache = tmp_path / "cache"
    shutil.copytree(FIXTURES / "ebible" / "corpus", cache / "ebible" / "corpus")
    return Settings(cache_dir=cache, figures_dir=FIXTURES / "figures_of_speech", offline=True)


@pytest.fixture
def glottolog() -> Glottolog:
    from rlr.glottolog import Glottolog

    return Glottolog.from_cldf(
        FIXTURES / "glottolog" / "languages.csv", FIXTURES / "glottolog" / "values.csv"
    )


@pytest.fixture
def corpus() -> EBibleCorpus:
    from rlr.ebible import EBibleCorpus

    d = FIXTURES / "ebible"
    return EBibleCorpus.from_files(
        d / "translations.csv", d / "licences.tsv", d / "lang_details.tsv"
    )


@pytest.fixture
def index() -> VerseIndex:
    from rlr.verses import VerseIndex

    return VerseIndex(FIXTURES / "ebible" / "vref.txt")


@pytest.fixture
def figures() -> FiguresOfSpeech:
    from rlr.resources.figures_of_speech import FiguresOfSpeech

    return FiguresOfSpeech(FIXTURES / "figures_of_speech")


@pytest.fixture
def pipeline(
    settings: Settings,
    glottolog: Glottolog,
    corpus: EBibleCorpus,
    index: VerseIndex,
    figures: FiguresOfSpeech,
) -> Pipeline:
    from rlr.agent import Pipeline
    from rlr.mt import NoTranslator

    return Pipeline(
        settings=settings,
        glottolog=glottolog,
        corpus=corpus,
        index=index,
        translator=NoTranslator(),
        resources=(figures,),
    )


@pytest.fixture
def translating_pipeline(pipeline: Pipeline) -> Pipeline:
    pipeline.translator = FakeTranslator()
    return pipeline
