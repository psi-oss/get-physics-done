"""Small shared utility helpers with intentionally narrow semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "first_nonempty_string",
    "first_nonempty_stripped_string",
    "first_strict_bool",
    "paths_equal",
    "strict_bool_value",
    "utc_now_iso",
]


def paths_equal(left: Path, right: Path) -> bool:
    """Return whether two paths resolve to the same location when comparable."""
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser() == right.expanduser()


def strict_bool_value(value: object) -> bool | None:
    """Return bool values unchanged and reject bool-like aliases as unknown."""
    if isinstance(value, bool):
        return value
    return None


def utc_now_iso() -> str:
    """Return the current UTC timestamp in Python ISO-8601 format."""
    return datetime.now(UTC).isoformat()


def _object_value(value: object, key: str) -> object | None:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def first_nonempty_string(value: object, *keys: str) -> str:
    """Return the first non-empty string for keys from a mapping or object."""
    for key in keys:
        candidate = _object_value(value, key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def first_nonempty_stripped_string(value: object, *keys: str) -> str | None:
    """Return the first non-blank string, stripped, for keys from a mapping or object."""
    for key in keys:
        candidate = _object_value(value, key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def first_strict_bool(value: object, *keys: str) -> bool | None:
    """Return the first strict bool for keys from a mapping or object."""
    for key in keys:
        candidate = _object_value(value, key)
        if isinstance(candidate, bool):
            return candidate
    return None
