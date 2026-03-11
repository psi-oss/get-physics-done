#!/usr/bin/env python3
"""Claude Code / Gemini statusline hook — GPD edition.

Reads JSON from stdin, outputs an ANSI-formatted statusline to stdout.
Shows: model | current task | directory | research position | context usage.
"""

import json
import math
import os
import sys
from pathlib import Path

from gpd.core.constants import ENV_GPD_DEBUG, PLANNING_DIR_NAME, STATE_JSON_FILENAME

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


def _read_position(workspace_dir: str) -> str:
    """Read research position from .gpd/state.json."""
    state_file = Path(workspace_dir) / PLANNING_DIR_NAME / STATE_JSON_FILENAME
    if not state_file.exists():
        return ""
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            return ""
        pos = state.get("position", {})
        phase = pos.get("current_phase")
        total_phases = pos.get("total_phases")
        if phase is None or total_phases is None:
            return ""
        result = f"P{phase}/{total_phases}"
        plan = pos.get("current_plan")
        total_plans = pos.get("total_plans_in_phase")
        if plan is not None and total_plans is not None:
            result += f" plan {plan}/{total_plans}"
        return result
    except Exception as exc:
        _debug(f"Failed to read state.json: {exc}")
        return ""


def _matching_todo_files(todos_dir: Path, session_id: str) -> list[Path]:
    """Return matching todo files for a session ordered newest-first within one directory."""
    matches: list[tuple[float, Path]] = []
    try:
        for todo_file in todos_dir.iterdir():
            if todo_file.name.startswith(f"{session_id}-agent-") and todo_file.suffix == ".json":
                try:
                    matches.append((todo_file.stat().st_mtime, todo_file))
                except OSError as exc:
                    _debug(f"Failed to stat {todo_file}: {exc}")
    except OSError as exc:
        _debug(f"Failed to read todo dir {todos_dir}: {exc}")
        return []

    matches.sort(key=lambda item: item[0], reverse=True)
    return [todo_file for _, todo_file in matches]


def _read_todo_entries(todo_file: Path) -> list[dict[str, object]]:
    """Return normalized todo entries from one JSON file."""
    try:
        payload = json.loads(todo_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _debug(f"Failed to parse todo file {todo_file}: {exc}")
        return []

    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    if isinstance(payload, dict):
        return [payload]

    _debug(f"Ignoring non-object todo file {todo_file}")
    return []


def _read_current_task(session_id: str, workspace_dir: str | None = None) -> str:
    """Find the in-progress task across all runtime todo directories."""
    if not session_id:
        return ""

    from gpd.hooks.runtime_detect import get_todo_dirs

    workspace_path = Path(workspace_dir) if workspace_dir else None
    todo_dirs = get_todo_dirs(cwd=workspace_path)

    for todos_dir in todo_dirs:
        if not todos_dir.is_dir():
            continue
        for todo_file in _matching_todo_files(todos_dir, session_id):
            for todo in _read_todo_entries(todo_file):
                if todo.get("status") != "in_progress":
                    continue
                active_form = todo.get("activeForm")
                if isinstance(active_form, str) and active_form:
                    return active_form

    return ""


def _latest_update_cache(workspace_dir: str | None = None) -> dict[str, object] | None:
    """Return the freshest valid update cache across all runtime locations."""
    from gpd.hooks.runtime_detect import detect_active_runtime, get_update_cache_files

    workspace_path = Path(workspace_dir) if workspace_dir else None
    preferred_runtime = detect_active_runtime(cwd=workspace_path) if workspace_path else None
    latest_cache: dict[str, object] | None = None
    latest_checked = -1.0

    for cache_file in get_update_cache_files(cwd=workspace_path, preferred_runtime=preferred_runtime):
        if not cache_file.exists():
            continue
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            _debug(f"Failed to parse update cache {cache_file}: {exc}")
            continue

        if not isinstance(cache, dict):
            _debug(f"Ignoring non-object update cache {cache_file}")
            continue

        checked = cache.get("checked")
        checked_value = float(checked) if isinstance(checked, (int, float)) else -1.0
        if latest_cache is None or checked_value > latest_checked:
            latest_cache = cache
            latest_checked = checked_value

    return latest_cache


def _check_update(workspace_dir: str | None = None) -> str:
    """Check GPD update cache files for available updates."""
    cache = _latest_update_cache(workspace_dir)
    if cache and cache.get("update_available"):
        from gpd.adapters import get_adapter
        from gpd.hooks.runtime_detect import detect_active_runtime, detect_install_scope, update_command_for_runtime

        workspace_path = Path(workspace_dir) if workspace_dir else None
        runtime = detect_active_runtime(cwd=workspace_path)
        try:
            command = get_adapter(runtime).format_command("update")
        except KeyError:
            scope = detect_install_scope(runtime, cwd=workspace_path)
            command = update_command_for_runtime(runtime, scope=scope)
        return f"\x1b[33m\u2b06 {command}\x1b[0m \u2502 "
    return ""


def main() -> None:
    """Entry point: read JSON from stdin, write ANSI statusline to stdout."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        _debug(f"Failed to parse stdin JSON: {exc}")
        return

    if not isinstance(data, dict):
        return

    try:
        model_value = data.get("model")
        if isinstance(model_value, str) and model_value:
            model = model_value
        else:
            model = _first_string(model_value, "display_name", "name", "id") or "unknown"

        workspace_value = data.get("workspace")
        if isinstance(workspace_value, str) and workspace_value:
            workspace_dir = workspace_value
        else:
            workspace_dir = _first_string(workspace_value, "current_dir", "cwd", "path", "workspace_dir") or os.getcwd()

        session_value = data.get("session_id")
        session_id = session_value if isinstance(session_value, str) else ""
        remaining = _mapping(data.get("context_window")).get("remaining_percentage")
        if not isinstance(remaining, (int, float)):
            remaining = _mapping(data.get("context_window")).get("remainingPercent")
        if not isinstance(remaining, (int, float)):
            remaining = _mapping(data.get("context_window")).get("remaining")

        ctx = _context_bar(remaining) if isinstance(remaining, (int, float)) and math.isfinite(remaining) else ""
        position = _read_position(workspace_dir)
        task = _read_current_task(session_id, workspace_dir)
        gpd_update = _check_update(workspace_dir)

        dirname = Path(workspace_dir).name
        pos_str = f" \u2502 \x1b[36m{position}\x1b[0m" if position else ""

        if task:
            sys.stdout.write(
                f"{gpd_update}\x1b[2m{model}\x1b[0m \u2502 \x1b[1m{task}\x1b[0m \u2502 \x1b[2m{dirname}\x1b[0m{pos_str}{ctx}"
            )
        else:
            sys.stdout.write(f"{gpd_update}\x1b[2m{model}\x1b[0m \u2502 \x1b[2m{dirname}\x1b[0m{pos_str}{ctx}")
    except Exception as exc:
        _debug(f"Statusline render failed: {exc}")
        sys.stdout.write("\x1b[2mGPD\x1b[0m")


if __name__ == "__main__":
    main()
