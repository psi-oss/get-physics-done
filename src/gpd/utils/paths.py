"""Project root resolution.

Inlined from ``_paths._find_project_root`` so GPD
can locate project roots standalone.
"""

from __future__ import annotations

from pathlib import Path


def find_project_root() -> Path | None:
    """Find the project root by looking for pyproject.toml with a packages/ dir.

    Walks up from CWD and from this file's location, returning the first
    directory that contains both pyproject.toml and a packages/ subdirectory.
    """
    for start in (Path.cwd(), Path(__file__).resolve()):
        for parent in (start, *start.parents):
            pyproject = parent / "pyproject.toml"
            if pyproject.exists() and (parent / "packages").is_dir():
                return parent
    return None
