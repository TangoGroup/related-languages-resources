"""Runtime settings and the download cache.

Every external dataset RLR downloads (Glottolog, the eBible Corpus) is fetched
once into a cache directory and read from disk after that. The figures-of-speech
notes are the exception: they ship inside the ``bible-figures-of-speech``
package, so stage 5 needs no download.

Settings come from environment variables so the CLI, tests and any future
service share one source of truth:

``RLR_CACHE_DIR``
    Where downloaded files live. Default ``$XDG_CACHE_HOME/rlr`` or
    ``~/.cache/rlr``.
``RLR_FIGURES_DIR``
    Optional directory holding a different snapshot of the figures-of-speech
    data (``figs_types.yaml`` plus ``figs_instances/``). Unset, the copy
    bundled with ``bible-figures-of-speech`` is used.
``RLR_RENDERINGS_DIR``
    Optional directory of pre-rendered translations (``<lwc>.json.gz``, see
    :mod:`rlr.renderings`), searched before the cache and the bundled copies.
``RLR_LWC_CSV``
    Optional path to an ``lwc.csv`` (per-language LWC probabilities, see
    :func:`rlr.languages.suggest_lwcs`) for suggesting Languages of Wider
    Communication.
``RLR_MT``
    Machine-translation backend: ``none`` (default) or ``madlad`` /
    ``madlad:<model-id>``. See :mod:`rlr.mt`.
``RLR_MT_DEVICE``
    Force the device for the live backend (``cuda``, ``mps`` or ``cpu``);
    unset, the best available is picked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import httpx


def _default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "rlr"


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved runtime settings."""

    cache_dir: Path = field(default_factory=_default_cache_dir)
    figures_dir: Path | None = None
    renderings_dir: Path | None = None
    lwc_csv: Path | None = None
    mt_backend: str = "none"
    #: Skip network access entirely; missing files raise instead of download.
    offline: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        """Read settings from the ``RLR_*`` environment variables."""
        cache = os.environ.get("RLR_CACHE_DIR")
        figures = os.environ.get("RLR_FIGURES_DIR")
        renderings = os.environ.get("RLR_RENDERINGS_DIR")
        lwc = os.environ.get("RLR_LWC_CSV")
        return cls(
            cache_dir=Path(cache).expanduser() if cache else _default_cache_dir(),
            figures_dir=Path(figures).expanduser() if figures else None,
            renderings_dir=Path(renderings).expanduser() if renderings else None,
            lwc_csv=Path(lwc).expanduser() if lwc else None,
            mt_backend=os.environ.get("RLR_MT", "none"),
            offline=os.environ.get("RLR_OFFLINE", "") not in ("", "0", "false"),
        )


class OfflineError(RuntimeError):
    """Raised when a needed file is absent and downloads are disabled."""


def fetch_cached(url: str, relative_path: str, settings: Settings) -> Path:
    """Return a local path for ``url``, downloading into the cache if needed.

    Args:
        url: Where to fetch the file from.
        relative_path: Path under ``settings.cache_dir`` to store it at.
        settings: Runtime settings.

    Returns:
        The cached file's path.

    Raises:
        OfflineError: If the file is missing and ``settings.offline`` is set.
        httpx.HTTPStatusError: If the download fails.
    """
    target = settings.cache_dir / relative_path
    if target.exists():
        return target
    if settings.offline:
        msg = f"{target} is not cached and downloads are disabled"
        raise OfflineError(msg)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    tmp.replace(target)
    return target
