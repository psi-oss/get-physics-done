"""Single source of truth for the GPD package version.

Reads from ``importlib.metadata`` so the only authoritative value is
``pyproject.toml [project] version``.
"""

from __future__ import annotations

from pathlib import Path
import tomllib
from importlib.metadata import PackageNotFoundError, version


def _version_from_pyproject() -> str | None:
    """Best-effort fallback for source checkouts without installed metadata."""
    try:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return None

    project = data.get("project")
    if not isinstance(project, dict):
        return None

    raw_version = project.get("version")
    return str(raw_version) if raw_version else None


try:
    __version__ = version("get-physics-done")
except PackageNotFoundError:
    # Editable installs or running from source without install
    __version__ = _version_from_pyproject() or "0.0.0-dev"
