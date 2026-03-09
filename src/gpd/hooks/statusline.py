#!/usr/bin/env python3
"""Claude Code / OpenCode / Gemini / Codex statusline hook — GPD edition.

Reads JSON from stdin, outputs an ANSI-formatted statusline to stdout.
Shows: model | current task | directory | research position | context usage.
"""

import json
import os
import sys
from pathlib import Path

# Context bar thresholds (percentage of scaled usage)
_CONTEXT_REAL_LIMIT_PCT = 80
_CONTEXT_WARN_THRESHOLD = 63
_CONTEXT_HIGH_THRESHOLD = 81
_CONTEXT_CRITICAL_THRESHOLD = 95


def _context_bar(remaining_pct: float) -> str:
    """Build an ANSI-colored context-usage bar (scaled to real limit)."""
    rem = round(remaining_pct)
    raw_used = max(0, min(100, 100 - rem))
    used = min(100, round((raw_used / _CONTEXT_REAL_LIMIT_PCT) * 100))

    filled = used // 10
    bar = "\u2588" * filled + "\u2591" * (10 - filled)

    if used < _CONTEXT_WARN_THRESHOLD:
        return f" \x1b[32m{bar} {used}%\x1b[0m"
    if used < _CONTEXT_HIGH_THRESHOLD:
        return f" \x1b[33m{bar} {used}%\x1b[0m"
    if used < _CONTEXT_CRITICAL_THRESHOLD:
        return f" \x1b[38;5;208m{bar} {used}%\x1b[0m"
    return f" \x1b[5;31m\U0001f480 {bar} {used}%\x1b[0m"


def _debug(msg: str) -> None:
    if os.environ.get("GPD_DEBUG"):
        sys.stderr.write(f"[gpd-debug] {msg}\n")


def _read_position(workspace_dir: str) -> str:
    """Read research position from .planning/state.json."""
    state_file = Path(workspace_dir) / ".planning" / "state.json"
    if not state_file.exists():
        return ""
    try:
        state = json.loads(state_file.read_text())
        pos = state.get("position", {})
        phase = pos.get("current_phase")
        total_phases = pos.get("total_phases")
        if not phase or not total_phases:
            return ""
        result = f"P{phase}/{total_phases}"
        plan = pos.get("current_plan")
        total_plans = pos.get("total_plans_in_phase")
        if plan and total_plans:
            result += f" plan {plan}/{total_plans}"
        return result
    except Exception as exc:
        _debug(f"Failed to read state.json: {exc}")
        return ""


def _read_current_task(session_id: str) -> str:
    """Find the in-progress task across all runtime todo directories."""
    if not session_id:
        return ""

    from gpd.hooks.runtime_detect import get_todo_dirs

    todo_dirs = get_todo_dirs()

    matches: list[tuple[float, Path]] = []
    for todos_dir in todo_dirs:
        if not todos_dir.is_dir():
            continue
        try:
            for f in todos_dir.iterdir():
                if f.name.startswith(session_id) and "-agent-" in f.name and f.suffix == ".json":
                    try:
                        matches.append((f.stat().st_mtime, f))
                    except OSError as exc:
                        _debug(f"Failed to stat {f}: {exc}")
        except OSError as exc:
            _debug(f"Failed to read todo dir {todos_dir}: {exc}")

    matches.sort(key=lambda x: x[0], reverse=True)

    if not matches:
        return ""

    try:
        todos = json.loads(matches[0][1].read_text())
        for t in todos:
            if t.get("status") == "in_progress":
                return t.get("activeForm", "")
    except Exception as exc:
        _debug(f"Failed to parse todo file: {exc}")

    return ""


def _check_update() -> str:
    """Check GPD update cache files for available updates."""
    from gpd.hooks.runtime_detect import get_cache_dirs

    cache_paths = [Path.home() / ".gpd" / "cache" / "gpd-update-check.json"] + [
        d / "gpd-update-check.json" for d in get_cache_dirs()
    ]
    for cache_file in cache_paths:
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text())
                if cache.get("update_available"):
                    return "\x1b[33m\u2b06 /gpd:update\x1b[0m \u2502 "
            except Exception as exc:
                _debug(f"Failed to parse update cache {cache_file}: {exc}")
            break
    return ""


def main() -> None:
    """Entry point: read JSON from stdin, write ANSI statusline to stdout."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    model = (data.get("model") or {}).get("display_name", "Claude")
    workspace_dir = (data.get("workspace") or {}).get("current_dir", os.getcwd())
    session_id = data.get("session_id", "")
    remaining = (data.get("context_window") or {}).get("remaining_percentage")

    ctx = _context_bar(remaining) if remaining is not None else ""
    position = _read_position(workspace_dir)
    task = _read_current_task(session_id)
    gpd_update = _check_update()

    dirname = Path(workspace_dir).name
    pos_str = f" \u2502 \x1b[36m{position}\x1b[0m" if position else ""

    if task:
        sys.stdout.write(
            f"{gpd_update}\x1b[2m{model}\x1b[0m \u2502 \x1b[1m{task}\x1b[0m \u2502 \x1b[2m{dirname}\x1b[0m{pos_str}{ctx}"
        )
    else:
        sys.stdout.write(f"{gpd_update}\x1b[2m{model}\x1b[0m \u2502 \x1b[2m{dirname}\x1b[0m{pos_str}{ctx}")


if __name__ == "__main__":
    main()
