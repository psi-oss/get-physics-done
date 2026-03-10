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

from gpd.core.constants import ENV_GPD_DEBUG, PLANNING_DIR_NAME

try:
    from packaging.version import InvalidVersion, Version
except ModuleNotFoundError:
    try:
        from pip._vendor.packaging.version import InvalidVersion, Version
    except ModuleNotFoundError:
        InvalidVersion = ValueError
        Version = None

SECONDS_PER_HOUR = 3600
UPDATE_CHECK_TTL_SECONDS = 12 * SECONDS_PER_HOUR
PYPI_PACKAGE_NAME = "get-physics-done"


def _debug(msg: str) -> None:
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _version_files() -> list[Path]:
    """Return VERSION file candidates, preferring the active runtime's install first."""
    from gpd.hooks.runtime_detect import get_gpd_install_dirs

    return [d / "VERSION" for d in get_gpd_install_dirs(prefer_active=True)]


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
                return vf.read_text(encoding="utf-8").strip()
        except OSError as exc:
            _debug(f"Failed to read {vf}: {exc}")
    return "0.0.0"


def _is_older_than(a: str, b: str) -> bool:
    """Return True if version *a* is strictly older than *b*."""
    normalized_a = a.strip().lstrip("v")
    normalized_b = b.strip().lstrip("v")

    if Version is not None:
        try:
            return Version(normalized_a) < Version(normalized_b)
        except InvalidVersion as exc:
            _debug(f"Version parsing failed for {a!r} vs {b!r}: {exc}")

    def parts(v: str) -> tuple[int, int, int]:
        numeric_parts: list[int] = []
        for segment in v.split("."):
            digits = []
            for ch in segment:
                if not ch.isdigit():
                    break
                digits.append(ch)
            numeric_parts.append(int("".join(digits)) if digits else 0)
            if len(numeric_parts) == 3:
                break
        numeric_parts.extend([0] * (3 - len(numeric_parts)))
        return tuple(numeric_parts[:3])

    return parts(normalized_a) < parts(normalized_b)


def _do_check(cache_file: Path) -> None:
    """Perform the actual network check and write cache (runs in child process)."""
    installed = _read_installed_version()

    latest = None
    try:
        import urllib.request

        with urllib.request.urlopen(f"https://pypi.org/pypi/{PYPI_PACKAGE_NAME}/json", timeout=10) as resp:
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
        cache_file.write_text(json.dumps(result), encoding="utf-8")
    except OSError as exc:
        _debug(f"Failed to write update cache: {exc}")


def main() -> None:
    """Entry point: throttle-check for updates, spawn background worker if needed."""
    from gpd.hooks.runtime_detect import get_update_cache_files

    cache_candidates = get_update_cache_files()
    cache_file = cache_candidates[0] if cache_candidates else (Path.home() / PLANNING_DIR_NAME / "cache" / "gpd-update-check.json")

    # Throttle: skip if any candidate cache was checked recently.
    for candidate in cache_candidates:
        if not candidate.exists():
            continue
        try:
            cache = json.loads(candidate.read_text(encoding="utf-8"))
            checked = cache.get("checked")
            if isinstance(checked, (int, float)):
                age = int(time.time()) - int(checked)
                if 0 <= age < UPDATE_CHECK_TTL_SECONDS:
                    return
        except Exception as exc:
            _debug(f"Failed to read update cache {candidate}: {exc}")

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
