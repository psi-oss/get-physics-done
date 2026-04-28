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
from gpd.adapters.runtime_catalog import get_shared_install_metadata
from gpd.core.constants import ENV_GPD_DEBUG
from gpd.hooks.install_context import should_prefer_self_owned_install
from gpd.hooks.install_metadata import config_dir_has_complete_install, load_install_manifest_state

_SHARED_INSTALL_METADATA = get_shared_install_metadata()
SECONDS_PER_HOUR = 3600
UPDATE_CHECK_TTL_SECONDS = 12 * SECONDS_PER_HOUR
UPDATE_CHECK_INFLIGHT_TTL_SECONDS = 5 * 60
LATEST_RELEASE_URL = _SHARED_INSTALL_METADATA.latest_release_url
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
    return 1, 0


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
    from gpd.hooks.install_context import detect_self_owned_install

    self_install = detect_self_owned_install(__file__)
    return None if self_install is None else self_install.config_dir


def _parse_worker_cache_file(argv: list[str]) -> Path | None:
    """Return the cache file for worker-mode invocations."""
    if len(argv) == 2 and argv[0] == "--cache-file" and argv[1]:
        return Path(argv[1])
    return None


def _background_worker_command(cache_file: Path) -> list[str]:
    """Return the background-worker command anchored to the current hook script."""
    return [
        sys.executable,
        str(Path(__file__).resolve(strict=False)),
        "--cache-file",
        str(cache_file),
    ]


def _version_files() -> list[Path]:
    """Return VERSION file candidates, preferring the active runtime's install first."""
    from gpd.hooks.runtime_detect import get_gpd_install_dirs

    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        return [self_config_dir / GPD_INSTALL_DIR_NAME / "VERSION"]

    version_files: list[Path] = []
    for install_dir in get_gpd_install_dirs(prefer_active=True):
        config_dir = install_dir.parent
        if not config_dir_has_complete_install(config_dir):
            _debug(f"Skipping non-authoritative VERSION file candidate {install_dir / 'VERSION'}")
            continue
        version_files.append(install_dir / "VERSION")
    return version_files


def _read_manifest_version(config_dir: Path) -> str | None:
    """Return the install manifest's version when it is present and usable."""
    manifest_state, manifest = load_install_manifest_state(config_dir)
    if manifest_state != "ok":
        return None
    version = manifest.get("version")
    if not isinstance(version, str):
        return None
    version = version.strip()
    return version or None


def _read_installed_version() -> str:
    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        version_file = self_config_dir / GPD_INSTALL_DIR_NAME / "VERSION"
        try:
            if version_file.exists():
                version = version_file.read_text(encoding="utf-8").strip()
                if version:
                    return version
        except OSError as exc:
            _debug(f"Failed to read self-owned VERSION file {version_file}: {exc}")
        return _read_manifest_version(self_config_dir) or "0.0.0"

    try:
        from gpd.version import __version__

        if __version__ != "0.0.0-dev":
            return __version__
    except Exception as exc:
        _debug(f"importlib.metadata lookup failed: {exc}")

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

            with urllib.request.urlopen(LATEST_RELEASE_URL, timeout=10) as resp:
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


def _relevant_update_cache_candidates(
    *,
    self_config_dir: Path | None,
    resolved_cwd: Path,
    resolved_home: Path,
) -> tuple[list[object], Path]:
    from gpd.hooks.install_context import detect_self_owned_install
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, UpdateCacheCandidate, detect_runtime_install_target
    from gpd.hooks.update_resolution import (
        ordered_update_cache_candidates,
        primary_update_cache_file,
        resolve_update_cache_inputs,
    )

    workspace_path, resolved_home, active_installed_runtime, preferred_runtime = resolve_update_cache_inputs(
        cwd=resolved_cwd,
        home=resolved_home,
    )
    shared_candidates = ordered_update_cache_candidates(
        cwd=workspace_path,
        home=resolved_home,
        active_installed_runtime=active_installed_runtime,
        preferred_runtime=preferred_runtime,
    )

    if self_config_dir is not None:
        self_install = detect_self_owned_install(__file__)
        active_install_target = (
            detect_runtime_install_target(active_installed_runtime, cwd=workspace_path, home=resolved_home)
            if active_installed_runtime not in (None, "", RUNTIME_UNKNOWN)
            else None
        )
        if should_prefer_self_owned_install(
            self_install,
            active_install_target=active_install_target,
            active_runtime=active_installed_runtime,
            workspace_path=workspace_path,
        ):
            self_candidate = (
                UpdateCacheCandidate(path=self_config_dir / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME)
                if self_install is None
                else UpdateCacheCandidate(
                    path=self_install.cache_file,
                    runtime=self_install.runtime,
                    scope=self_install.install_scope,
                )
            )
            relevant_candidates = [self_candidate]
            seen_paths = {self_candidate.path}
            for candidate in shared_candidates:
                candidate_path = getattr(candidate, "path", None)
                if candidate_path in seen_paths:
                    continue
                seen_paths.add(candidate_path)
                relevant_candidates.append(candidate)
        else:
            relevant_candidates = shared_candidates
    else:
        relevant_candidates = shared_candidates

    return relevant_candidates, primary_update_cache_file(relevant_candidates, home=resolved_home)


def main(argv: list[str] | None = None) -> None:
    """Entry point: throttle-check for updates, spawn background worker if needed."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    worker_cache_file = _parse_worker_cache_file(raw_argv)
    if worker_cache_file is not None:
        _do_check(worker_cache_file)
        return

    from gpd.hooks.runtime_detect import (
        supported_runtime_names,
    )

    resolved_cwd = Path.cwd()
    resolved_home = Path.home()
    self_config_dir = _self_config_dir()
    relevant_candidates, cache_file = _relevant_update_cache_candidates(
        self_config_dir=self_config_dir,
        resolved_cwd=resolved_cwd,
        resolved_home=resolved_home,
    )

    # Throttle: skip only when the preferred runtime/home cache set is still fresh.
    runtime_names = supported_runtime_names()
    has_runtime_specific_candidate = any(candidate.runtime in runtime_names for candidate in relevant_candidates)
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
            _background_worker_command(cache_file),
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
