"""Single source of truth for the GPD package version.

Reads from ``importlib.metadata`` so the only authoritative value is
``pyproject.toml [project] version``.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("get-physics-done")
except PackageNotFoundError:
    # Editable installs or running from source without install
    __version__ = "0.0.0-dev"
