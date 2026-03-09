#!/usr/bin/env python3
"""Check for GPD updates in background, write result to cache.

Called by SessionStart hook — runs once per session.
Supports Claude Code, Codex, Gemini CLI, and OpenCode runtimes.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SECONDS_PER_HOUR = 3600
UPDATE_CHECK_TTL_SECONDS = 12 * SECONDS_PER_HOUR


def _debug(msg: str) -> None:
    if os.environ.get("GPD_DEBUG"):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _version_files() -> list[Path]:
    """Return VERSION file candidates: project-local first, then global, across runtimes."""
    from gpd.hooks.runtime_detect import get_gpd_install_dirs

    return [d / "VERSION" for d in get_gpd_install_dirs()]


def _read_installed_version() -> str:
    # Primary: importlib.metadata (single source of truth)
    try:
        from gpd.version import __version__

        if __version__ != "0.0.0-dev":
            return __version__
    except Exception as exc:
        _debug(f"importlib.metadata lookup failed: {exc}")

    # Fallback: VERSION files (for hook running outside installed package)
    for vf in _version_files():
        try:
            if vf.exists():
                return vf.read_text().strip()
        except OSError as exc:
            _debug(f"Failed to read {vf}: {exc}")
    return "0.0.0"


def _is_older_than(a: str, b: str) -> bool:
    """Return True if semver string *a* is strictly older than *b*."""

    def parts(v: str) -> list[int]:
        segs = v.split(".")
        return [int(s) for s in segs[:3]] + [0] * (3 - len(segs))

    pa, pb = parts(a), parts(b)
    for va, vb in zip(pa, pb, strict=False):
        if va < vb:
            return True
        if va > vb:
            return False
    return False


def _do_check(cache_file: Path) -> None:
    """Perform the actual network check and write cache (runs in child process)."""
    installed = _read_installed_version()

    latest = None
    try:
        import urllib.request

        with urllib.request.urlopen("https://pypi.org/pypi/gpd/json", timeout=10) as resp:
            data = json.loads(resp.read())
            latest = data["info"]["version"]
    except Exception as exc:
        _debug(f"PyPI version check failed: {exc}")

    result = {
        "update_available": bool(latest and _is_older_than(installed, latest)),
        "installed": installed,
        "latest": latest or "unknown",
        "checked": int(time.time()),
    }

    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result))
    except OSError as exc:
        _debug(f"Failed to write update cache: {exc}")


def main() -> None:
    """Entry point: throttle-check for updates, spawn background worker if needed."""
    home = Path.home()
    cache_dir = home / ".gpd" / "cache"
    cache_file = cache_dir / "gpd-update-check.json"

    # Throttle: skip if checked recently
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text())
            checked = cache.get("checked")
            if isinstance(checked, (int, float)):
                age = int(time.time()) - int(checked)
                if 0 <= age < UPDATE_CHECK_TTL_SECONDS:
                    return
        except Exception as exc:
            _debug(f"Failed to read update cache: {exc}")

    # Spawn background child to do the actual check
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"from gpd.hooks.check_update import _do_check; from pathlib import Path; _do_check(Path({str(cache_file)!r}))",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        _debug(f"Failed to spawn background update check: {exc}")


if __name__ == "__main__":
    main()
