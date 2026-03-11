#!/usr/bin/env python3
"""Runtime notification hook for GPD."""

import json
import os
import subprocess
import sys
from pathlib import Path

from gpd.core.constants import ENV_GPD_DEBUG


def _debug(msg: str) -> None:
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _mapping(value: object) -> dict[str, object]:
    """Return *value* when it is a dict, otherwise an empty mapping."""
    return value if isinstance(value, dict) else {}


def _first_string(value: object, *keys: str) -> str:
    """Return the first non-empty string for *keys* from *value* when it is a mapping."""
    mapping = _mapping(value)
    for key in keys:
        candidate = mapping.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def _trigger_update_check(cwd: str) -> None:
    """Opportunistically refresh the update cache (throttled by check_update)."""
    try:
        subprocess.Popen(
            [sys.executable, "-m", "gpd.hooks.check_update"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
        )
    except OSError as exc:
        _debug(f"Failed to spawn check_update.py: {exc}")


def _check_and_notify_update(cwd: str | None = None) -> None:
    """Read update cache and emit a notification to stderr if update available."""
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_active_runtime_with_gpd_install,
        detect_install_scope,
        get_update_cache_files,
        update_command_for_runtime,
    )

    workspace_path = Path(cwd) if cwd else None
    runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)

    latest_cache: dict[str, object] | None = None
    latest_checked = -1.0

    for cache_file in get_update_cache_files(cwd=workspace_path, preferred_runtime=runtime):
        if not cache_file.exists():
            continue
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            _debug(f"Failed to parse cache {cache_file}: {exc}")
            continue

        if not isinstance(cache, dict):
            continue
        checked = cache.get("checked")
        checked_value = float(checked) if isinstance(checked, (int, float)) else -1.0
        if latest_cache is None or checked_value > latest_checked:
            latest_cache = cache
            latest_checked = checked_value

    if latest_cache and latest_cache.get("update_available"):
        installed = latest_cache.get("installed", "?")
        latest = latest_cache.get("latest", "?")
        scope = None if runtime == RUNTIME_UNKNOWN else detect_install_scope(runtime, cwd=workspace_path)
        cmd = update_command_for_runtime(runtime, scope=scope)
        sys.stderr.write(f"[GPD] Update available: v{installed} \u2192 v{latest}. Run: {cmd}\n")


def _workspace_from_payload(data: dict[str, object]) -> str:
    workspace_value = data.get("workspace")
    if isinstance(workspace_value, str) and workspace_value:
        return workspace_value
    return _first_string(workspace_value, "current_dir", "cwd", "path", "workspace_dir") or os.getcwd()


def main() -> None:
    """Entry point: read a JSON event from stdin and process notifications."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        _debug(f"notify stdin parse error: {exc}")
        return

    if not isinstance(data, dict):
        return

    if data.get("type") not in ("agent-turn-complete", None):
        return

    cwd = _workspace_from_payload(data)
    try:
        _trigger_update_check(cwd)
        _check_and_notify_update(cwd)
    except Exception as exc:
        _debug(f"notify handler failed: {exc}")


if __name__ == "__main__":
    main()
