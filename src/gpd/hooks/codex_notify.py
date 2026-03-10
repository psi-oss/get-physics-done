#!/usr/bin/env python3
"""Codex CLI notification hook — GPD edition.

Receives event payloads from Codex CLI notify system on stdin.
Currently handles: agent-turn-complete.
"""

import json
import os
import subprocess
import sys

from gpd.core.constants import ENV_GPD_DEBUG


def _debug(msg: str) -> None:
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _mapping(value: object) -> dict[str, object]:
    """Return *value* when it is a dict, otherwise an empty mapping."""
    return value if isinstance(value, dict) else {}


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


def _check_and_notify_update() -> None:
    """Read update cache and emit a notification to stderr if update available."""
    from gpd.hooks.runtime_detect import detect_active_runtime, get_update_cache_files, update_command_for_runtime

    latest_cache: dict[str, object] | None = None
    latest_checked = -1.0

    for cache_file in get_update_cache_files():
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
        runtime = detect_active_runtime()
        cmd = update_command_for_runtime(runtime)
        sys.stderr.write(f"[GPD] Update available: v{installed} \u2192 v{latest}. Run: {cmd}\n")


def main() -> None:
    """Entry point: read JSON event from stdin, handle agent-turn-complete."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        _debug(f"codex-notify stdin parse error: {exc}")
        return

    if not isinstance(data, dict):
        return

    if data.get("type") != "agent-turn-complete":
        return

    workspace_value = data.get("workspace")
    if isinstance(workspace_value, str) and workspace_value:
        cwd = workspace_value
    else:
        cwd = str(_mapping(workspace_value).get("current_dir") or os.getcwd())
    try:
        _trigger_update_check(cwd)
        _check_and_notify_update()
    except Exception:
        pass


if __name__ == "__main__":
    main()
