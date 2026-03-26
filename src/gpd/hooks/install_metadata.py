"""Shared helpers for installed-hook metadata."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_install_repair_command


def _load_manifest_payload(config_dir: Path) -> dict[str, object] | None:
    """Return the parsed manifest payload when it is a mapping."""

    state, payload = load_install_manifest_state(config_dir)
    if state != "ok":
        return None
    return payload


def load_install_manifest_state(config_dir: Path) -> tuple[str, dict[str, object]]:
    """Return the manifest parse state and payload for *config_dir*.

    The state is one of ``missing``, ``corrupt``, ``invalid``, or ``ok``.
    ``ok`` means the manifest parsed as a mapping; the payload is the parsed
    dict in that case and ``{}`` otherwise.
    """

    manifest_path = config_dir / MANIFEST_NAME
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "missing", {}
    except (OSError, UnicodeDecodeError):
        return "corrupt", {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "corrupt", {}

    if not isinstance(payload, dict):
        return "invalid", {}
    return "ok", payload


def load_install_manifest_runtime_status(config_dir: Path) -> tuple[str, dict[str, object], str | None]:
    """Return the manifest parse state, payload, and canonical runtime when available."""

    state, payload = load_install_manifest_state(config_dir)
    if state != "ok":
        return state, payload, None

    if "runtime" not in payload:
        return "missing_runtime", payload, None

    runtime = payload.get("runtime")
    if not isinstance(runtime, str):
        return "malformed_runtime", payload, None

    normalized_runtime = runtime.strip()
    if not normalized_runtime:
        return "malformed_runtime", payload, None

    from gpd.hooks.runtime_detect import normalize_runtime_name

    canonical_runtime = normalize_runtime_name(normalized_runtime)
    if canonical_runtime is None:
        return "malformed_runtime", payload, None
    return "ok", payload, canonical_runtime


def install_scope_from_manifest(config_dir: Path) -> str | None:
    """Return the persisted install scope for *config_dir*."""

    manifest = _load_manifest_payload(config_dir)
    if manifest is None:
        return None

    scope = manifest.get("install_scope")
    return scope if scope in {"local", "global"} else None


def _manifest_runtime(config_dir: Path) -> str | None:
    """Return the authoritative runtime declared in *config_dir*'s manifest."""
    manifest_state, _payload, runtime = load_install_manifest_runtime_status(config_dir)
    return runtime if manifest_state == "ok" else None


def installed_runtime(config_dir: Path) -> str | None:
    """Return the authoritative runtime declared by *config_dir*'s manifest."""
    return _manifest_runtime(config_dir)


def config_dir_has_complete_install(config_dir: Path) -> bool:
    """Return whether *config_dir* is a complete install with authoritative runtime identity."""
    runtime = _manifest_runtime(config_dir)
    if runtime is not None:
        try:
            return get_adapter(runtime).has_complete_install(config_dir)
        except KeyError:
            return False
    return False


def installed_update_command(config_dir: Path) -> str | None:
    """Return the bootstrap update command for the install in *config_dir*."""

    manifest_state, manifest, runtime = load_install_manifest_runtime_status(config_dir)
    if manifest_state != "ok" or runtime is None:
        return None

    scope = manifest.get("install_scope")
    if scope not in {"local", "global"}:
        return None

    explicit_target = manifest.get("explicit_target")
    if not isinstance(explicit_target, bool):
        return None

    install_target = config_dir
    if explicit_target:
        install_target_value = manifest.get("install_target_dir")
        if not isinstance(install_target_value, str) or not install_target_value.strip():
            return None
        install_target = Path(install_target_value)

    try:
        get_adapter(runtime)
    except KeyError:
        return None

    return build_runtime_install_repair_command(
        runtime,
        install_scope=scope,
        target_dir=install_target,
        explicit_target=explicit_target,
    )
