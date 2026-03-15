#!/usr/bin/env python3
"""Runtime-agnostic statusline hook for GPD.

Reads JSON from stdin, outputs an ANSI-formatted statusline to stdout.
Shows: GPD | model | path | current task | research position | context usage.
"""

import json
import math
import os
import sys
from pathlib import Path

from gpd.core.constants import ENV_GPD_DEBUG, PLANNING_DIR_NAME, STATE_JSON_FILENAME
from gpd.hooks.install_metadata import install_scope_from_manifest, installed_runtime, installed_update_command

# Context bar thresholds (percentage of scaled usage)
_CONTEXT_REAL_LIMIT_PCT = 80
_CONTEXT_WARN_THRESHOLD = 63
_CONTEXT_HIGH_THRESHOLD = 81
_CONTEXT_CRITICAL_THRESHOLD = 95
_STATUS_LABEL = "GPD"


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


def _first_value(value: object, *keys: str) -> object | None:
    """Return the first present value for *keys* from *value* when it is a mapping."""
    mapping = _mapping(value)
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def _hook_payload_policy(workspace_dir: str | None = None):
    """Return hook payload metadata for the active runtime or a merged fallback."""
    from gpd.adapters.runtime_catalog import get_hook_payload_policy
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_active_runtime_with_gpd_install

    workspace_path = Path(workspace_dir) if workspace_dir else None
    runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    return get_hook_payload_policy(None if runtime == RUNTIME_UNKNOWN else runtime)


def _format_context_window_size(value: object) -> str:
    """Return a compact context-window label like ``1M context``."""
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return ""

    size = int(value)
    if size >= 1_000_000:
        scaled = size / 1_000_000
        suffix = "M"
    elif size >= 1_000:
        scaled = size / 1_000
        suffix = "k"
    else:
        return f"{size} context"

    if scaled.is_integer() or scaled >= 100:
        compact = f"{scaled:.0f}"
    else:
        compact = f"{scaled:.1f}".rstrip("0").rstrip(".")
    return f"{compact}{suffix} context"


def _read_model_label(data: dict[str, object], hook_payload=None) -> str:
    """Return the current model label with context-window size when available."""
    policy = hook_payload or _hook_payload_policy()
    model_value = data.get("model")
    if isinstance(model_value, str) and model_value:
        model_label = model_value
    else:
        model_label = _first_string(model_value, *policy.model_keys)

    context_label = _format_context_window_size(
        _first_value(data.get("context_window"), *policy.context_window_size_keys)
    )
    if model_label and context_label:
        return f"{model_label} ({context_label})"
    return model_label


def _read_workspace_label(data: dict[str, object], workspace_dir: str, hook_payload=None) -> str:
    """Return a compact workspace label, relative to the project root when possible."""
    if not workspace_dir:
        return ""

    policy = hook_payload or _hook_payload_policy(workspace_dir)
    workspace_path = Path(workspace_dir).expanduser()
    workspace_value = data.get("workspace")
    project_dir = _first_string(workspace_value, *policy.project_dir_keys) or _first_string(data, *policy.project_dir_keys)

    try:
        resolved_workspace = workspace_path.resolve()
    except OSError:
        resolved_workspace = workspace_path

    if project_dir:
        project_path = Path(project_dir).expanduser()
        try:
            resolved_project = project_path.resolve()
            relative = resolved_workspace.relative_to(resolved_project)
            project_name = resolved_project.name or str(resolved_project)
            if relative.parts:
                return f"[{project_name}/{relative.as_posix()}]"
            return f"[{project_name}]"
        except (OSError, ValueError):
            pass

    display_name = resolved_workspace.name or workspace_dir
    return f"[{display_name}]"


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


def _self_config_dir() -> Path | None:
    """Return the installed runtime config dir when this hook runs from one."""
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "gpd-file-manifest.json").is_file() or (candidate / "get-physics-done").is_dir():
        return candidate
    return None


def _self_install_scope(config_dir: Path) -> str | None:
    """Return the persisted install scope for the hook's own config dir."""
    return install_scope_from_manifest(config_dir)


def _self_update_command(config_dir: Path) -> str | None:
    """Return the public update command for the installed runtime."""
    return installed_update_command(config_dir)


def _matching_todo_files(todos_dir: Path, session_id: str) -> list[tuple[float, Path]]:
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
    return matches


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

    from gpd.hooks.runtime_detect import (
        TodoCandidate,
        detect_active_runtime_with_gpd_install,
        detect_runtime_for_gpd_use,
        get_todo_candidates,
        should_consider_todo_candidate,
    )

    workspace_path = Path(workspace_dir) if workspace_dir else None
    active_installed_runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    preferred_runtime = detect_runtime_for_gpd_use(cwd=workspace_path)
    todo_candidates = get_todo_candidates(cwd=workspace_path, preferred_runtime=preferred_runtime)
    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        self_candidate = TodoCandidate(
            self_config_dir / "todos",
            runtime=installed_runtime(self_config_dir),
            scope=_self_install_scope(self_config_dir),
        )
        if all(candidate.path != self_candidate.path for candidate in todo_candidates):
            todo_candidates = [self_candidate, *todo_candidates]

    todo_files: list[tuple[float, Path]] = []
    for candidate in todo_candidates:
        if not should_consider_todo_candidate(
            candidate,
            active_installed_runtime=active_installed_runtime,
            cwd=workspace_path,
        ):
            continue
        todos_dir = candidate.path
        if not todos_dir.is_dir():
            continue
        todo_files.extend(_matching_todo_files(todos_dir, session_id))

    todo_files.sort(key=lambda item: item[0], reverse=True)
    for _mtime, todo_file in todo_files:
        for todo in _read_todo_entries(todo_file):
            if todo.get("status") != "in_progress":
                continue
            active_form = todo.get("activeForm")
            if isinstance(active_form, str) and active_form:
                return active_form

    return ""


def _workspace_from_payload(data: dict[str, object]) -> str:
    """Extract the workspace directory from a runtime hook payload."""
    from gpd.adapters.runtime_catalog import get_hook_payload_policy

    hook_payload = get_hook_payload_policy()
    workspace_value = data.get("workspace")
    if isinstance(workspace_value, str) and workspace_value:
        return workspace_value
    return _first_string(workspace_value, *hook_payload.workspace_keys) or _first_string(
        data,
        *hook_payload.workspace_keys,
    ) or os.getcwd()


def _read_context_remaining(data: dict[str, object], hook_payload) -> float | int | None:
    """Read remaining context percentage from runtime payload aliases."""
    remaining = _first_value(data.get("context_window"), *hook_payload.context_remaining_keys)
    if isinstance(remaining, (int, float)) and math.isfinite(remaining):
        return remaining
    return None


def _read_execution_state(workspace_dir: str | None = None) -> dict[str, object]:
    """Return the current normalized execution snapshot for the workspace."""
    from gpd.core.observability import get_current_execution

    workspace_path = Path(workspace_dir) if workspace_dir else None
    snapshot = get_current_execution(workspace_path)
    return snapshot.model_dump(mode="json") if snapshot is not None else {}


def _execution_reason_label(reason: str | None, *, default: str) -> str:
    text = (reason or "").strip().lower()
    if not text:
        return default
    if "user" in text or "review" in text or "approve" in text:
        return "user"
    if "depend" in text or "upstream" in text or "fanout" in text:
        return "dependency"
    if "anchor" in text or "checkpoint" in text:
        return "checkpoint"
    return default


def _elapsed_segment_label(started_at: object, updated_at: object) -> str:
    """Return a compact segment elapsed label like ``12m`` when timestamps parse."""
    if not isinstance(started_at, str) or not isinstance(updated_at, str):
        return ""
    try:
        from datetime import datetime

        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    elapsed_seconds = max(0, int((end - start).total_seconds()))
    if elapsed_seconds < 60:
        return f"{elapsed_seconds}s"
    if elapsed_seconds < 3600:
        return f"{elapsed_seconds // 60}m"
    return f"{elapsed_seconds // 3600}h"


def _execution_badge(snapshot: dict[str, object]) -> str:
    """Return a compact badge describing live execution state."""
    if not snapshot:
        return ""

    checkpoint_reason = _first_string(snapshot, "checkpoint_reason")
    waiting_reason = _first_string(snapshot, "waiting_reason")
    blocked_reason = _first_string(snapshot, "blocked_reason")
    segment_status = _first_string(snapshot, "segment_status").lower()
    skeptical_review = bool(snapshot.get("skeptical_requestioning_required"))
    pre_fanout_review = bool(snapshot.get("pre_fanout_review_pending"))

    if blocked_reason:
        badge = "BLOCKED"
    elif skeptical_review:
        badge = "REVIEW:skeptical"
    elif bool(snapshot.get("first_result_gate_pending")):
        badge = "REVIEW:first-result"
    elif pre_fanout_review:
        badge = "REVIEW:pre-fanout"
    elif bool(snapshot.get("waiting_for_review")):
        label = "checkpoint"
        if checkpoint_reason == "first_result":
            label = "first-result"
        elif checkpoint_reason == "skeptical_requestioning":
            label = "skeptical"
        elif checkpoint_reason == "pre_fanout":
            label = "pre-fanout"
        elif checkpoint_reason:
            label = checkpoint_reason.replace("_", "-")
        badge = f"REVIEW:{label}"
    elif waiting_reason:
        badge = f"WAIT:{_execution_reason_label(waiting_reason, default='hold')}"
    elif segment_status in {"paused", "ready_to_continue"}:
        badge = "RESUME" if _first_string(snapshot, "resume_file") else "PAUSED"
    elif segment_status:
        badge = "EXEC" if segment_status == "active" else segment_status.upper().replace("_", "-")
    else:
        return ""

    cadence = _first_string(snapshot, "review_cadence")
    elapsed = _elapsed_segment_label(snapshot.get("segment_started_at"), snapshot.get("updated_at"))
    parts = [badge]
    if cadence:
        parts.append(cadence)
    if elapsed:
        parts.append(elapsed)
    return " ".join(parts)


def _execution_artifact_label(snapshot: dict[str, object]) -> str:
    """Return the latest artifact or result label for live execution state."""
    if bool(snapshot.get("skeptical_requestioning_required")):
        weakest_anchor = _first_string(snapshot, "weakest_unchecked_anchor")
        if weakest_anchor:
            return weakest_anchor
    artifact = _first_string(snapshot, "last_artifact_path")
    if artifact:
        return Path(artifact).name
    return _first_string(snapshot, "last_result_label")


def _latest_update_cache(workspace_dir: str | None = None) -> tuple[dict[str, object] | None, object | None]:
    """Return the highest-priority valid update cache and its candidate metadata."""
    from types import SimpleNamespace

    from gpd.hooks.runtime_detect import (
        detect_active_runtime_with_gpd_install,
        get_update_cache_candidates,
        should_consider_update_cache_candidate,
    )

    workspace_path = Path(workspace_dir) if workspace_dir else None
    active_installed_runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        cache_file = self_config_dir / "cache" / "gpd-update-check.json"
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception as exc:
                _debug(f"Failed to parse update cache {cache_file}: {exc}")
            else:
                if isinstance(cache, dict):
                    candidate = SimpleNamespace(
                        path=cache_file,
                        runtime=None,
                        scope=_self_install_scope(self_config_dir),
                        config_dir=self_config_dir,
                    )
                    return cache, candidate

    preferred_runtime = active_installed_runtime if workspace_path is not None else None
    fallback_hit: tuple[dict[str, object], object] | None = None
    for candidate in get_update_cache_candidates(cwd=workspace_path, preferred_runtime=preferred_runtime):
        cache_file = candidate.path
        if not cache_file.exists():
            continue
        if not should_consider_update_cache_candidate(
            candidate,
            active_installed_runtime=active_installed_runtime,
            cwd=workspace_path,
        ):
            continue
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            _debug(f"Failed to parse update cache {cache_file}: {exc}")
            continue

        if not isinstance(cache, dict):
            _debug(f"Ignoring non-object update cache {cache_file}")
            continue

        if getattr(candidate, "runtime", None):
            return cache, candidate
        if fallback_hit is None:
            fallback_hit = (cache, candidate)

    return fallback_hit if fallback_hit is not None else (None, None)


def _check_update(workspace_dir: str | None = None) -> str:
    """Check GPD update cache files for available updates."""
    cache, cache_candidate = _latest_update_cache(workspace_dir)
    if cache and cache.get("update_available"):
        config_dir = getattr(cache_candidate, "config_dir", None)
        if isinstance(config_dir, Path):
            command = _self_update_command(config_dir) or "npx -y get-physics-done"
            return f"\x1b[33m\u2b06 {command}\x1b[0m \u2502 "

        from gpd.adapters import get_adapter
        from gpd.hooks.runtime_detect import (
            RUNTIME_UNKNOWN,
            _runtime_dir_has_gpd_install,
            detect_active_runtime_with_gpd_install,
            detect_install_scope,
            update_command_for_runtime,
        )

        workspace_path = Path(workspace_dir) if workspace_dir else None
        runtime = getattr(cache_candidate, "runtime", None) or RUNTIME_UNKNOWN
        scope = getattr(cache_candidate, "scope", None)
        if runtime != RUNTIME_UNKNOWN and not _runtime_dir_has_gpd_install(runtime, cwd=workspace_path):
            runtime = RUNTIME_UNKNOWN
            scope = None
        if runtime == RUNTIME_UNKNOWN:
            runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
        try:
            command = get_adapter(runtime).format_command("update")
        except KeyError:
            if scope is None and runtime != RUNTIME_UNKNOWN:
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
        workspace_dir = _workspace_from_payload(data)
        hook_payload = _hook_payload_policy(workspace_dir)

        session_value = data.get("session_id")
        session_id = session_value if isinstance(session_value, str) else ""
        remaining = _read_context_remaining(data, hook_payload)
        execution = _read_execution_state(workspace_dir)

        ctx = _context_bar(remaining) if isinstance(remaining, (int, float)) and math.isfinite(remaining) else ""
        position = _read_position(workspace_dir)
        execution_badge = _execution_badge(execution)
        execution_task = _first_string(execution, "current_task")
        task = execution_task or _read_current_task(session_id, workspace_dir)
        if execution_task:
            task = execution_task
        elif execution_badge:
            task = ""
        artifact_label = _execution_artifact_label(execution)
        gpd_update = _check_update(workspace_dir)
        model_label = _read_model_label(data, hook_payload)
        workspace_label = _read_workspace_label(data, workspace_dir, hook_payload)

        segments = [f"\x1b[2m{_STATUS_LABEL}\x1b[0m"]
        if model_label:
            segments.append(model_label)
        if workspace_label:
            segments.append(f"\x1b[2m{workspace_label}\x1b[0m")
        if execution_badge:
            segments.append(f"\x1b[35m{execution_badge}\x1b[0m")
        if task:
            segments.append(f"\x1b[1m{task}\x1b[0m")
        if artifact_label:
            segments.append(f"\x1b[2m{artifact_label}\x1b[0m")
        if position:
            segments.append(f"\x1b[36m{position}\x1b[0m")

        statusline = " \u2502 ".join(segments)
        if gpd_update:
            statusline = f"{gpd_update}{statusline}"

        sys.stdout.write(statusline)
        if ctx:
            sys.stdout.write(ctx)
    except Exception as exc:
        _debug(f"Statusline render failed: {exc}")
        sys.stdout.write("\x1b[2mGPD\x1b[0m")


if __name__ == "__main__":
    main()
