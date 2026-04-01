"""Shared helpers for installed-hook metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

AGENTS_DIR_NAME = "agents"
COMMANDS_DIR_NAME = "commands"
FLAT_COMMANDS_DIR_NAME = "command"
GPD_INSTALL_DIR_NAME = "get-physics-done"
MANIFEST_NAME = "gpd-file-manifest.json"


def get_adapter(runtime: str):
    """Lazily resolve the runtime adapter to keep manifest parsing lightweight."""
    return import_module("gpd.adapters").get_adapter(runtime)


def build_runtime_install_repair_command(
    runtime: str,
    *,
    install_scope: str | None,
    target_dir: Path,
    explicit_target: bool = False,
) -> str:
    """Lazily resolve the public repair-command helper."""
    install_utils = import_module("gpd.adapters.install_utils")
    return install_utils.build_runtime_install_repair_command(
        runtime,
        install_scope=install_scope,
        target_dir=target_dir,
        explicit_target=explicit_target,
    )


def _canonical_manifest_runtime_name(value: str) -> str | None:
    """Return the exact canonical runtime id stored in trusted install manifests."""

    normalized = value.strip()
    if not normalized:
        return None

    runtime_catalog = import_module("gpd.adapters.runtime_catalog")
    for descriptor in runtime_catalog.iter_runtime_descriptors():
        if normalized == descriptor.runtime_name:
            return descriptor.runtime_name
    return None


@dataclass(frozen=True, slots=True)
class InstallTargetAssessment:
    """Shared classification of a runtime config dir's GPD install state."""

    config_dir: Path
    expected_runtime: str | None
    state: str
    manifest_state: str
    manifest_runtime: str | None
    has_managed_markers: bool
    missing_install_artifacts: tuple[str, ...] = ()


def _load_manifest_payload(config_dir: Path) -> dict[str, object] | None:
    """Return the parsed manifest payload when it is a mapping."""

    state, payload = load_install_manifest_state(config_dir)
    if state != "ok":
        return None
    return payload


def config_dir_has_managed_install_markers(config_dir: Path) -> bool:
    """Return whether *config_dir* carries any managed GPD install markers."""
    if any(
        (
            (config_dir / GPD_INSTALL_DIR_NAME).exists(),
            (config_dir / COMMANDS_DIR_NAME / "gpd").exists(),
            (config_dir / FLAT_COMMANDS_DIR_NAME).exists(),
        )
    ):
        return True

    agents_dir = config_dir / AGENTS_DIR_NAME
    if not agents_dir.is_dir():
        return False

    return any(
        entry.is_file() and entry.name.startswith("gpd-") and entry.suffix in {".md", ".toml"}
        for entry in agents_dir.iterdir()
    )


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

    canonical_runtime = _canonical_manifest_runtime_name(normalized_runtime)
    if canonical_runtime is None:
        return "malformed_runtime", payload, None
    return "ok", payload, canonical_runtime


def assess_install_target(
    config_dir: Path,
    *,
    expected_runtime: str | None = None,
) -> InstallTargetAssessment:
    """Classify the GPD install state for *config_dir*.

    States:
    - ``absent``: target path does not exist and has no managed markers
    - ``clean``: target path exists but contains no managed GPD surface
    - ``owned_complete``: valid manifest for the owning runtime and complete install
    - ``owned_incomplete``: valid manifest for the owning runtime but missing install artifacts
    - ``foreign_runtime``: valid manifest, but ownership belongs to another runtime
    - ``untrusted_manifest``: manifest missing/corrupt/malformed on a managed surface
    """

    resolved = config_dir.expanduser().resolve(strict=False)
    manifest_state, _payload, manifest_runtime = load_install_manifest_runtime_status(resolved)
    has_managed_markers = config_dir_has_managed_install_markers(resolved)
    missing_install_artifacts: tuple[str, ...] = ()

    if manifest_state == "ok" and manifest_runtime is not None:
        if expected_runtime is not None and manifest_runtime != expected_runtime:
            return InstallTargetAssessment(
                config_dir=resolved,
                expected_runtime=expected_runtime,
                state="foreign_runtime",
                manifest_state=manifest_state,
                manifest_runtime=manifest_runtime,
                has_managed_markers=True,
            )
        try:
            adapter = get_adapter(manifest_runtime)
        except KeyError:
            state = "untrusted_manifest"
        else:
            missing_install_artifacts = adapter.missing_install_artifacts(resolved)
            state = "owned_complete" if not missing_install_artifacts else "owned_incomplete"
        return InstallTargetAssessment(
            config_dir=resolved,
            expected_runtime=expected_runtime,
            state=state,
            manifest_state=manifest_state,
            manifest_runtime=manifest_runtime,
            has_managed_markers=True,
            missing_install_artifacts=missing_install_artifacts,
        )

    if manifest_state == "missing" and not has_managed_markers:
        state = "absent" if not resolved.exists() else "clean"
    else:
        state = "untrusted_manifest"

    return InstallTargetAssessment(
        config_dir=resolved,
        expected_runtime=expected_runtime,
        state=state,
        manifest_state=manifest_state,
        manifest_runtime=manifest_runtime,
        has_managed_markers=has_managed_markers,
    )


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
    return assess_install_target(config_dir).state == "owned_complete"


def installed_update_command(config_dir: Path) -> str | None:
    """Return the bootstrap update command for the install in *config_dir*."""

    manifest_state, manifest, runtime = load_install_manifest_runtime_status(config_dir)
    if manifest_state != "ok" or runtime is None:
        return None

    scope = manifest.get("install_scope")
    if scope not in {"local", "global"}:
        return None

    explicit_target = manifest.get("explicit_target")
    if explicit_target is None:
        if scope == "global":
            return None
        install_target_dir = manifest.get("install_target_dir")
        explicit_target = isinstance(install_target_dir, str) and bool(install_target_dir.strip())
    elif not isinstance(explicit_target, bool):
        return None

    try:
        get_adapter(runtime)
    except KeyError:
        return None

    return build_runtime_install_repair_command(
        runtime,
        install_scope=scope,
        # The live config dir is the authoritative install location for self-owned hooks.
        # Using it keeps update guidance stable even when target metadata drifts.
        target_dir=config_dir,
        explicit_target=explicit_target,
    )
