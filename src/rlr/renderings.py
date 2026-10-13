"""Pre-rendered translations, consulted before any live machine-translation backend.

Live MT needs an 11 GB model and a few seconds per sentence, which is fine on a
workstation and a poor fit for someone who clones the repository to try the
demo. So the renderings RLR would produce for a language can be computed once
(``rlr pretranslate``) and shipped as data: one gzipped JSON file per target
language, keyed by a hash of the source text, with the backend, the source
dataset and its license recorded in the file.

Files are looked up in order: ``RLR_RENDERINGS_DIR`` if set, the user's cache
(``~/.cache/rlr/renderings``), then the copies bundled with the package under
``rlr/data/renderings``. The first file that has the text wins.

Renderings of unfoldingWord's notes are derivative works and carry the notes'
own CC BY-SA 4.0 license; the file says so.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.resources import files
from typing import TYPE_CHECKING, Any

from rlr.resources.figures_of_speech import ALTERNATIVES_LABEL

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from importlib.resources.abc import Traversable
    from pathlib import Path

    from rlr.mt import Translator
    from rlr.resources import ResourceNote
    from rlr.types import LanguageCode

FORMAT = 1


def rendering_key(text: str, source: LanguageCode) -> str:
    """Stable key for a source text: a hash, so files never embed the English."""
    digest = hashlib.sha256(f"{source}\x1f{text}".encode()).hexdigest()
    return digest[:32]


@dataclass(slots=True)
class RenderingFile:
    """One target language's renderings, as stored on disk."""

    backend: str
    source: LanguageCode
    target: LanguageCode
    derived_from: str
    license: str
    generated: str = ""
    entries: dict[str, str] = field(default_factory=dict)

    def lookup(self, text: str, source: LanguageCode) -> str | None:
        """The stored rendering of ``text``, if any."""
        if source.split("_")[0] != self.source.split("_")[0]:
            return None
        return self.entries.get(rendering_key(text, self.source))

    def to_json(self) -> dict[str, Any]:
        """The on-disk form."""
        return {
            "format": FORMAT,
            "backend": self.backend,
            "source": self.source,
            "target": self.target,
            "derived_from": self.derived_from,
            "license": self.license,
            "generated": self.generated,
            "entries": dict(sorted(self.entries.items())),
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> RenderingFile:
        """Parse the on-disk form."""
        return cls(
            backend=str(raw["backend"]),
            source=str(raw["source"]),
            target=str(raw["target"]),
            derived_from=str(raw.get("derived_from", "")),
            license=str(raw.get("license", "")),
            generated=str(raw.get("generated", "")),
            entries={str(k): str(v) for k, v in raw.get("entries", {}).items()},
        )


def file_name(target: LanguageCode) -> str:
    """``swh.json.gz`` for Swahili."""
    return f"{target.split('_')[0]}.json.gz"


def read_file(path: Path | Traversable) -> RenderingFile:
    """Load a gzipped rendering file."""
    with path.open("rb") as fh:
        raw = json.loads(gzip.decompress(fh.read()).decode("utf-8"))
    return RenderingFile.from_json(raw)


def write_file(path: Path, rendering: RenderingFile) -> None:
    """Write a gzipped rendering file, deterministically, via a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(rendering.to_json(), ensure_ascii=False, indent=0).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".part")
    with tmp.open("wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(data)
    tmp.replace(path)


def bundled_dir() -> Traversable:
    """The renderings shipped inside the package."""
    return files("rlr") / "data" / "renderings"


class RenderingCache:
    """Renderings from several directories, first match wins."""

    def __init__(self, dirs: Sequence[Path | Traversable]) -> None:
        """Search ``dirs`` in order for ``<target>.json.gz`` files."""
        self.dirs = list(dirs)
        self._loaded: dict[str, list[RenderingFile]] = {}

    def _files(self, target: LanguageCode) -> list[RenderingFile]:
        bare = target.split("_")[0]
        if bare not in self._loaded:
            found: list[RenderingFile] = []
            for d in self.dirs:
                candidate = d / file_name(bare)
                if candidate.is_file():
                    found.append(read_file(candidate))
            self._loaded[bare] = found
        return self._loaded[bare]

    def backends(self) -> set[str]:
        """Names of every backend that produced a file in any directory."""
        if not hasattr(self, "_backends"):
            found: set[str] = set()
            for d in self.dirs:
                if not d.is_dir():
                    continue
                for entry in d.iterdir():
                    if entry.name.endswith(".json.gz"):
                        found.add(read_file(entry).backend)
            self._backends: set[str] = found
        return set(self._backends)

    def has_language(self, source: LanguageCode, target: LanguageCode) -> bool:
        """Whether any file renders ``source`` into ``target``."""
        src = source.split("_")[0]
        return any(f.source.split("_")[0] == src for f in self._files(target))

    def lookup(
        self, text: str, source: LanguageCode, target: LanguageCode
    ) -> tuple[str, str] | None:
        """``(rendering, backend)`` for ``text``, or ``None``."""
        for f in self._files(target):
            hit = f.lookup(text, source)
            if hit is not None:
                return hit, f.backend
        return None

    def backend_for(self, source: LanguageCode, target: LanguageCode) -> str | None:
        """The backend named by the first file that renders this pair."""
        src = source.split("_")[0]
        for f in self._files(target):
            if f.source.split("_")[0] == src:
                return f.backend
        return None


def note_texts(notes: Iterable[ResourceNote]) -> list[str]:
    """Every translatable string the given notes need, deduplicated, in order."""
    seen: dict[str, None] = {ALTERNATIVES_LABEL: None}
    for note in notes:
        for part in note.parts:
            if part.translate and part.text:
                seen.setdefault(part.text, None)
    return list(seen)


def render_texts(
    texts: Sequence[str],
    translator: Translator,
    source: LanguageCode,
    target: LanguageCode,
    existing: RenderingFile,
    *,
    batch_size: int = 32,
    progress: Any = None,
) -> int:
    """Translate the texts ``existing`` lacks and add them to it. Returns the count added."""
    todo = [t for t in texts if rendering_key(t, source) not in existing.entries]
    many = getattr(translator, "translate_many", None)
    added = 0
    for start in range(0, len(todo), batch_size):
        batch = todo[start : start + batch_size]
        rendered = (
            many(batch, source, target)
            if callable(many)
            else [translator.translate(t, source, target) for t in batch]
        )
        for text, out in zip(batch, rendered, strict=True):
            existing.entries[rendering_key(text, source)] = out
        added += len(batch)
        if progress is not None:
            progress(added, len(todo))
    existing.generated = datetime.now(UTC).date().isoformat()
    return added


__all__ = [
    "RenderingCache",
    "RenderingFile",
    "bundled_dir",
    "file_name",
    "note_texts",
    "read_file",
    "render_texts",
    "rendering_key",
    "write_file",
]
