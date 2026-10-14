"""Turn the frozen dataclasses into plain JSON-able values.

Shared by the CLI's ``--json`` output and the demo server, so both surfaces
emit the same shape.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses, enums and containers to JSON-safe values."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, frozenset, set)):
        return [to_jsonable(v) for v in obj]
    return obj
