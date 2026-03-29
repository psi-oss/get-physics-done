#!/usr/bin/env python3
"""Runtime notification hook for GPD."""

import json
import os
import subprocess
import sys
from pathlib import Path

from gpd.adapters.runtime_catalog import get_hook_payload_policy
from gpd.core.constants import ENV_GPD_DEBUG, ProjectLayout
from gpd.core.observability import humanize_execution_reason
from gpd.core.root_resolution import resolve_project_root
from gpd.core.utils import atomic_write, file_lock
from gpd.hooks.payload_policy import resolve_hook_payload_policy, resolve_hook_surface_runtime
from gpd.hooks.payload_roots import project_root_from_payload as _shared_project_root_from_payload
from gpd.hooks.payload_roots import resolve_payload_roots as _resolve_payload_roots
from gpd.hooks.payload_roots import workspace_dir_from_payload as _shared_workspace_dir_from_payload
from gpd.hooks.update_resolution import latest_update_cache as _shared_latest_update_cache
from gpd.hooks.update_resolution import update_command_for_candidate as _shared_update_command_for_candidate

_PAUSED_SEGMENT_STATES = {"paused", "awaiting_user", "ready_to_continue"}
_COMPLETED_SEGMENT_STATES = {"completed", "complete", "done", "finished"}


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
        check_update_script = Path(__file__).resolve(strict=False).with_name("check_update.py")
        subprocess.Popen(
            [sys.executable, str(check_update_script)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
        )
    except OSError as exc:
        _debug(f"Failed to spawn check_update.py: {exc}")


def _hook_payload_policy(cwd: str | None = None):
    """Return hook payload metadata for the active runtime or a merged fallback."""
    return resolve_hook_payload_policy(hook_file=__file__, cwd=cwd, surface="notify")


def _root_resolution_policy(cwd: str | None = None):
    """Use merged aliases until a payload workspace is known, then narrow by runtime."""
    if cwd is None:
        return get_hook_payload_policy()
    return _hook_payload_policy(cwd)


def _payload_runtime(cwd: str | None = None) -> str | None:
    """Return the active installed runtime for one payload workspace, when known."""
    return resolve_hook_surface_runtime(hook_file=__file__, cwd=cwd, surface="notify")


def _runtime_supports_usage_telemetry(runtime: str | None) -> bool:
    """Return whether one concrete runtime exposes a usage-telemetry contract."""
    if not isinstance(runtime, str) or not runtime.strip():
        return False

    from gpd.adapters.runtime_catalog import get_runtime_capabilities

    try:
        capability = get_runtime_capabilities(runtime)
    except Exception:
        return False
    return capability.telemetry_source == "notify-hook" and capability.telemetry_completeness != "none"


def _record_usage_telemetry(data: dict[str, object], *, workspace_dir: str, project_root: str) -> None:
    """Persist measured usage/cost telemetry when the runtime payload exposes it."""
    from gpd.core.costs import record_usage_from_runtime_payload

    try:
        runtime = _payload_runtime(project_root)
        if not _runtime_supports_usage_telemetry(runtime):
            _debug("usage telemetry skipped: runtime capability unknown or unsupported")
            return
        record_usage_from_runtime_payload(
            data,
            runtime=runtime,
            cwd=Path(workspace_dir),
            workspace_root=Path(workspace_dir),
            project_root=Path(project_root),
        )
    except Exception as exc:
        # Usage telemetry is advisory only and must never break the notify hook.
        _debug(f"usage telemetry skipped: {exc}")


def _latest_update_cache(cwd: str | None = None) -> tuple[dict[str, object] | None, object | None]:
    return _shared_latest_update_cache(hook_file=__file__, cwd=cwd, debug=_debug)


def _check_and_notify_update(cwd: str | None = None) -> None:
    """Read update cache and emit a notification to stderr if update available."""
    latest_cache, latest_candidate = _latest_update_cache(cwd)

    if latest_cache and latest_cache.get("update_available"):
        cmd = _shared_update_command_for_candidate(latest_candidate, hook_file=__file__, cwd=cwd)
        if cmd is None:
            return
        installed = latest_cache.get("installed", "?")
        latest = latest_cache.get("latest", "?")
        sys.stderr.write(f"[GPD] Update available: v{installed} \u2192 v{latest}. Run: {cmd}\n")


def _workspace_dir_from_payload(data: dict[str, object], *, cwd: str | None = None) -> str:
    return _shared_workspace_dir_from_payload(
        data,
        policy_getter=_root_resolution_policy,
        cwd=cwd,
    )


def _project_root_from_payload(
    data: dict[str, object],
    workspace_dir: str,
    *,
    cwd: str | None = None,
) -> str:
    """Resolve the project root for one notify payload workspace."""
    return _shared_project_root_from_payload(
        data,
        workspace_dir,
        policy_getter=_root_resolution_policy,
        cwd=cwd,
    )


def _resolved_project_root_from_payload(data: dict[str, object], *, cwd: str | None = None) -> str:
    """Return the resolved project root for one notify payload workspace."""
    return _resolve_payload_roots(
        data,
        policy_getter=_root_resolution_policy,
        cwd=cwd,
    ).project_root


def _notification_state_path(cwd: str) -> Path:
    workspace_root = resolve_project_root(cwd, require_layout=True) or Path(cwd).expanduser().resolve(strict=False)
    return ProjectLayout(workspace_root).last_observability_notification


def _load_last_notification(cwd: str) -> dict[str, object]:
    path = _notification_state_path(cwd)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _claim_last_notification(cwd: str, fingerprint: str) -> bool:
    """Atomically claim a notification fingerprint for one workspace."""
    path = _notification_state_path(cwd)
    with file_lock(path):
        previous = _load_last_notification(cwd)
        if previous.get("fingerprint") == fingerprint:
            return False
        atomic_write(path, json.dumps({"fingerprint": fingerprint}, indent=2))
        return True


def _execution_notification_message(cwd: str) -> tuple[str | None, str | None]:
    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(Path(cwd))
    if snapshot is None:
        return None, None

    phase_plan = "-".join(part for part in (snapshot.phase, snapshot.plan) if part) or "current work"
    artifact = snapshot.last_result_label or snapshot.last_artifact_path or snapshot.current_task or "latest result"
    segment_status = (snapshot.segment_status or "").strip().lower()

    if snapshot.blocked_reason:
        blocked_reason = humanize_execution_reason(snapshot.blocked_reason) or snapshot.blocked_reason
        return (
            f"[GPD] Blocked in {phase_plan}: {blocked_reason}\n",
            f"blocked:{snapshot.transition_id or snapshot.segment_id or snapshot.blocked_reason}",
        )
    if snapshot.first_result_gate_pending:
        return (
            f"[GPD] First-result review due for {phase_plan}: {artifact}\n",
            f"first-result:{snapshot.transition_id or snapshot.segment_id or artifact}",
        )
    if snapshot.skeptical_requestioning_required:
        focus = snapshot.weakest_unchecked_anchor or artifact
        gate = "pre-fanout" if snapshot.pre_fanout_review_pending else "skeptical"
        return (
            f"[GPD] Skeptical {gate} review due for {phase_plan}: {focus}\n",
            f"skeptical:{snapshot.transition_id or snapshot.segment_id or focus}",
        )
    if snapshot.pre_fanout_review_pending:
        return (
            f"[GPD] Pre-fanout review due for {phase_plan}: {artifact}\n",
            f"pre-fanout:{snapshot.transition_id or snapshot.segment_id or artifact}",
        )
    if snapshot.waiting_for_review:
        checkpoint = snapshot.checkpoint_reason or "checkpoint"
        return (
            f"[GPD] Review checkpoint due for {phase_plan}: {checkpoint}\n",
            f"review:{snapshot.transition_id or snapshot.segment_id or checkpoint}",
        )
    if snapshot.waiting_reason:
        waiting_reason = humanize_execution_reason(snapshot.waiting_reason) or snapshot.waiting_reason
        return (
            f"[GPD] Waiting in {phase_plan}: {waiting_reason}\n",
            f"wait:{snapshot.transition_id or snapshot.segment_id or snapshot.waiting_reason}",
        )
    if segment_status in _COMPLETED_SEGMENT_STATES:
        return None, None
    if snapshot.resume_file:
        resume_target = snapshot.resume_file
        return (
            f"[GPD] Resume candidate from live overlay for {phase_plan}: {resume_target}\n",
            f"resume:{snapshot.transition_id or snapshot.segment_id or resume_target}",
        )
    if segment_status in _PAUSED_SEGMENT_STATES:
        if segment_status == "awaiting_user":
            return (
                f"[GPD] Waiting for user in {phase_plan}: {artifact}\n",
                f"paused:{snapshot.transition_id or snapshot.segment_id or artifact}",
            )
        return (
            f"[GPD] Paused in {phase_plan}: {artifact}\n",
            f"paused:{snapshot.transition_id or snapshot.segment_id or artifact}",
        )
    return None, None


def _emit_execution_notification(cwd: str) -> None:
    message, fingerprint = _execution_notification_message(cwd)
    if not message or not fingerprint:
        return

    if not _claim_last_notification(cwd, fingerprint):
        return

    sys.stderr.write(message)


def main() -> None:
    """Entry point: read a JSON event from stdin and process notifications."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        _debug(f"notify stdin parse error: {exc}")
        return

    if not isinstance(data, dict):
        return

    try:
        roots = _resolve_payload_roots(data, policy_getter=_root_resolution_policy)
        workspace_dir = roots.workspace_dir
        project_root = roots.project_root
        hook_payload = _hook_payload_policy(project_root)
        allowed_event_types = hook_payload.notify_event_types
        if allowed_event_types and data.get("type") not in (*allowed_event_types, None):
            return
        _record_usage_telemetry(data, workspace_dir=workspace_dir, project_root=project_root)
        _trigger_update_check(project_root)
        _check_and_notify_update(project_root)
        _emit_execution_notification(project_root)
    except Exception as exc:
        _debug(f"notify handler failed: {exc}")


if __name__ == "__main__":
    main()
