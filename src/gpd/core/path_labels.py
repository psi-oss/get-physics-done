"""Small helpers for path labels shown in artifacts and return contracts."""

from __future__ import annotations

import posixpath
from pathlib import Path

__all__ = ["normalize_posix_path_label", "project_relative_path_label"]


def normalize_posix_path_label(value: str) -> str:
    """Trim and normalize path label text with POSIX separators."""

    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    return posixpath.normpath(normalized)


def project_relative_path_label(project_root: Path, path: Path | None) -> str | None:
    """Return a POSIX label relative to ``project_root`` when possible."""

    if path is None:
        return None
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()
