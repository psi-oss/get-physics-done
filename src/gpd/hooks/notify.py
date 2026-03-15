#!/usr/bin/env python3
"""Runtime notification hook for GPD."""

import json
import os
import subprocess
import sys
from pathlib import Path

from gpd.core.constants import ENV_GPD_DEBUG
from gpd.hooks.install_metadata import install_scope_from_manifest, installed_update_command


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


def _hook_payload_policy(cwd: str | None = None):
    """Return hook payload metadata for the active runtime or a merged fallback."""
    from gpd.adapters.runtime_catalog import get_hook_payload_policy
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_active_runtime_with_gpd_install

    workspace_path = Path(cwd) if cwd else None
    runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    return get_hook_payload_policy(None if runtime == RUNTIME_UNKNOWN else runtime)


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


def _latest_update_cache(cwd: str | None = None) -> tuple[dict[str, object] | None, object | None]:
    """Return the highest-priority valid update cache and its candidate metadata."""
    from types import SimpleNamespace

    from gpd.hooks.runtime_detect import (
        detect_active_runtime_with_gpd_install,
        get_update_cache_candidates,
        should_consider_update_cache_candidate,
    )

    workspace_path = Path(cwd) if cwd else None
    active_installed_runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    self_config_dir = _self_config_dir()
    if self_config_dir is not None:
        cache_file = self_config_dir / "cache" / "gpd-update-check.json"
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception as exc:
                _debug(f"Failed to parse cache {cache_file}: {exc}")
            else:
                if isinstance(cache, dict):
                    candidate = SimpleNamespace(
                        path=cache_file,
                        runtime=None,
                        scope=_self_install_scope(self_config_dir),
                        config_dir=self_config_dir,
                    )
                    return cache, candidate

    for candidate in get_update_cache_candidates(cwd=workspace_path, preferred_runtime=active_installed_runtime):
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
        return cache, candidate

    return None, None


def _check_and_notify_update(cwd: str | None = None) -> None:
    """Read update cache and emit a notification to stderr if update available."""
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_active_runtime_with_gpd_install,
        detect_install_scope,
        update_command_for_runtime,
    )

    workspace_path = Path(cwd) if cwd else None
    latest_cache, latest_candidate = _latest_update_cache(cwd)

    if latest_cache and latest_cache.get("update_available"):
        installed = latest_cache.get("installed", "?")
        latest = latest_cache.get("latest", "?")
        config_dir = getattr(latest_candidate, "config_dir", None)
        if isinstance(config_dir, Path):
            cmd = _self_update_command(config_dir) or "npx -y get-physics-done"
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
    if isinstance(workspace_value, str) and workspace_value:
        return workspace_value
    return (
        _first_string(workspace_value, *policy.workspace_keys)
        or _first_string(data, *policy.workspace_keys)
        or cwd
        or os.getcwd()
    )


def _notification_state_path(cwd: str) -> Path:
    return Path(cwd) / ".gpd" / "observability" / "last-notify.json"


def _load_last_notification(cwd: str) -> dict[str, object]:
    path = _notification_state_path(cwd)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_last_notification(cwd: str, payload: dict[str, object]) -> None:
    path = _notification_state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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

    previous = _load_last_notification(cwd)
    if previous.get("fingerprint") == fingerprint:
        return

    sys.stderr.write(message)
    _save_last_notification(cwd, {"fingerprint": fingerprint})


def main() -> None:
    """Entry point: read a JSON event from stdin and process notifications."""
    try:
        data = json.loads(sys.stdin.read())
    except Exception as exc:
        _debug(f"notify stdin parse error: {exc}")
        return

    if not isinstance(data, dict):
        return

    cwd = _workspace_from_payload(data)
    hook_payload = _hook_payload_policy(cwd)
    allowed_event_types = hook_payload.notify_event_types
    if allowed_event_types and data.get("type") not in (*allowed_event_types, None):
        return

    try:
        _trigger_update_check(cwd)
        _check_and_notify_update(cwd)
        _emit_execution_notification(cwd)
    except Exception as exc:
        _debug(f"notify handler failed: {exc}")


if __name__ == "__main__":
    main()
