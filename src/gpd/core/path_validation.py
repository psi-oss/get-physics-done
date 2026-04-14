"""Shared helpers for validating project-relative path strings."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

__all__ = ["is_cross_platform_absolute_path"]


def is_cross_platform_absolute_path(path_text: str) -> bool:
    """Return whether *path_text* is absolute under POSIX or Windows rules.

    Surrounding whitespace is ignored so validation stays stable even when a
    caller has already checked for non-empty strings but has not trimmed before
    classifying the path.
    """

    normalized = path_text.strip()
    if not normalized:
        return False
    if normalized.startswith("/"):
        return True
    if PureWindowsPath(normalized).is_absolute():
        return True
    return Path(normalized).is_absolute()
