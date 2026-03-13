"""Version and source-checkout resolution helpers for GPD.

``__version__`` reflects the running Python package metadata when available.
When the CLI is invoked from inside a source checkout, helper functions in this
module can instead resolve the checkout's ``src/gpd`` tree and its
``pyproject.toml`` version so installs use the latest local source rather than
stale managed-environment package contents.
"""

from __future__ import annotations

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _read_pyproject_version(pyproject_path: Path) -> str | None:
    """Read ``[project].version`` from *pyproject_path* when available."""
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, tomllib.TOMLDecodeError):
        return None

    project = data.get("project")
    if not isinstance(project, dict):
        return None

    raw_version = project.get("version")
    return str(raw_version) if raw_version else None


def _version_from_pyproject() -> str | None:
    """Best-effort fallback for source checkouts without installed metadata."""
    return _read_pyproject_version(Path(__file__).resolve().parents[2] / "pyproject.toml")


def _is_checkout_root(root: Path) -> bool:
    """Return whether *root* looks like a GPD source checkout."""
    src_gpd = root / "src" / "gpd"
    return (
        (root / "pyproject.toml").is_file()
        and (root / "package.json").is_file()
        and (src_gpd / "commands").is_dir()
        and (src_gpd / "agents").is_dir()
        and (src_gpd / "hooks").is_dir()
        and (src_gpd / "specs").is_dir()
    )


def _find_checkout_root(start: Path) -> Path | None:
    """Walk upward from *start* to find the nearest GPD checkout root."""
    current = start.expanduser().resolve(strict=False)
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if _is_checkout_root(candidate):
            return candidate
    return None


def checkout_root(start: Path | None = None) -> Path | None:
    """Resolve the active GPD checkout root, preferring *start* when provided."""
    if start is not None:
        root = _find_checkout_root(Path(start))
        if root is not None:
            return root
    return _find_checkout_root(Path(__file__).resolve())


def resolve_install_gpd_root(start: Path | None = None) -> Path:
    """Return the GPD source tree to use for installs.

    When invoked from inside a source checkout, prefer that checkout's
    ``src/gpd`` tree. Otherwise fall back to the running package directory.
    """
    root = checkout_root(start)
    if root is not None:
        return root / "src" / "gpd"
    return Path(__file__).resolve().parent


def version_for_gpd_root(gpd_root: Path) -> str | None:
    """Return the source version associated with *gpd_root*, if it is a checkout."""
    root = _find_checkout_root(gpd_root)
    if root is None:
        return None
    return _read_pyproject_version(root / "pyproject.toml")


def resolve_active_version(start: Path | None = None) -> str:
    """Return the version that should be shown for the active source context."""
    root = checkout_root(start)
    if root is not None:
        checkout_version = _read_pyproject_version(root / "pyproject.toml")
        if checkout_version:
            return checkout_version
    return __version__


try:
    __version__ = version("get-physics-done")
except PackageNotFoundError:
    # Editable installs or running from source without install
    __version__ = _version_from_pyproject() or "0.0.0-dev"


__all__ = [
    "__version__",
    "checkout_root",
    "resolve_active_version",
    "resolve_install_gpd_root",
    "version_for_gpd_root",
]
