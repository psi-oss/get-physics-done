"""Version and source-checkout resolution helpers for GPD.

``__version__`` reflects the running Python package metadata when available.
When the CLI is invoked from inside a source checkout, helper functions in this
module can instead resolve the checkout's ``src/gpd`` tree and its
``pyproject.toml`` version so installs use the latest local source rather than
stale managed-environment package contents.
"""

from __future__ import annotations

import os
import re
import sys
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


def _checkout_python_candidates(root: Path) -> tuple[Path, ...]:
    """Return plausible checkout-local Python interpreter paths."""
    if os.name == "nt":
        relpaths = (
            Path(".venv") / "Scripts",
            Path("venv") / "Scripts",
        )
    else:
        relpaths = (
            Path(".venv") / "bin",
            Path("venv") / "bin",
        )
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add_candidate(path: Path) -> None:
        if path in seen:
            return
        seen.add(path)
        candidates.append(path)

    pattern = re.compile(r"^python(?:\d+(?:\.\d+)?)?(?:\.exe)?$")
    preferred_name = "python.exe" if os.name == "nt" else "python"
    for relpath in relpaths:
        bindir = root / relpath
        add_candidate(bindir / preferred_name)
        if not bindir.is_dir():
            continue
        for child in sorted(bindir.iterdir()):
            if not child.is_file():
                continue
            if child.name == preferred_name or not pattern.fullmatch(child.name):
                continue
            add_candidate(child)
    return tuple(candidates)


def current_python_executable() -> str | None:
    """Return the active interpreter path when Python knows it explicitly."""
    executable = sys.executable if isinstance(sys.executable, str) else None
    if executable:
        executable = executable.strip()
    return executable or None


def resolve_checkout_python(start: Path | None = None, *, fallback: str | None = None) -> str | None:
    """Return the preferred Python interpreter for the active checkout.

    When a source checkout is available, installed runtime artifacts should
    point at the checkout's own virtualenv if present so copied hook scripts,
    MCP servers, and runtime bridges all import the same live source tree.
    Return ``None`` when no checkout is available so managed-install callers
    can keep their own interpreter selection. Fall back to *fallback* only
    when a checkout exists but its local virtualenv is missing.
    """
    root = checkout_root(start)
    if root is None:
        return None

    for candidate in _checkout_python_candidates(root):
        if candidate.is_file():
            return str(candidate)

    return fallback


def reexec_from_checkout_if_needed(
    *,
    cwd: Path,
    active_gpd: Path,
    module: str,
    argv: list[str],
    disable_env_name: str,
) -> None:
    """Re-exec through the nearest checkout when the active package differs."""
    if os.environ.get(disable_env_name) == "1":
        return

    root = checkout_root(cwd)
    if root is None:
        return

    checkout_gpd = (root / "src" / "gpd").resolve(strict=False)
    if active_gpd.resolve(strict=False) == checkout_gpd:
        return

    env = os.environ.copy()
    checkout_src = str((root / "src").resolve(strict=False))
    existing_pythonpath = [entry for entry in env.get("PYTHONPATH", "").split(os.pathsep) if entry]
    if checkout_src not in existing_pythonpath:
        env["PYTHONPATH"] = os.pathsep.join([checkout_src, *existing_pythonpath]) if existing_pythonpath else checkout_src
    env[disable_env_name] = "1"
    active_python = current_python_executable()
    checkout_python = resolve_checkout_python(root, fallback=active_python) or active_python
    if checkout_python is None:
        return
    os.execve(checkout_python, [checkout_python, "-m", module, *argv], env)


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
    "current_python_executable",
    "resolve_checkout_python",
    "resolve_active_version",
    "resolve_install_gpd_root",
    "version_for_gpd_root",
]
