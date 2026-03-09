"""GPD version compatibility checking."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.mcp.gpd_bridge.discovery import GPD_CORE_DIR
from gpd.version import __version__ as GPD_REQUIRED_VERSION  # noqa: N812


def check_gpd_version(gpd_dir: Path) -> tuple[bool, str]:
    """Check installed GPD version against the pinned requirement.

    Reads ``package.json`` from the GPD core directory and compares the
    ``version`` field with ``GPD_REQUIRED_VERSION`` using exact string match.

    Returns:
        A ``(is_compatible, installed_version)`` tuple.
    """
    pkg_json_path = gpd_dir / GPD_CORE_DIR / "package.json"
    try:
        pkg_data = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False, "0.0.0"
    installed = pkg_data.get("version", "0.0.0")
    is_compatible = installed == GPD_REQUIRED_VERSION
    return is_compatible, installed


def format_version_warning(installed: str, required: str) -> str:
    """Return a formatted warning string for version mismatch display."""
    return (
        f"GPD version mismatch: installed {installed}, required {required}.\n"
        "Some commands may not work as expected. Run 'gpd update' to fix."
    )
