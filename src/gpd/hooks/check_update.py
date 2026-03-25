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

SECONDS_PER_HOUR = 3600
UPDATE_CHECK_TTL_SECONDS = 12 * SECONDS_PER_HOUR
UPDATE_CHECK_INFLIGHT_TTL_SECONDS = 5 * 60
NPM_PACKAGE_NAME = "get-physics-done"
NPM_LATEST_RELEASE_URL = f"https://registry.npmjs.org/{NPM_PACKAGE_NAME}/latest"
_VERSION_RELEASE_RE = re.compile(r"^\s*v?(?P<release>\d+(?:\.\d+)*)(?P<suffix>.*)$")


def _trim_trailing_zero_segments(parts: tuple[int, ...]) -> tuple[int, ...]:
    trimmed = parts
    while len(trimmed) > 1 and trimmed[-1] == 0:
        trimmed = trimmed[:-1]
    return trimmed


def _suffix_rank(suffix: str) -> tuple[int, int]:
    normalized = suffix.lower().split("+", 1)[0]
    if not normalized:
        return 1, 0

    def _extract_number(tag: str) -> int:
        match = re.search(rf"{re.escape(tag)}(?:[._-])?(\d+)", normalized)
        return int(match.group(1)) if match is not None and match.group(1) else 0

    if "post" in normalized:
        return 2, _extract_number("post")
    if "dev" in normalized:
        return -3, _extract_number("dev")
    if "alpha" in normalized or re.search(r"(?:^|[._-])a\d*", normalized):
        return -2, _extract_number("alpha") or _extract_number("a")
    if "beta" in normalized or re.search(r"(?:^|[._-])b\d*", normalized):
        return -1, _extract_number("beta") or _extract_number("b")
    if "rc" in normalized:
        return 0, _extract_number("rc")
    return -1, 0


def _version_key(version: str) -> tuple[tuple[int, ...], int, int, str]:
    normalized = version.strip().lstrip("v").split("+", 1)[0]
    match = _VERSION_RELEASE_RE.match(normalized)
    if match is None:
        return ((), -1, 0, normalized.casefold())

    release = tuple(int(part) for part in match.group("release").split("."))
    release = _trim_trailing_zero_segments(release) or (0,)
    rank, number = _suffix_rank(match.group("suffix"))
    return (release, rank, number, "")


def _debug(msg: str) -> None:
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _self_config_dir() -> Path | None:
    """Return the installed runtime config dir when this hook runs from one."""
    from gpd.hooks.install_metadata import config_dir_has_complete_install

    candidate = Path(__file__).resolve().parent.parent
    if config_dir_has_complete_install(candidate):
        return candidate
    return None


def _version_files() -> list[Path]:
    """Return VERSION file candidates, preferring the active runtime's install first."""
    from gpd.hooks.runtime_detect import get_gpd_install_dirs

    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        return [self_config_dir / GPD_INSTALL_DIR_NAME / "VERSION"]

    return [install_dir / "VERSION" for install_dir in get_gpd_install_dirs(prefer_active=True)]


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
    return _version_key(a) < _version_key(b)


def _do_check(cache_file: Path) -> None:
    """Perform the actual network check and write cache (runs in child process)."""
    try:
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
    finally:
        _clear_inflight_marker(cache_file)


def _inflight_marker(cache_file: Path) -> Path:
    return cache_file.with_name(f"{cache_file.name}.inflight")


def _inflight_started_at(marker_path: Path) -> int | None:
    try:
        raw = marker_path.read_text(encoding="utf-8").strip()
    except OSError:
        try:
            return int(marker_path.stat().st_mtime)
        except OSError:
            return None
    try:
        return int(raw)
    except ValueError:
        try:
            return int(marker_path.stat().st_mtime)
        except OSError:
            return None


def _has_fresh_inflight_marker(cache_file: Path) -> bool:
    marker_path = _inflight_marker(cache_file)
    if not marker_path.exists():
        return False
    started_at = _inflight_started_at(marker_path)
    if started_at is None:
        return False
    age = int(time.time()) - started_at
    return 0 <= age < UPDATE_CHECK_INFLIGHT_TTL_SECONDS


def _claim_inflight_marker(cache_file: Path) -> bool:
    marker_path = _inflight_marker(cache_file)
    if _has_fresh_inflight_marker(cache_file):
        return False
    if marker_path.exists():
        try:
            marker_path.unlink()
        except OSError:
            if _has_fresh_inflight_marker(cache_file):
                return False
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        fd = os.open(marker_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except (FileExistsError, OSError):
        return False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(int(time.time())))
    except OSError:
        try:
            marker_path.unlink()
        except OSError:
            pass
        return False
    return True


def _clear_inflight_marker(cache_file: Path) -> None:
    try:
        _inflight_marker(cache_file).unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def main() -> None:
    """Entry point: throttle-check for updates, spawn background worker if needed."""
    from gpd.hooks.runtime_detect import (
        ALL_RUNTIMES,
        RUNTIME_UNKNOWN,
        UpdateCacheCandidate,
        detect_active_runtime_with_gpd_install,
        detect_runtime_for_gpd_use,
        get_update_cache_candidates,
        should_consider_update_cache_candidate,
    )

    resolved_cwd = Path.cwd()
    resolved_home = Path.home()
    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        cache_file = self_config_dir / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME
        relevant_candidates = [UpdateCacheCandidate(path=cache_file)]
    else:
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
        if active_installed_runtime in (None, "", RUNTIME_UNKNOWN) and preferred_runtime in ALL_RUNTIMES:
            preferred_candidates = [candidate for candidate in cache_candidates if candidate.runtime == preferred_runtime]
            fallback_candidates = [candidate for candidate in relevant_candidates if candidate.runtime is None]
            if preferred_candidates:
                seen_paths: set[Path] = set()
                preferred_first: list[UpdateCacheCandidate] = []
                for candidate in [*preferred_candidates, *fallback_candidates]:
                    if candidate.path in seen_paths:
                        continue
                    seen_paths.add(candidate.path)
                    preferred_first.append(candidate)
                relevant_candidates = preferred_first
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
    has_runtime_specific_candidate = any(candidate.runtime in ALL_RUNTIMES for candidate in relevant_candidates)
    for candidate in relevant_candidates:
        if candidate.runtime is None and has_runtime_specific_candidate:
            continue
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

    if not _claim_inflight_marker(cache_file):
        return

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
        _clear_inflight_marker(cache_file)
        _debug(f"Failed to spawn background update check: {exc}")


if __name__ == "__main__":
    main()
