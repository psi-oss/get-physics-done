"""Small helpers for path labels shown in artifacts and return contracts."""

from __future__ import annotations

import posixpath

__all__ = ["normalize_posix_path_label"]


def normalize_posix_path_label(value: str) -> str:
    """Trim and normalize path label text with POSIX separators."""

    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    return posixpath.normpath(normalized)
