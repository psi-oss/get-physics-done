"""Shared helpers for installed-hook metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import gpd.adapters.install_utils as install_utils
from gpd.adapters.runtime_catalog import (
    get_managed_install_surface_policy,
    get_shared_install_metadata,
    list_runtime_names,
)

_SHARED_INSTALL_METADATA = get_shared_install_metadata()
GPD_INSTALL_DIR_NAME = _SHARED_INSTALL_METADATA.install_root_dir_name
MANIFEST_NAME = _SHARED_INSTALL_METADATA.manifest_name


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

    return normalized if normalized in list_runtime_names() else None


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

    @property
    def readiness_state(self) -> str:
        """Return the coarse readiness state derived from the install assessment."""
        return "ready" if self.state in {"absent", "clean", "owned_complete"} else "blocked"

    def readiness_message(self, runtime: str | None = None) -> str:
        """Return a human-readable summary for the current install assessment."""
        if self.state == "owned_incomplete":
            missing = ", ".join(f"`{item}`" for item in self.missing_install_artifacts) or "required install artifacts"
            return f"{self.config_dir} has an incomplete GPD install; missing artifacts: {missing}."
        if self.state == "foreign_runtime":
            owner = f"`{self.manifest_runtime}`" if self.manifest_runtime else "another runtime"
            runtime_label = f"`{runtime}`" if runtime else "the selected runtime"
            return f"{self.config_dir} belongs to {owner}, not {runtime_label}."
        if self.state == "untrusted_manifest":
            return f"{self.config_dir} has an untrusted GPD manifest and cannot be treated as a ready install target."
        if self.state == "owned_complete":
            owner = f"`{self.manifest_runtime}`" if self.manifest_runtime else "the selected runtime"
            return f"{self.config_dir} already contains a complete GPD install for {owner}."
        if self.state == "clean":
            return f"{self.config_dir} is ready for a new GPD install."
        return f"{self.config_dir} is ready for installation."


@dataclass(frozen=True, slots=True)
class ManagedInstallSurface:
    """Observed managed install surfaces under a runtime config directory."""

    has_gpd_content: bool
    has_nested_commands: bool
    has_flat_commands: bool
    has_managed_agents: bool

    @property
    def has_managed_markers(self) -> bool:
        return any(
            (
                self.has_gpd_content,
                self.has_nested_commands,
                self.has_flat_commands,
                self.has_managed_agents,
            )
        )


def _glob_contains_files(config_dir: Path, patterns: tuple[str, ...]) -> bool:
    """Return whether any configured managed-surface glob materializes files."""

    for pattern in patterns:
        for match in config_dir.glob(pattern):
            if match.is_file():
                return True
            if match.is_dir() and install_utils._dir_contains_files(match):
                return True
    return False


def inspect_managed_install_surface(config_dir: Path) -> ManagedInstallSurface:
    """Return the managed install surfaces currently materialized in *config_dir*."""
    policy = get_managed_install_surface_policy()

    return ManagedInstallSurface(
        has_gpd_content=_glob_contains_files(config_dir, policy.gpd_content_globs),
        has_nested_commands=_glob_contains_files(config_dir, policy.nested_command_globs),
        has_flat_commands=_glob_contains_files(config_dir, policy.flat_command_globs),
        has_managed_agents=_glob_contains_files(config_dir, policy.managed_agent_globs),
    )


def config_dir_has_managed_install_markers(config_dir: Path) -> bool:
    """Return whether *config_dir* carries any managed GPD install markers."""
    return inspect_managed_install_surface(config_dir).has_managed_markers


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


def load_install_manifest_scope_status(config_dir: Path) -> tuple[str, dict[str, object], str | None]:
    """Return the manifest parse state, payload, and canonical install scope when available."""

    state, payload = load_install_manifest_state(config_dir)
    if state != "ok":
        return state, payload, None

    if "install_scope" not in payload:
        return "missing_install_scope", payload, None

    scope = payload.get("install_scope")
    if not isinstance(scope, str):
        return "malformed_install_scope", payload, None

    normalized_scope = scope.strip()
    if normalized_scope not in {"local", "global"}:
        return "malformed_install_scope", payload, None
    return "ok", payload, normalized_scope


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

    state, _payload, scope = load_install_manifest_scope_status(config_dir)
    return scope if state == "ok" else None


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

    try:
        get_adapter(runtime)
    except KeyError:
        return None

    explicit_target = manifest.get("explicit_target")
    if not isinstance(explicit_target, bool):
        # Fail closed for legacy manifests that do not prove whether the
        # install was explicitly targeted. Update-command synthesis is only
        # trusted when the manifest carries the authoritative flag.
        return None

    return build_runtime_install_repair_command(
        runtime,
        install_scope=scope,
        target_dir=config_dir,
        explicit_target=explicit_target,
    )
