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
from types import SimpleNamespace

import gpd.hooks.install_context as hook_layout
from gpd.adapters.runtime_catalog import get_hook_payload_policy
from gpd.core.constants import ENV_GPD_DEBUG
from gpd.core.root_resolution import resolve_project_root
from gpd.core.state import load_state_json
from gpd.hooks.payload_policy import resolve_hook_payload_policy, resolve_hook_surface_runtime
from gpd.hooks.payload_roots import payload_uses_alias_only_workspace_mapping
from gpd.hooks.payload_roots import resolve_payload_roots as _resolve_payload_roots
from gpd.hooks.runtime_detect import SCOPE_LOCAL, detect_runtime_install_target
from gpd.hooks.runtime_lookup import resolve_runtime_lookup_context_from_payload_roots
from gpd.hooks.update_resolution import latest_update_cache as _shared_latest_update_cache
from gpd.hooks.update_resolution import update_command_for_candidate as _shared_update_command_for_candidate

# Context bar thresholds (percentage of scaled usage)
_CONTEXT_REAL_LIMIT_PCT = 80
_CONTEXT_WARN_THRESHOLD = 63
_CONTEXT_HIGH_THRESHOLD = 81
_CONTEXT_CRITICAL_THRESHOLD = 95
_STATUS_LABEL = "GPD"
_CANONICAL_MODEL_KEYS = ("display_name", "name", "id")
_CANONICAL_CONTEXT_WINDOW_SIZE_KEYS = ("context_window_size",)
_CANONICAL_CONTEXT_REMAINING_KEYS = ("remaining_percentage", "remainingPercent", "remaining")


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


def _merged_policy_keys(value: object, attribute: str, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
    """Return policy-owned keys plus canonical fallbacks, deduplicated in order."""
    raw_keys = getattr(value, attribute, ())
    merged: list[str] = []
    for key in (*raw_keys, *fallback):
        if isinstance(key, str) and key and key not in merged:
            merged.append(key)
    return tuple(merged)


def _object_value(value: object, key: str) -> object | None:
    """Return *key* from either a mapping or an attribute-bearing object."""
    if isinstance(value, dict) and key in value:
        return value.get(key)
    if hasattr(value, key):
        return getattr(value, key)
    return None


def _object_string(value: object, key: str) -> str:
    """Return a non-empty string field from either a mapping or an object."""
    candidate = _object_value(value, key)
    return candidate if isinstance(candidate, str) and candidate else ""


def _workspace_mapping_prefers_local_statusline_lookup(
    data: dict[str, object],
    *,
    hook_payload: object,
) -> bool:
    """Keep alias-only workspace mappings anchored to the runtime-owned workspace."""
    return payload_uses_alias_only_workspace_mapping(data, hook_payload=hook_payload)


def _compact_age_label(value: object) -> str:
    """Return a short age label like ``45m`` from a human label like ``45m ago``."""
    if not isinstance(value, str):
        return ""
    label = value.strip()
    if not label:
        return ""
    if label.endswith(" ago"):
        return label[:-4]
    return label


def _hook_payload_policy(workspace_dir: str | None = None):
    """Return hook payload metadata for the active runtime or a merged fallback."""
    return resolve_hook_payload_policy(hook_file=__file__, cwd=workspace_dir, surface="statusline")


def _root_resolution_policy(cwd: str | None = None):
    """Use merged aliases until a payload workspace is known, then narrow by runtime."""
    if cwd is None:
        return get_hook_payload_policy()
    return _hook_payload_policy(cwd)


def _payload_runtime(cwd: str | None = None) -> str | None:
    """Return the active installed runtime for one payload workspace, when known."""
    return resolve_hook_surface_runtime(hook_file=__file__, cwd=cwd, surface="statusline")


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
        model_label = _first_string(
            model_value,
            *_merged_policy_keys(policy, "model_keys", fallback=_CANONICAL_MODEL_KEYS),
        )

    context_label = _format_context_window_size(
        _first_value(
            data.get("context_window"),
            *_merged_policy_keys(policy, "context_window_size_keys", fallback=_CANONICAL_CONTEXT_WINDOW_SIZE_KEYS),
        )
    )
    if model_label and context_label:
        return f"{model_label} ({context_label})"
    return model_label


def _read_workspace_label(
    data: dict[str, object],
    workspace_dir: str,
    *,
    project_root: str | None = None,
    hook_payload=None,
) -> str:
    """Return a compact workspace label, relative to the project root when possible."""
    if not workspace_dir:
        return ""

    policy = hook_payload or _hook_payload_policy(workspace_dir)
    workspace_path = Path(workspace_dir).expanduser()
    workspace_value = data.get("workspace")
    project_dir = project_root or _first_string(workspace_value, *policy.project_dir_keys) or _first_string(
        data,
        *policy.project_dir_keys,
    )

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
    """Read research position from GPD/state.json."""
    workspace_root = resolve_project_root(workspace_dir, require_layout=True) or Path(workspace_dir).expanduser().resolve(strict=False)
    try:
        state = load_state_json(workspace_root)
    except Exception as exc:
        _debug(f"Failed to read state via canonical loader: {exc}")
        return ""

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

    todo_candidates = hook_layout.ordered_todo_lookup_candidates(
        hook_file=__file__,
        cwd=workspace_dir,
    )
    for candidate in todo_candidates:
        todos_dir = candidate.path
        if not todos_dir.is_dir():
            continue
        for _mtime, todo_file in _matching_todo_files(todos_dir, session_id):
            for todo in _read_todo_entries(todo_file):
                if todo.get("status") != "in_progress":
                    continue
                active_form = todo.get("activeForm")
                if isinstance(active_form, str) and active_form:
                    return active_form

    return ""


def _read_context_remaining(data: dict[str, object], hook_payload) -> float | int | None:
    """Read remaining context percentage from runtime payload aliases."""
    remaining = _first_value(
        data.get("context_window"),
        *_merged_policy_keys(hook_payload, "context_remaining_keys", fallback=_CANONICAL_CONTEXT_REMAINING_KEYS),
    )
    if isinstance(remaining, (int, float)) and math.isfinite(remaining):
        return remaining
    return None


def _read_session_id(data: dict[str, object], hook_payload) -> str:
    """Read the runtime session id using the adapter-owned contract."""
    for container in (
        data,
        data.get("workspace"),
        data.get("model"),
        data.get("usage"),
        data.get("token_usage"),
    ):
        session_id = _first_string(container, *hook_payload.runtime_session_id_keys)
        if session_id:
            return session_id
    return ""


def _read_execution_state(workspace_dir: str | None = None) -> dict[str, object]:
    """Return the current normalized execution snapshot for the workspace."""
    from gpd.core.observability import get_current_execution

    workspace_path = Path(workspace_dir) if workspace_dir else None
    snapshot = get_current_execution(workspace_path)
    return snapshot.model_dump(mode="json") if snapshot is not None else {}


def _read_runtime_hints(workspace_dir: str | None = None) -> dict[str, object]:
    """Return the shallow runtime hint payload for the workspace."""
    from gpd.core.runtime_hints import build_runtime_hint_payload

    payload = build_runtime_hint_payload(
        Path(workspace_dir) if workspace_dir else None,
        include_recovery=False,
        include_cost=False,
        include_workflow_presets=False,
    )
    return payload.model_dump(mode="json")


def _project_state_dir(
    data: dict[str, object],
    *,
    workspace_dir: str,
    project_root: str,
    runtime_lookup_dir: str,
    active_runtime: str | None,
    hook_payload: object,
) -> str:
    """Route project-owned state helpers to the project root unless the workspace owns the live runtime."""

    if runtime_lookup_dir != workspace_dir:
        return runtime_lookup_dir
    if not project_root or project_root == workspace_dir:
        return runtime_lookup_dir
    if _workspace_mapping_prefers_local_statusline_lookup(data, hook_payload=hook_payload):
        return runtime_lookup_dir

    normalized_project_root = str(Path(project_root).expanduser().resolve(strict=False))

    if isinstance(active_runtime, str) and active_runtime:
        install_target = detect_runtime_install_target(
            active_runtime,
            cwd=Path(workspace_dir).expanduser().resolve(strict=False),
        )
        if install_target is not None and install_target.install_scope == SCOPE_LOCAL:
            return runtime_lookup_dir

    return normalized_project_root


def _execution_reason_label(reason: str | None, *, default: str) -> str:
    text = (reason or "").strip().lower()
    if not text:
        return default
    if "result" in text or "skeptical" in text or "fanout" in text:
        return "review"
    if "budget" in text or "time" in text:
        return "budget"
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


def _execution_review_badge(snapshot: dict[str, object]) -> str:
    """Return a compact review/wait badge from a raw execution snapshot."""
    checkpoint_reason = _first_string(snapshot, "checkpoint_reason")
    waiting_reason = _first_string(snapshot, "waiting_reason")
    segment_status = _first_string(snapshot, "segment_status").lower()

    if bool(snapshot.get("skeptical_requestioning_required")):
        return "REVIEW:skeptical"
    if bool(snapshot.get("first_result_gate_pending")):
        return "REVIEW:first-result"
    if bool(snapshot.get("pre_fanout_review_pending")):
        return "REVIEW:pre-fanout"
    if bool(snapshot.get("waiting_for_review")):
        label = "checkpoint"
        if checkpoint_reason == "first_result":
            label = "first-result"
        elif checkpoint_reason == "skeptical_requestioning":
            label = "skeptical"
        elif checkpoint_reason == "pre_fanout":
            label = "pre-fanout"
        elif checkpoint_reason:
            label = checkpoint_reason.replace("_", "-")
        return f"REVIEW:{label}"
    if waiting_reason:
        return f"WAIT:{_execution_reason_label(waiting_reason, default='hold')}"
    if segment_status in {"paused", "ready_to_continue"}:
        return "RESUME" if _first_string(snapshot, "resume_file") else "PAUSED"
    if segment_status:
        return "EXEC" if segment_status == "active" else segment_status.upper().replace("_", "-")
    return ""


def _execution_badge(snapshot: dict[str, object], visibility: object | None = None) -> str:
    """Return a compact badge describing live execution state."""
    if not snapshot and visibility is None:
        return ""

    current_snapshot = snapshot
    classification = ""
    possibly_stalled = False
    if visibility is not None:
        current_execution = _object_value(visibility, "current_execution")
        if isinstance(current_execution, dict):
            current_snapshot = current_execution
        classification = _object_string(visibility, "status_classification")
        possibly_stalled = bool(_object_value(visibility, "possibly_stalled"))
        if not classification and isinstance(current_snapshot, dict):
            classification = _first_string(current_snapshot, "segment_status").lower()
    else:
        classification = _first_string(snapshot, "segment_status").lower()

    blocked_reason = _first_string(current_snapshot, "blocked_reason")
    if visibility is not None and not classification:
        return ""

    if visibility is not None:
        if classification == "blocked" or blocked_reason:
            badge = "BLOCKED"
        elif classification == "waiting":
            badge = _execution_review_badge(current_snapshot)
        elif classification == "paused-or-resumable":
            badge = "RESUME" if _first_string(current_snapshot, "resume_file") else "PAUSED"
        elif classification == "active":
            badge = "STALL?" if possibly_stalled else "EXEC"
        elif classification == "idle":
            return ""
        else:
            badge = _execution_review_badge(current_snapshot)
    else:
        badge = _execution_review_badge(current_snapshot)
        if not badge:
            return ""
        if blocked_reason:
            badge = "BLOCKED"

    cadence = _first_string(snapshot, "review_cadence")
    if badge == "STALL?" and visibility is not None:
        elapsed = _compact_age_label(_object_string(visibility, "last_updated_age_label"))
    else:
        elapsed = _elapsed_segment_label(snapshot.get("segment_started_at"), snapshot.get("updated_at"))
    parts = [badge]
    if cadence:
        parts.append(cadence)
    if elapsed:
        parts.append(elapsed)
    return " ".join(parts)


def _execution_artifact_label(snapshot: dict[str, object]) -> str:
    """Return the latest artifact, result, or rerun anchor label for live execution state."""
    if bool(snapshot.get("skeptical_requestioning_required")):
        weakest_anchor = _first_string(snapshot, "weakest_unchecked_anchor")
        if weakest_anchor:
            return weakest_anchor
    tangent_summary = _first_string(snapshot, "tangent_summary")
    if tangent_summary:
        tangent_decision = _first_string(snapshot, "tangent_decision")
        if tangent_decision:
            return f"{tangent_decision.replace('_', ' ')}: {tangent_summary}"
        return tangent_summary
    artifact = _first_string(snapshot, "last_artifact_path")
    if artifact:
        return Path(artifact).name
    last_result_label = _first_string(snapshot, "last_result_label")
    if last_result_label:
        return last_result_label
    last_result_id = _first_string(snapshot, "last_result_id")
    if last_result_id:
        return f"rerun anchor: {last_result_id}"
    return ""


def _latest_update_cache(workspace_dir: str | None = None) -> tuple[dict[str, object] | None, object | None]:
    return _shared_latest_update_cache(hook_file=__file__, cwd=workspace_dir, debug=_debug)


def _check_update(workspace_dir: str | None = None) -> str:
    """Check GPD update cache files for available updates."""
    cache, cache_candidate = _latest_update_cache(workspace_dir)
    if cache and cache.get("update_available"):
        command = _shared_update_command_for_candidate(
            cache_candidate,
            hook_file=__file__,
            cwd=workspace_dir,
        )
        if command is None:
            return ""
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
        roots = _resolve_payload_roots(data, policy_getter=_root_resolution_policy)
        workspace_dir = roots.workspace_dir
        project_root = roots.project_root
        project_dir_present = roots.project_dir_present
        project_dir_trusted = roots.project_dir_trusted
        payload_policy = _hook_payload_policy(workspace_dir)
        if project_dir_trusted is True and _workspace_mapping_prefers_local_statusline_lookup(
            data,
            hook_payload=payload_policy,
        ):
            project_dir_trusted = False
        runtime_roots = SimpleNamespace(
            workspace_dir=workspace_dir,
            project_root=project_root,
            project_dir_present=project_dir_present,
            project_dir_trusted=project_dir_trusted,
        )
        runtime_lookup = resolve_runtime_lookup_context_from_payload_roots(
            runtime_roots,
            runtime_resolver=_payload_runtime,
        )
        runtime_lookup_dir = runtime_lookup.lookup_dir

        hook_payload = _hook_payload_policy(runtime_lookup_dir)
        project_state_dir = _project_state_dir(
            data,
            workspace_dir=workspace_dir,
            project_root=project_root,
            runtime_lookup_dir=runtime_lookup_dir,
            active_runtime=runtime_lookup.active_runtime,
            hook_payload=hook_payload,
        )

        session_id = _read_session_id(data, hook_payload)
        remaining = _read_context_remaining(data, hook_payload)
        runtime_hints = _read_runtime_hints(project_state_dir)
        visibility = _mapping(runtime_hints.get("execution"))
        execution = _mapping(visibility.get("current_execution")) or _read_execution_state(project_state_dir)

        ctx = _context_bar(remaining) if isinstance(remaining, (int, float)) and math.isfinite(remaining) else ""
        position = _read_position(project_state_dir)
        execution_badge = _execution_badge(execution, visibility or None)
        execution_task = _object_string(visibility, "current_task") or _first_string(execution, "current_task")
        task = execution_task or _read_current_task(session_id, project_state_dir)
        if execution_task:
            task = execution_task
        elif execution_badge:
            task = ""
        artifact_label = _execution_artifact_label(execution)
        gpd_update = _check_update(project_state_dir)
        model_label = _read_model_label(data, hook_payload)
        workspace_label = _read_workspace_label(
            data,
            workspace_dir,
            project_root=project_root,
            hook_payload=hook_payload,
        )

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
