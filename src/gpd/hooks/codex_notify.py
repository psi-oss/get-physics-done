#!/usr/bin/env python3
"""Codex CLI notification hook — GPD edition.

Receives event payloads from Codex CLI notify system on stdin.
Currently handles: agent-turn-complete.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def _debug(msg: str) -> None:
    if os.environ.get("GPD_DEBUG"):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


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
        _debug(f"Failed to spawn gpd-check-update: {exc}")


def _check_and_notify_update() -> None:
    """Read update cache and emit a notification to stderr if update available."""
    from gpd.hooks.runtime_detect import detect_active_runtime, get_cache_dirs, update_command_for_runtime

    cache_paths = [Path.home() / ".gpd" / "cache" / "gpd-update-check.json"] + [
        d / "gpd-update-check.json" for d in get_cache_dirs()
    ]
    for cache_file in cache_paths:
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
                if cache.get("update_available"):
                    installed = cache.get("installed", "?")
                    latest = cache.get("latest", "?")
                    runtime = detect_active_runtime()
                    cmd = update_command_for_runtime(runtime)
                    sys.stderr.write(f"[GPD] Update available: v{installed} \u2192 v{latest}. Run: {cmd}\n")
            except Exception as exc:
                _debug(f"Failed to parse cache {cache_file}: {exc}")
            break


def main() -> None:
    """Entry point: read JSON event from stdin, handle agent-turn-complete."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        _debug(f"codex-notify stdin parse error: {exc}")
        return

    if data.get("type") != "agent-turn-complete":
        return

    cwd = (data.get("workspace") or {}).get("current_dir", os.getcwd())
    _trigger_update_check(cwd)
    _check_and_notify_update()


if __name__ == "__main__":
    main()
