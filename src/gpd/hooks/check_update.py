#!/usr/bin/env python3
"""Check for GPD updates in background and write the result to cache."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from gpd.adapters.install_utils import CACHE_DIR_NAME, GPD_INSTALL_DIR_NAME, UPDATE_CACHE_FILENAME
from gpd.core.constants import ENV_GPD_DEBUG, PLANNING_DIR_NAME

try:
    from packaging.version import InvalidVersion, Version
except ImportError:
    try:
        from pip._vendor.packaging.version import InvalidVersion, Version
    except ImportError:
        InvalidVersion = ValueError
        Version = None

SECONDS_PER_HOUR = 3600
UPDATE_CHECK_TTL_SECONDS = 12 * SECONDS_PER_HOUR
NPM_PACKAGE_NAME = "get-physics-done"
NPM_LATEST_RELEASE_URL = f"https://registry.npmjs.org/{NPM_PACKAGE_NAME}/latest"


def _debug(msg: str) -> None:
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _version_files() -> list[Path]:
    """Return VERSION file candidates, preferring the active runtime's install first."""
    from gpd.hooks.runtime_detect import (
        ALL_RUNTIMES,
        _global_runtime_dir,
        _local_runtime_dir,
        detect_runtime_for_gpd_use,
    )

    resolved_cwd = Path.cwd()
    resolved_home = Path.home()
    active_runtime = detect_runtime_for_gpd_use(cwd=resolved_cwd, home=resolved_home)
    runtimes = [active_runtime] + [runtime for runtime in ALL_RUNTIMES if runtime != active_runtime]

    install_dirs: list[Path] = []
    for runtime in runtimes:
        if runtime not in ALL_RUNTIMES:
            continue
        install_dirs.append(_local_runtime_dir(runtime, resolved_cwd) / GPD_INSTALL_DIR_NAME)
        install_dirs.append(_global_runtime_dir(runtime, home=resolved_home) / GPD_INSTALL_DIR_NAME)

    seen: set[Path] = set()
    ordered: list[Path] = []
    for install_dir in install_dirs:
        if install_dir in seen:
            continue
        seen.add(install_dir)
        ordered.append(install_dir)
    return [d / "VERSION" for d in ordered]


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

    def parts(v: str) -> tuple[int, int, int, int]:
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
        # Pre-release versions (dev/alpha/beta/rc) sort before final release
        is_pre = -1 if re.search(r"(?:dev|alpha|beta|rc|\d+[ab]\d+)", v) else 0
        return (numeric_parts[0], numeric_parts[1], numeric_parts[2], is_pre)

    return parts(normalized_a) < parts(normalized_b)


def _do_check(cache_file: Path) -> None:
    """Perform the actual network check and write cache (runs in child process)."""
    installed = _read_installed_version()

    latest = None
    try:
        import urllib.request

        with urllib.request.urlopen(NPM_LATEST_RELEASE_URL, timeout=10) as resp:
            data = json.loads(resp.read())
            latest = data["version"]
    except Exception as exc:
        _debug(f"npm registry version check failed: {exc}")

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
    from gpd.hooks.runtime_detect import (
        ALL_RUNTIMES,
        detect_active_runtime_with_gpd_install,
        detect_runtime_for_gpd_use,
        get_update_cache_candidates,
        should_consider_update_cache_candidate,
    )

    resolved_cwd = Path.cwd()
    resolved_home = Path.home()
    cache_candidates = get_update_cache_candidates(cwd=resolved_cwd, home=resolved_home)
    active_installed_runtime = detect_active_runtime_with_gpd_install(cwd=resolved_cwd, home=resolved_home)
    preferred_runtime = detect_runtime_for_gpd_use(cwd=resolved_cwd, home=resolved_home)
    relevant_candidates = [
        candidate
        for candidate in cache_candidates
        if should_consider_update_cache_candidate(
            candidate,
            active_installed_runtime=active_installed_runtime,
            cwd=resolved_cwd,
            home=resolved_home,
        )
    ]
    if active_installed_runtime in (None, "", "unknown") and preferred_runtime in ALL_RUNTIMES:
        relevant_candidates = [
            candidate
            for candidate in relevant_candidates
            if candidate.runtime in (None, preferred_runtime)
        ]
    cache_file = (
        relevant_candidates[0].path
        if relevant_candidates
        else (resolved_home / PLANNING_DIR_NAME / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME)
    )

    # Throttle: skip only when the preferred runtime/home cache set is still fresh.
    for candidate in relevant_candidates:
        candidate_path = candidate.path
        if not candidate_path.exists():
            continue
        try:
            cache = json.loads(candidate_path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                continue
            checked = cache.get("checked")
            if isinstance(checked, (int, float)):
                age = int(time.time()) - int(checked)
                if 0 <= age < UPDATE_CHECK_TTL_SECONDS:
                    return
        except Exception as exc:
            _debug(f"Failed to read update cache {candidate_path}: {exc}")

    # Spawn background child to do the actual check
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; from gpd.hooks.check_update import _do_check; from pathlib import Path; _do_check(Path(sys.argv[1]))",
                str(cache_file),
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
