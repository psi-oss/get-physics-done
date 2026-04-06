#!/usr/bin/env python3
"""Install health check hook — detects and repairs broken GPD installs on session start.

GPD can disappear after Claude Code credit exhaustion, an update, or an
environment restart. This hook runs on SessionStart alongside the update
check hook and:

1. Verifies the install manifest and key artifacts exist.
2. When artifacts are missing but the manifest is intact, attempts an
   automatic self-repair by re-running the installer.
3. Emits a diagnostic message to stderr when repair fails so the user
   knows how to recover manually.

The hook is intentionally lightweight: it imports lazily, never blocks on
network I/O, and exits quickly when the install is healthy.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from gpd.adapters.install_utils import (
    CACHE_DIR_NAME,
    MANIFEST_NAME,
)
from gpd.core.constants import ENV_GPD_DEBUG

# Cooldown: do not attempt repair more than once per 5 minutes.
_REPAIR_COOLDOWN_SECONDS = 300
_REPAIR_STATE_FILENAME = "gpd-install-doctor.json"


def _debug(msg: str) -> None:
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-doctor] {msg}\n")


def _self_config_dir() -> Path | None:
    """Return the installed runtime config dir when this hook runs from one."""
    from gpd.hooks.install_context import detect_self_owned_install

    self_install = detect_self_owned_install(__file__)
    return None if self_install is None else self_install.config_dir


def _repair_state_path(config_dir: Path) -> Path:
    """Return the path to the repair state file."""
    return config_dir / CACHE_DIR_NAME / _REPAIR_STATE_FILENAME


def _load_repair_state(config_dir: Path) -> dict[str, object]:
    """Load the repair state from cache."""
    state_path = _repair_state_path(config_dir)
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _save_repair_state(config_dir: Path, state: dict[str, object]) -> None:
    """Save the repair state to cache."""
    state_path = _repair_state_path(config_dir)
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:
        _debug(f"Failed to write repair state: {exc}")


def _is_repair_on_cooldown(config_dir: Path) -> bool:
    """Return True if a recent repair attempt should suppress another."""
    state = _load_repair_state(config_dir)
    last_attempt = state.get("last_repair_attempt")
    if not isinstance(last_attempt, (int, float)):
        return False
    age = int(time.time()) - int(last_attempt)
    return 0 <= age < _REPAIR_COOLDOWN_SECONDS


def _record_repair_attempt(config_dir: Path, *, success: bool, missing: list[str]) -> None:
    """Record that a repair attempt was made."""
    state = _load_repair_state(config_dir)
    state["last_repair_attempt"] = int(time.time())
    state["last_repair_success"] = success
    state["last_repair_missing"] = missing
    repair_count = state.get("repair_count", 0)
    if isinstance(repair_count, int):
        state["repair_count"] = repair_count + 1
    else:
        state["repair_count"] = 1
    _save_repair_state(config_dir, state)


def _check_install_integrity(config_dir: Path) -> tuple[bool, list[str]]:
    """Check whether the install at config_dir has all required artifacts.

    Returns (is_healthy, missing_artifacts).
    """
    from gpd.hooks.install_metadata import load_install_manifest_runtime_status

    manifest_state, _manifest, runtime = load_install_manifest_runtime_status(config_dir)
    missing: list[str] = []

    if manifest_state != "ok":
        missing.append(MANIFEST_NAME)
        return False, missing

    if runtime is None:
        missing.append(f"{MANIFEST_NAME} (no runtime)")
        return False, missing

    try:
        from gpd.adapters import get_adapter

        adapter = get_adapter(runtime)
    except KeyError:
        missing.append(f"adapter:{runtime}")
        return False, missing

    missing_artifacts = adapter.missing_install_artifacts(config_dir)
    if missing_artifacts:
        missing.extend(missing_artifacts)

    # Also check for commands directory specifically since that is what
    # surfaces the /gpd slash commands in Claude Code.
    commands_dir = config_dir / "commands" / "gpd"
    if not commands_dir.is_dir():
        if "commands/gpd" not in missing:
            missing.append("commands/gpd (missing)")
    elif not any(commands_dir.iterdir()):
        if "commands/gpd" not in missing:
            missing.append("commands/gpd (empty)")

    return len(missing) == 0, missing


def _get_repair_command(config_dir: Path) -> str | None:
    """Return the npx reinstall command for the install at config_dir."""
    from gpd.hooks.install_metadata import installed_update_command

    return installed_update_command(config_dir)


def _find_gpd_root() -> Path | None:
    """Locate the GPD package data root (commands/, agents/, specs/, hooks/).

    Tries the installed package location first, then falls back to a source
    checkout.
    """
    # Strategy 1: Walk up from the hooks module to find the package root.
    try:
        import gpd

        gpd_package_dir = Path(gpd.__file__).resolve().parent
        # The package root typically lives at gpd_package_dir.parent.parent
        # (src/gpd/ -> src/ -> root/)
        candidate = gpd_package_dir.parent.parent
        if (candidate / "commands").is_dir() and (candidate / "specs").is_dir():
            return candidate
    except Exception:
        pass

    # Strategy 2: Look for GPD_HOME.
    gpd_home = os.environ.get("GPD_HOME", "").strip()
    if gpd_home:
        candidate = Path(gpd_home).expanduser()
        if (candidate / "commands").is_dir():
            return candidate

    # Strategy 3: Look relative to this script for a source checkout.
    this_file = Path(__file__).resolve()
    # hooks/install_doctor.py -> hooks/ -> gpd/ -> src/ -> repo root
    repo_root = this_file.parent.parent.parent.parent
    if (repo_root / "commands").is_dir() and (repo_root / "specs").is_dir():
        return repo_root

    return None


def _attempt_self_repair(config_dir: Path) -> bool:
    """Attempt to repair the install by re-running the installer.

    Returns True if repair succeeded.
    """
    from gpd.hooks.install_metadata import load_install_manifest_runtime_status

    manifest_state, manifest, runtime = load_install_manifest_runtime_status(config_dir)
    if manifest_state != "ok" or runtime is None:
        _debug("Cannot self-repair: manifest missing or corrupt")
        return False

    install_scope = manifest.get("install_scope")
    if install_scope not in {"local", "global"}:
        _debug(f"Cannot self-repair: unknown install_scope={install_scope}")
        return False

    try:
        from gpd.adapters import get_adapter

        adapter = get_adapter(runtime)
    except KeyError:
        _debug(f"Cannot self-repair: unknown runtime {runtime}")
        return False

    gpd_root = _find_gpd_root()
    if gpd_root is None:
        _debug("Cannot self-repair: unable to locate GPD package root")
        return False

    is_global = install_scope == "global"
    explicit_target = manifest.get("explicit_target", False)
    if not isinstance(explicit_target, bool):
        explicit_target = False

    _debug(f"Attempting self-repair: runtime={runtime}, scope={install_scope}, target={config_dir}")
    try:
        result = adapter.install(
            gpd_root,
            config_dir,
            is_global=is_global,
            explicit_target=explicit_target,
        )
        # Finalize the install (writes settings.json, statusline, etc.)
        adapter.finalize_install(result, force_statusline=False)
        _debug(f"Self-repair succeeded: {result.get('commands', 0)} commands, {result.get('agents', 0)} agents")
        return True
    except Exception as exc:
        _debug(f"Self-repair failed: {exc}")
        return False


def main(argv: list[str] | None = None) -> None:
    """Entry point: check install health and attempt repair if needed."""
    config_dir = _self_config_dir()
    if config_dir is None:
        _debug("Not running from an installed config dir; skipping health check")
        return

    is_healthy, missing = _check_install_integrity(config_dir)
    if is_healthy:
        _debug("Install is healthy")
        return

    _debug(f"Install integrity check failed, missing: {missing}")

    # Check cooldown to avoid repair loops.
    if _is_repair_on_cooldown(config_dir):
        _debug("Repair on cooldown; skipping auto-repair")
        repair_command = _get_repair_command(config_dir)
        if repair_command:
            sys.stderr.write(
                f"[GPD] Install appears damaged (missing: {', '.join(missing)}). "
                f"Run `{repair_command}` to repair.\n"
            )
        return

    # Attempt self-repair.
    success = _attempt_self_repair(config_dir)
    _record_repair_attempt(config_dir, success=success, missing=missing)

    if success:
        sys.stderr.write("[GPD] Auto-repaired install after detecting missing artifacts.\n")
        return

    # Repair failed — emit guidance.
    repair_command = _get_repair_command(config_dir)
    if repair_command:
        sys.stderr.write(
            f"[GPD] Install appears damaged (missing: {', '.join(missing)}). "
            f"Auto-repair failed. Run `{repair_command}` to repair manually.\n"
        )
    else:
        sys.stderr.write(
            f"[GPD] Install appears damaged (missing: {', '.join(missing)}). "
            "Run `npx -y get-physics-done` to reinstall.\n"
        )


if __name__ == "__main__":
    main()
