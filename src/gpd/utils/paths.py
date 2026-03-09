"""Project root resolution.

Inlined from ``_paths._find_project_root`` so GPD
can locate project roots standalone.
"""

from __future__ import annotations

from pathlib import Path


def _looks_like_project_root(candidate: Path) -> bool:
    """Return True when *candidate* matches a supported GPD repo layout."""
    if not candidate.is_dir():
        return False

    has_repo_metadata = (candidate / "pyproject.toml").is_file() or (candidate / ".git").exists()
    has_layout_marker = (
        (candidate / "infra").is_dir()
        or (candidate / "packages").is_dir()
        or (candidate / "src" / "gpd").is_dir()
    )
    return has_repo_metadata and has_layout_marker


def find_project_root(start: Path | None = None) -> Path | None:
    """Find the GPD project root from CWD, an explicit start, or this module.

    Supports both the current ``src/gpd`` repository layout and older
    ``packages/``-based layouts.
    """
    starts = [Path.cwd(), Path(__file__).resolve()]
    if start is not None:
        starts.insert(0, Path(start).expanduser().resolve())

    seen: set[Path] = set()
    for origin in starts:
        current = origin if origin.is_dir() else origin.parent
        for parent in (current, *current.parents):
            if parent in seen:
                continue
            seen.add(parent)
            if _looks_like_project_root(parent):
                return parent
    return None
