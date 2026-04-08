#!/usr/bin/env python3
"""Runtime notification hook for GPD."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from gpd.adapters.runtime_catalog import get_hook_payload_policy
from gpd.core.constants import (
    ENV_GPD_DEBUG,
    HOME_DATA_DIR_NAME,
    OBSERVABILITY_DIR_NAME,
    OBSERVABILITY_LAST_NOTIFY_FILENAME,
    ProjectLayout,
)
from gpd.core.observability import humanize_execution_reason
from gpd.core.root_resolution import resolve_project_root
from gpd.core.utils import atomic_write, file_lock
from gpd.hooks.install_context import detect_self_owned_install
from gpd.hooks.payload_policy import resolve_hook_payload_policy, resolve_hook_surface_runtime
from gpd.hooks.payload_roots import payload_uses_alias_only_workspace_mapping
from gpd.hooks.payload_roots import resolve_payload_roots as _resolve_payload_roots
from gpd.hooks.runtime_lookup import resolve_runtime_lookup_context_from_payload_roots
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


def _has_project_layout(cwd: str) -> bool:
    resolved_root = resolve_project_root(cwd, require_layout=True)
    return resolved_root is not None


def _workspace_mapping_prefers_local_notify_lookup(
    data: dict[str, object],
    *,
    hook_payload: object,
) -> bool:
    """Keep notify lookup anchored to the workspace when only non-primary aliases were populated."""
    return payload_uses_alias_only_workspace_mapping(data, hook_payload=hook_payload)


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
    except KeyError:
        return False
    return capability.telemetry_source == "notify-hook" and capability.telemetry_completeness != "none"


def _record_usage_telemetry(
    data: dict[str, object],
    *,
    workspace_dir: str,
    project_root: str,
    active_runtime: str | None = None,
) -> None:
    """Persist measured usage/cost telemetry when the runtime payload exposes it."""
    from gpd.core.costs import record_usage_from_runtime_payload

    try:
        runtime = active_runtime or _payload_runtime(workspace_dir)
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
        fingerprint = _update_notification_fingerprint(latest_cache, cmd)
        claimed = _claim_last_notification(cwd or str(Path.cwd()), channel="update", fingerprint=fingerprint)
        if claimed is False:
            return
        installed = latest_cache.get("installed", "?")
        latest = latest_cache.get("latest", "?")
        sys.stderr.write(f"[GPD] Update available: v{installed} -> v{latest}. Run: {cmd}\n")


def _notification_state_path(cwd: str) -> Path:
    workspace_root = resolve_project_root(cwd, require_layout=True)
    if workspace_root is not None:
        return ProjectLayout(workspace_root).last_observability_notification
    self_install = detect_self_owned_install(__file__)
    if self_install is not None:
        return self_install.config_dir / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME
    return Path.home() / HOME_DATA_DIR_NAME / OBSERVABILITY_DIR_NAME / OBSERVABILITY_LAST_NOTIFY_FILENAME


def _load_last_notification(cwd: str) -> dict[str, object]:
    path = _notification_state_path(cwd)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _channel_scoped_fingerprint(cwd: str, *, channel: str, fingerprint: str) -> str:
    """Avoid cross-workspace dedupe collisions when execution falls back to home state."""
    if channel != "execution":
        return fingerprint
    if resolve_project_root(cwd, require_layout=True) is not None:
        return fingerprint
    return f"{Path(cwd).expanduser().resolve(strict=False).as_posix()}::{fingerprint}"


def _claim_last_notification(cwd: str, *, channel: str, fingerprint: str) -> bool | None:
    """Atomically claim a notification fingerprint for one channel in one workspace."""
    path = _notification_state_path(cwd)
    channel_key = f"{channel}_fingerprint"
    scoped_fingerprint = _channel_scoped_fingerprint(cwd, channel=channel, fingerprint=fingerprint)
    try:
        with file_lock(path):
            previous = _load_last_notification(cwd)
            if previous.get(channel_key) == scoped_fingerprint or previous.get("fingerprint") == scoped_fingerprint:
                return False
            previous[channel_key] = scoped_fingerprint
            previous.pop("fingerprint", None)
            atomic_write(path, json.dumps(previous, indent=2))
            return True
    except OSError as exc:
        _debug(f"notification dedupe skipped for {path}: {exc}")
        return None


def _update_notification_fingerprint(latest_cache: dict[str, object], cmd: str) -> str:
    """Return the dedupe fingerprint for one update notice payload."""
    installed = str(latest_cache.get("installed", "?")).strip() or "?"
    latest = str(latest_cache.get("latest", "?")).strip() or "?"
    return f"update:{installed}:{latest}:{cmd}"


def _execution_claim_fingerprint(cwd: str, fingerprint: str) -> str:
    """Scope execution dedupe to one workspace when no project layout is available."""
    if _has_project_layout(cwd):
        return fingerprint
    normalized_cwd = str(Path(cwd).expanduser().resolve(strict=False))
    workspace_hash = hashlib.sha256(normalized_cwd.encode("utf-8")).hexdigest()[:16]
    return f"{fingerprint}:workspace:{workspace_hash}"


def _execution_notification_message(cwd: str) -> tuple[str | None, str | None]:
    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(Path(cwd))
    if snapshot is None:
        return None, None

    phase_plan = "-".join(part for part in (snapshot.phase, snapshot.plan) if part) or "current work"
    artifact = snapshot.last_result_label or snapshot.last_artifact_path or snapshot.current_task or "latest result"
    if artifact == "latest result":
        last_result_id = snapshot.last_result_id
        if isinstance(last_result_id, str) and last_result_id.strip():
            artifact = f"rerun anchor: {last_result_id.strip()}"
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

    claim_fingerprint = _execution_claim_fingerprint(cwd, fingerprint)
    claimed = _claim_last_notification(cwd, channel="execution", fingerprint=claim_fingerprint)
    if claimed is False:
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
        project_dir_present = roots.project_dir_present
        project_dir_trusted = roots.project_dir_trusted
        payload_policy = _hook_payload_policy(workspace_dir)
        if project_dir_trusted is True and _workspace_mapping_prefers_local_notify_lookup(
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
        allowed_event_types = hook_payload.notify_event_types
        event_type = data.get("type")
        if allowed_event_types and event_type not in allowed_event_types:
            return
        _record_usage_telemetry(
            data,
            workspace_dir=workspace_dir,
            project_root=project_root,
            active_runtime=runtime_lookup.active_runtime,
        )
        _trigger_update_check(runtime_lookup_dir)
        _check_and_notify_update(runtime_lookup_dir)
        _emit_execution_notification(runtime_lookup_dir)
    except Exception as exc:
        _debug(f"notify handler failed: {exc}")


if __name__ == "__main__":
    main()
