#!/usr/bin/env python3
"""Runtime notification hook for GPD."""

import json
import os
import subprocess
import sys
from pathlib import Path

import gpd.hooks.install_context as hook_layout
from gpd.core.constants import ENV_GPD_DEBUG, ProjectLayout
from gpd.core.observability import resolve_project_root
from gpd.core.utils import atomic_write, file_lock


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


def _normalize_workspace_text(value: str | None) -> str:
    if not value:
        return str(Path.cwd().resolve(strict=False))
    path = Path(value).expanduser()
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path)


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
    from gpd.adapters.runtime_catalog import get_hook_payload_policy
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_active_runtime_with_gpd_install

    self_install = hook_layout.detect_self_owned_install(__file__)
    if self_install is not None:
        return get_hook_payload_policy(self_install.runtime)

    workspace_path = resolve_project_root(cwd) if cwd else None
    runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    return get_hook_payload_policy(None if runtime == RUNTIME_UNKNOWN else runtime)


def _payload_runtime(cwd: str | None = None) -> str | None:
    """Return the active installed runtime for one payload workspace, when known."""
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_active_runtime_with_gpd_install

    self_install = hook_layout.detect_self_owned_install(__file__)
    if self_install is not None:
        return self_install.runtime

    workspace_path = resolve_project_root(cwd) if cwd else None
    runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    return None if runtime == RUNTIME_UNKNOWN else runtime


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


def _record_usage_telemetry(data: dict[str, object], *, cwd: str) -> None:
    """Persist measured usage/cost telemetry when the runtime payload exposes it."""
    from gpd.core.costs import record_usage_from_runtime_payload

    try:
        runtime = _payload_runtime(cwd)
        if not _runtime_supports_usage_telemetry(runtime):
            _debug("usage telemetry skipped: runtime capability unknown or unsupported")
            return
        record_usage_from_runtime_payload(data, runtime=runtime, cwd=Path(cwd))
    except Exception as exc:
        # Usage telemetry is advisory only and must never break the notify hook.
        _debug(f"usage telemetry skipped: {exc}")


def _latest_update_cache(cwd: str | None = None) -> tuple[dict[str, object] | None, object | None]:
    """Return the highest-priority valid update cache and its candidate metadata."""
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_active_runtime_with_gpd_install,
        detect_runtime_install_target,
        get_update_cache_candidates,
        should_consider_update_cache_candidate,
    )

    workspace_path = resolve_project_root(cwd) if cwd else None
    active_installed_runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    self_install = hook_layout.detect_self_owned_install(__file__)
    active_install_target = (
        detect_runtime_install_target(active_installed_runtime, cwd=workspace_path)
        if active_installed_runtime not in (None, "", RUNTIME_UNKNOWN)
        else None
    )
    if hook_layout.should_prefer_self_owned_install(
        self_install,
        active_install_target=active_install_target,
        workspace_path=workspace_path,
    ):
        cache_file = self_install.cache_file
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception as exc:
                _debug(f"Failed to parse cache {cache_file}: {exc}")
            else:
                if isinstance(cache, dict):
                    candidate = hook_layout.self_owned_update_cache_candidate(self_install)
                    return cache, candidate

    preferred_runtime = active_installed_runtime if workspace_path is not None else None
    fallback_hit: tuple[dict[str, object], object] | None = None
    for candidate in get_update_cache_candidates(cwd=workspace_path, preferred_runtime=preferred_runtime):
        if not should_consider_update_cache_candidate(
            candidate,
            active_installed_runtime=active_installed_runtime,
            cwd=workspace_path,
        ):
            continue
        cache_file = candidate.path
        if not cache_file.exists():
            continue
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception as exc:
            _debug(f"Failed to parse cache {cache_file}: {exc}")
            continue

        if not isinstance(cache, dict):
            continue
        if getattr(candidate, "runtime", None):
            return cache, candidate
        if fallback_hit is None:
            fallback_hit = (cache, candidate)

    return fallback_hit if fallback_hit is not None else (None, None)


def _check_and_notify_update(cwd: str | None = None) -> None:
    """Read update cache and emit a notification to stderr if update available."""
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_active_runtime_with_gpd_install,
        detect_install_scope,
        update_command_for_runtime,
    )

    workspace_path = resolve_project_root(cwd) if cwd else None
    latest_cache, latest_candidate = _latest_update_cache(cwd)
    self_install = hook_layout.detect_self_owned_install(__file__)

    if latest_cache and latest_cache.get("update_available"):
        installed = latest_cache.get("installed", "?")
        latest = latest_cache.get("latest", "?")
        if self_install is not None and latest_candidate is not None and latest_candidate.path == self_install.cache_file:
            cmd = self_install.update_command
            if cmd is None:
                return
            sys.stderr.write(f"[GPD] Update available: v{installed} \u2192 v{latest}. Run: {cmd}\n")
            return
        runtime = latest_candidate.runtime if latest_candidate is not None else RUNTIME_UNKNOWN
        scope = getattr(latest_candidate, "scope", None)
        if runtime not in (None, RUNTIME_UNKNOWN):
            installed_scope = detect_install_scope(runtime, cwd=workspace_path)
            if installed_scope is None:
                runtime = RUNTIME_UNKNOWN
                scope = None
            else:
                scope = installed_scope
        if runtime == RUNTIME_UNKNOWN or runtime is None:
            runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
        if scope is None and runtime != RUNTIME_UNKNOWN:
            scope = detect_install_scope(runtime, cwd=workspace_path)
        cmd = update_command_for_runtime(runtime, scope=scope)
        sys.stderr.write(f"[GPD] Update available: v{installed} \u2192 v{latest}. Run: {cmd}\n")


def _workspace_from_payload(data: dict[str, object], *, cwd: str | None = None) -> str:
    from gpd.adapters.runtime_catalog import get_hook_payload_policy

    # Before the payload workspace is resolved, accept the union of known
    # workspace keys so event filtering can defer to the runtime that owns
    # the payload's actual workspace instead of the process cwd.
    policy = _hook_payload_policy(cwd) if cwd else get_hook_payload_policy()
    workspace_value = data.get("workspace")
    raw_workspace = (
        workspace_value
        if isinstance(workspace_value, str) and workspace_value
        else (
        _first_string(workspace_value, *policy.workspace_keys)
        or _first_string(data, *policy.workspace_keys)
        or cwd
        or os.getcwd()
        )
    )
    project_dir = _first_string(workspace_value, *policy.project_dir_keys) or _first_string(
        data,
        *policy.project_dir_keys,
    )
    resolved_root = resolve_project_root(raw_workspace, project_dir=project_dir)
    return str(resolved_root) if resolved_root is not None else _normalize_workspace_text(raw_workspace)


def _notification_state_path(cwd: str) -> Path:
    workspace_root = resolve_project_root(cwd) or Path(cwd).expanduser().resolve(strict=False)
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

    if snapshot.blocked_reason:
        return (
            f"[GPD] Blocked in {phase_plan}: {snapshot.blocked_reason}\n",
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
        return (
            f"[GPD] Waiting in {phase_plan}: {snapshot.waiting_reason}\n",
            f"wait:{snapshot.transition_id or snapshot.segment_id or snapshot.waiting_reason}",
        )
    if snapshot.segment_status in {"paused", "ready_to_continue"}:
        resume_target = snapshot.resume_file or artifact
        return (
            f"[GPD] Resume ready for {phase_plan}: {resume_target}\n",
            f"resume:{snapshot.transition_id or snapshot.segment_id or resume_target}",
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
        cwd = _workspace_from_payload(data)
        hook_payload = _hook_payload_policy(cwd)
        allowed_event_types = hook_payload.notify_event_types
        if allowed_event_types and data.get("type") not in (*allowed_event_types, None):
            return
        _record_usage_telemetry(data, cwd=cwd)
        _trigger_update_check(cwd)
        _check_and_notify_update(cwd)
        _emit_execution_notification(cwd)
    except Exception as exc:
        _debug(f"notify handler failed: {exc}")


if __name__ == "__main__":
    main()
