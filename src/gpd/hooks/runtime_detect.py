"""Runtime detection for GPD hooks.

Adapter metadata is the source of truth for runtime names, command syntax,
env-var activation signals, and config-directory layout.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.install_utils import (
    CACHE_DIR_NAME,
    GPD_INSTALL_DIR_NAME,
    MANIFEST_NAME,
    UPDATE_CACHE_FILENAME,
)
from gpd.adapters.runtime_catalog import (
    iter_runtime_descriptors,
)
from gpd.adapters.runtime_catalog import (
    resolve_global_config_dir as _resolve_global_config_dir,
)
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME, PLANNING_DIR_NAME, TODOS_DIR_NAME

RUNTIME_UNKNOWN = "unknown"
SCOPE_GLOBAL = "global"
SCOPE_LOCAL = "local"
SOURCE_ENV = "env"
SOURCE_LOCAL = "local"
SOURCE_GLOBAL = "global"
SOURCE_UNKNOWN = "unknown"

ALL_RUNTIMES = list_runtimes()


@dataclass(frozen=True, slots=True)
class UpdateCacheCandidate:
    path: Path
    runtime: str | None = None
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class TodoCandidate:
    path: Path
    runtime: str | None = None
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class EffectiveRuntimeResolution:
    runtime: str = RUNTIME_UNKNOWN
    source: str = SOURCE_UNKNOWN
    has_gpd_install: bool = False
    install_scope: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeInstallTarget:
    config_dir: Path
    install_scope: str


def _adapter(runtime: str):
    try:
        return get_adapter(runtime)
    except KeyError:
        return None


def normalize_runtime_name(value: str | None) -> str | None:
    """Resolve a runtime id, display name, or alias to a canonical runtime name."""
    if not isinstance(value, str):
        return None

    normalized = value.strip().casefold()
    if not normalized:
        return None

    for descriptor in iter_runtime_descriptors():
        if normalized in {
            descriptor.runtime_name.casefold(),
            descriptor.display_name.casefold(),
            *(alias.casefold() for alias in descriptor.selection_aliases),
        }:
            return descriptor.runtime_name
    return None


def _paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser() == right.expanduser()


def _is_workspace_local_runtime_dir(
    config_dir: Path,
    *,
    runtime: str,
    cwd: Path | None = None,
) -> bool:
    """Return whether *config_dir* is the canonical local runtime dir for one workspace root.

    Manifestless explicit targets must not claim ownership merely because their
    basename matches a runtime's local config dir. Only directories anchored to
    the current workspace ancestry qualify for local-path ownership fallback.
    """
    adapter = _adapter(runtime)
    if adapter is None or config_dir.name != adapter.local_config_dir_name:
        return False

    resolved_cwd = cwd or Path.cwd()
    for base in (resolved_cwd, *resolved_cwd.parents):
        if _paths_equal(config_dir, adapter.resolve_local_config_dir(base)):
            return True
    return False


def _explicit_runtime_override() -> str | None:
    """Return an explicit runtime override supplied by GPD-owned shell surfaces."""
    return normalize_runtime_name(os.environ.get(ENV_GPD_ACTIVE_RUNTIME))


def _prioritized_runtimes(preferred_runtime: str | None = None) -> list[str]:
    """Return runtimes in explicit priority order, optionally promoting one runtime to the front."""
    if preferred_runtime not in ALL_RUNTIMES:
        return list(ALL_RUNTIMES)
    return [preferred_runtime] + [runtime for runtime in ALL_RUNTIMES if runtime != preferred_runtime]


def _global_runtime_dir(runtime: str, *, home: Path | None = None) -> Path:
    """Resolve the global config directory for *runtime* with env overrides."""
    adapter = _adapter(runtime)
    if adapter is None:
        raise KeyError(runtime)
    return adapter.resolve_global_config_dir(home=home)


def _local_runtime_dir(runtime: str, cwd: Path | None = None) -> Path:
    """Return the workspace-local config directory for a runtime."""
    adapter = _adapter(runtime)
    if adapter is None:
        raise KeyError(runtime)
    return adapter.resolve_local_config_dir(cwd)


def _manifest_install_scope(config_dir: Path) -> str | None:
    """Return persisted install scope from a runtime manifest, if present."""
    manifest_path = config_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(manifest, dict):
        return None

    scope = manifest.get("install_scope")
    return scope if scope in (SCOPE_LOCAL, SCOPE_GLOBAL) else None


def _manifest_runtime_status(config_dir: Path) -> tuple[str, str | None]:
    """Return the manifest parse state and normalized runtime when available."""
    manifest_path = config_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return "missing", None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "corrupt", None

    if not isinstance(manifest, dict):
        return "invalid", None

    if "runtime" not in manifest:
        return "invalid", None

    runtime = manifest.get("runtime")
    if not isinstance(runtime, str):
        return "invalid", None

    normalized = runtime.strip()
    if not normalized:
        return "invalid", None
    normalized_runtime = normalize_runtime_name(normalized)
    if normalized_runtime is None:
        return "invalid", None
    return "ok", normalized_runtime


def _runtime_from_manifest_or_path(
    config_dir: Path,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    allow_local_path_fallback: bool = True,
) -> str | None:
    """Infer the owning runtime for *config_dir* from its manifest or path."""
    manifest_state, manifest_runtime = _manifest_runtime_status(config_dir)
    if manifest_state == "ok":
        return manifest_runtime or RUNTIME_UNKNOWN
    if manifest_state != "missing":
        return None

    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    for runtime in ALL_RUNTIMES:
        adapter = _adapter(runtime)
        if adapter is None:
            continue
        if allow_local_path_fallback and _is_workspace_local_runtime_dir(config_dir, runtime=runtime, cwd=resolved_cwd):
            return runtime
        # Explicit config-dir ownership should remain stable even when the
        # current process carries unrelated runtime/XDG override env vars.
        canonical_global_dir = _resolve_global_config_dir(adapter.runtime_descriptor, home=resolved_home, environ={})
        if _paths_equal(config_dir, canonical_global_dir):
            return runtime
    return None


def _has_gpd_install(
    config_dir: Path,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> bool:
    """Return True when *config_dir* has stable markers of a GPD install."""
    runtime = _runtime_from_manifest_or_path(config_dir, cwd=cwd, home=home)
    if runtime in (None, RUNTIME_UNKNOWN):
        return False
    adapter = _adapter(runtime)
    if adapter is None:
        return False
    return adapter.has_complete_install(config_dir)


def _install_marker_quality(config_dir: Path) -> int:
    """Rank how confidently *config_dir* represents a real GPD install."""
    if _has_gpd_install(config_dir):
        return 2
    if (config_dir / MANIFEST_NAME).is_file() or (config_dir / GPD_INSTALL_DIR_NAME).is_dir():
        return 1
    return 0


def _runtime_dir_has_gpd_install(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    include_local: bool = True,
    include_global: bool = True,
) -> bool:
    """Return whether *runtime* has a concrete GPD install in the requested locations."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()

    if include_local and _has_gpd_install(_local_runtime_dir(runtime, resolved_cwd), cwd=resolved_cwd, home=resolved_home):
        return True
    if include_global and _has_gpd_install(_global_runtime_dir(runtime, home=resolved_home), cwd=resolved_cwd, home=resolved_home):
        return True
    return False


def _detect_runtime_install_target(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> RuntimeInstallTarget | None:
    """Return the concrete config dir currently serving a runtime install, if any."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    local_dir = _local_runtime_dir(runtime, resolved_cwd)
    if _has_gpd_install(local_dir, cwd=resolved_cwd, home=resolved_home):
        return RuntimeInstallTarget(
            config_dir=local_dir,
            install_scope=_manifest_install_scope(local_dir) or SCOPE_LOCAL,
        )

    global_dir = _global_runtime_dir(runtime, home=resolved_home)
    if _has_gpd_install(global_dir, cwd=resolved_cwd, home=resolved_home):
        return RuntimeInstallTarget(
            config_dir=global_dir,
            install_scope=_manifest_install_scope(global_dir) or SCOPE_GLOBAL,
        )

    return None


def resolve_effective_runtime(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
    require_gpd_install: bool = False,
) -> EffectiveRuntimeResolution:
    """Resolve the active runtime plus how it was discovered."""

    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    override_runtime = _explicit_runtime_override()
    ordered_runtimes = _prioritized_runtimes(override_runtime or preferred_runtime)

    if override_runtime is not None and not require_gpd_install:
        install_target = _detect_runtime_install_target(override_runtime, cwd=resolved_cwd, home=resolved_home)
        return EffectiveRuntimeResolution(
            runtime=override_runtime,
            source=SOURCE_ENV,
            has_gpd_install=install_target is not None,
            install_scope=None if install_target is None else install_target.install_scope,
        )

    if override_runtime is not None and require_gpd_install:
        install_target = _detect_runtime_install_target(override_runtime, cwd=resolved_cwd, home=resolved_home)
        if install_target is not None:
            return EffectiveRuntimeResolution(
                runtime=override_runtime,
                source=SOURCE_ENV,
                has_gpd_install=True,
                install_scope=install_target.install_scope,
            )

    if not require_gpd_install:
        for runtime in ordered_runtimes:
            adapter = _adapter(runtime)
            if adapter is None:
                continue
            for env_var in adapter.activation_env_vars:
                if os.environ.get(env_var):
                    install_scope = detect_install_scope(adapter.runtime_name, cwd=resolved_cwd, home=resolved_home)
                    has_install = install_scope is not None
                    return EffectiveRuntimeResolution(
                        runtime=adapter.runtime_name,
                        source=SOURCE_ENV,
                        has_gpd_install=has_install,
                        install_scope=install_scope,
                    )

    for runtime in ordered_runtimes:
        local_dir = _local_runtime_dir(runtime, resolved_cwd)
        if _has_gpd_install(local_dir, cwd=resolved_cwd, home=resolved_home):
            return EffectiveRuntimeResolution(
                runtime=runtime,
                source=SOURCE_LOCAL,
                has_gpd_install=True,
                install_scope=_manifest_install_scope(local_dir) or SCOPE_LOCAL,
            )

        global_dir = _global_runtime_dir(runtime, home=resolved_home)
        if _has_gpd_install(global_dir, cwd=resolved_cwd, home=resolved_home):
            return EffectiveRuntimeResolution(
                runtime=runtime,
                source=SOURCE_GLOBAL,
                has_gpd_install=True,
                install_scope=_manifest_install_scope(global_dir) or SCOPE_GLOBAL,
            )

    if require_gpd_install:
        return EffectiveRuntimeResolution()

    return EffectiveRuntimeResolution()


def detect_active_runtime(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Detect which AI agent runtime is currently active."""
    return resolve_effective_runtime(cwd=cwd, home=home).runtime


def detect_active_runtime_with_gpd_install(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Detect the active runtime only when that runtime also has a GPD install."""
    preferred_runtime = detect_active_runtime(cwd=cwd, home=home)
    return resolve_effective_runtime(
        cwd=cwd,
        home=home,
        preferred_runtime=preferred_runtime,
        require_gpd_install=True,
    ).runtime


def detect_runtime_for_gpd_use(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Return the runtime GPD should target for installed surfaces.

    Prefer a runtime that both appears active and has a concrete GPD install.
    Fall back to the plain active-runtime heuristic when no installed runtime
    can be identified so lookup surfaces can still prioritize the active
    runtime's cache and todo paths.
    """
    installed_runtime = detect_active_runtime_with_gpd_install(cwd=cwd, home=home)
    if installed_runtime != RUNTIME_UNKNOWN:
        return installed_runtime
    return detect_active_runtime(cwd=cwd, home=home)


def detect_runtime_install_target(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> RuntimeInstallTarget | None:
    """Return the concrete config dir currently serving *runtime*, if any."""
    return _detect_runtime_install_target(runtime, cwd=cwd, home=home)


def detect_install_scope(
    runtime: str | None = None,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> str | None:
    """Detect whether the active install for *runtime* is local or global."""
    resolved_runtime = runtime or detect_runtime_for_gpd_use(cwd=cwd, home=home)
    if resolved_runtime not in ALL_RUNTIMES:
        return None

    install_target = _detect_runtime_install_target(resolved_runtime, cwd=cwd, home=home)
    return None if install_target is None else install_target.install_scope


def _ordered_runtime_dirs_for_lookup(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> list[tuple[Path, str]]:
    """Return runtime dirs, preferring the concrete installed config dir first."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    local_dir = _local_runtime_dir(runtime, resolved_cwd)
    global_dir = _global_runtime_dir(runtime, home=resolved_home)
    install_target = _detect_runtime_install_target(runtime, cwd=resolved_cwd, home=resolved_home)

    ordered_dirs: list[tuple[Path, str]] = []
    if install_target is not None:
        ordered_dirs.append((install_target.config_dir, install_target.install_scope))

    for runtime_dir, scope in ((local_dir, SCOPE_LOCAL), (global_dir, SCOPE_GLOBAL)):
        if any(existing_dir == runtime_dir for existing_dir, _existing_scope in ordered_dirs):
            continue
        ordered_dirs.append((runtime_dir, scope))
    return ordered_dirs


def _unique_paths(paths: list[Path]) -> list[Path]:
    """Return paths in order with duplicates removed."""
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _unique_update_cache_candidates(candidates: list[UpdateCacheCandidate]) -> list[UpdateCacheCandidate]:
    """Return update-cache candidates in order with duplicate paths removed."""
    seen: set[Path] = set()
    unique: list[UpdateCacheCandidate] = []
    for candidate in candidates:
        if candidate.path in seen:
            continue
        seen.add(candidate.path)
        unique.append(candidate)
    return unique


def _unique_todo_candidates(candidates: list[TodoCandidate]) -> list[TodoCandidate]:
    """Return todo candidates in order with duplicate paths removed."""
    seen: set[Path] = set()
    unique: list[TodoCandidate] = []
    for candidate in candidates:
        if candidate.path in seen:
            continue
        seen.add(candidate.path)
        unique.append(candidate)
    return unique


def _resolved_priority_runtime(
    preferred_runtime: str | None,
    *,
    cwd: Path,
    home: Path,
) -> str:
    """Return an explicit preferred runtime when valid, else detect the lookup priority runtime."""
    if preferred_runtime in ALL_RUNTIMES:
        return preferred_runtime
    return detect_runtime_for_gpd_use(cwd=cwd, home=home)


def _runtime_dirs_in_priority_order(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[Path]:
    """Return runtime config dirs, optionally prioritizing one runtime first."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    prioritized_runtime = _resolved_priority_runtime(preferred_runtime, cwd=resolved_cwd, home=resolved_home)

    dirs: list[Path] = []
    if prioritized_runtime in ALL_RUNTIMES:
        for runtime_dir, _scope in _ordered_runtime_dirs_for_lookup(
            prioritized_runtime,
            cwd=resolved_cwd,
            home=resolved_home,
        ):
            dirs.append(runtime_dir)

    for runtime in ALL_RUNTIMES:
        if runtime == prioritized_runtime:
            continue
        dirs.append(_local_runtime_dir(runtime, resolved_cwd))
        dirs.append(_global_runtime_dir(runtime, home=resolved_home))
    return _unique_paths(dirs)


def all_runtime_dirs(*, include_local: bool = False, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return config directories for all known runtimes."""
    dirs: list[Path] = []
    if include_local:
        resolved_cwd = cwd or Path.cwd()
        dirs.extend(_local_runtime_dir(runtime, resolved_cwd) for runtime in ALL_RUNTIMES)

    resolved_home = home or Path.home()
    dirs.extend(_global_runtime_dir(runtime, home=resolved_home) for runtime in ALL_RUNTIMES)
    return _unique_paths(dirs)


def get_todo_dirs(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    prefer_active: bool = False,
) -> list[Path]:
    """Return todo directories for local and global runtime installs."""
    if prefer_active:
        preferred_runtime = detect_runtime_for_gpd_use(cwd=cwd, home=home)
        return [candidate.path for candidate in get_todo_candidates(cwd=cwd, home=home, preferred_runtime=preferred_runtime)]
    return [d / TODOS_DIR_NAME for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]


def get_todo_candidates(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[TodoCandidate]:
    """Return candidate todo directories with runtime/scope attribution."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    prioritized_runtime = _resolved_priority_runtime(preferred_runtime, cwd=resolved_cwd, home=resolved_home)
    candidates: list[TodoCandidate] = []

    if prioritized_runtime in ALL_RUNTIMES:
        for runtime_dir, scope in _ordered_runtime_dirs_for_lookup(
            prioritized_runtime,
            cwd=resolved_cwd,
            home=resolved_home,
        ):
            candidates.append(
                TodoCandidate(
                    runtime_dir / TODOS_DIR_NAME,
                    runtime=prioritized_runtime,
                    scope=scope,
                )
            )

    for runtime in ALL_RUNTIMES:
        candidates.append(
            TodoCandidate(
                _local_runtime_dir(runtime, resolved_cwd) / TODOS_DIR_NAME,
                runtime=runtime,
                scope=SCOPE_LOCAL,
            )
        )
        candidates.append(
            TodoCandidate(
                _global_runtime_dir(runtime, home=resolved_home) / TODOS_DIR_NAME,
                runtime=runtime,
                scope=SCOPE_GLOBAL,
            )
        )
    return _unique_todo_candidates(candidates)


def get_cache_dirs(*, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return cache directories for local and global runtime installs."""
    return [d / CACHE_DIR_NAME for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]


def get_update_cache_files(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[Path]:
    """Return all candidate update-cache files in priority scan order."""
    return [candidate.path for candidate in get_update_cache_candidates(cwd=cwd, home=home, preferred_runtime=preferred_runtime)]


def get_update_cache_candidates(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[UpdateCacheCandidate]:
    """Return candidate update-cache files with runtime/scope attribution."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    prioritized_runtime = _resolved_priority_runtime(preferred_runtime, cwd=resolved_cwd, home=resolved_home)
    candidates: list[UpdateCacheCandidate] = []

    if prioritized_runtime in ALL_RUNTIMES:
        for runtime_dir, scope in _ordered_runtime_dirs_for_lookup(
            prioritized_runtime,
            cwd=resolved_cwd,
            home=resolved_home,
        ):
            candidates.append(
                UpdateCacheCandidate(
                    runtime_dir / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME,
                    runtime=prioritized_runtime,
                    scope=scope,
                )
            )

    for runtime in ALL_RUNTIMES:
        candidates.append(
            UpdateCacheCandidate(
                _local_runtime_dir(runtime, resolved_cwd) / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME,
                runtime=runtime,
                scope=SCOPE_LOCAL,
            )
        )
        candidates.append(
            UpdateCacheCandidate(
                _global_runtime_dir(runtime, home=resolved_home) / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME,
                runtime=runtime,
                scope=SCOPE_GLOBAL,
            )
        )
    candidates.append(UpdateCacheCandidate(resolved_home / PLANNING_DIR_NAME / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME))
    return _unique_update_cache_candidates(candidates)


def should_consider_update_cache_candidate(
    candidate: UpdateCacheCandidate,
    *,
    active_installed_runtime: str | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
) -> bool:
    """Return whether a cache candidate should participate in update lookup.

    Runtime-specific caches are ignored when they belong to an uninstalled runtime
    and a different runtime currently has a live GPD install. This prevents stale
    caches from one runtime from being paired with another runtime's update command.
    """
    runtime = candidate.runtime
    if runtime not in ALL_RUNTIMES:
        return True

    candidate_config_dir = candidate.path.parent.parent
    manifest_state, manifest_runtime = _manifest_runtime_status(candidate_config_dir)
    if manifest_state == "ok":
        if manifest_runtime != runtime:
            return False
    elif manifest_state != "missing":
        return False

    install_target = _detect_runtime_install_target(runtime, cwd=cwd, home=home)
    if install_target is not None:
        if candidate_config_dir != install_target.config_dir:
            return False
        return candidate.scope in (None, install_target.install_scope)

    if active_installed_runtime in (None, "", RUNTIME_UNKNOWN):
        return True

    # A caller may supply an active runtime hint that no longer matches the
    # actual filesystem. Only use that hint to suppress other runtime caches
    # when the hinted runtime still has a concrete install.
    if not _runtime_dir_has_gpd_install(active_installed_runtime, cwd=cwd, home=home):
        return True

    return False


def should_consider_todo_candidate(
    candidate: TodoCandidate,
    *,
    active_installed_runtime: str | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
) -> bool:
    """Return whether a todo candidate should participate in current-task lookup."""
    runtime = candidate.runtime
    if runtime not in ALL_RUNTIMES:
        return True

    candidate_config_dir = candidate.path.parent
    manifest_state, manifest_runtime = _manifest_runtime_status(candidate_config_dir)
    if manifest_state == "ok":
        if manifest_runtime != runtime:
            return False
    elif manifest_state != "missing":
        return False

    install_target = _detect_runtime_install_target(runtime, cwd=cwd, home=home)
    if install_target is not None:
        if candidate_config_dir != install_target.config_dir:
            return False
        return candidate.scope in (None, install_target.install_scope)

    if active_installed_runtime in (None, "", RUNTIME_UNKNOWN):
        return True

    if not _runtime_dir_has_gpd_install(active_installed_runtime, cwd=cwd, home=home):
        return True

    return False


def get_gpd_install_dirs(*, prefer_active: bool = False, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return GPD installation directories for all known runtimes."""
    if not prefer_active:
        return [d / GPD_INSTALL_DIR_NAME for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]

    dirs: list[Path] = []
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    prioritized_runtime = detect_runtime_for_gpd_use(cwd=resolved_cwd, home=resolved_home)

    if prioritized_runtime in ALL_RUNTIMES:
        for runtime_dir, _scope in _ordered_runtime_dirs_for_lookup(
            prioritized_runtime,
            cwd=resolved_cwd,
            home=resolved_home,
        ):
            dirs.append(runtime_dir / GPD_INSTALL_DIR_NAME)

    for runtime in ALL_RUNTIMES:
        if runtime == prioritized_runtime:
            continue
        dirs.append(_local_runtime_dir(runtime, resolved_cwd) / GPD_INSTALL_DIR_NAME)
        dirs.append(_global_runtime_dir(runtime, home=resolved_home) / GPD_INSTALL_DIR_NAME)
    return _unique_paths(dirs)


def update_command_for_runtime(runtime: str, scope: str | None = None) -> str:
    """Return the public update command for a given runtime install.

    When the runtime cannot be identified, fall back to the canonical
    runtime-neutral command id instead of a hard-coded bootstrap runtime.
    """
    base = "gpd-update"
    try:
        command = get_adapter(runtime).update_command
    except KeyError:
        command = base

    if command == base:
        return command

    scope_flag = ""
    if scope == SCOPE_LOCAL:
        scope_flag = " --local"
    elif scope == SCOPE_GLOBAL:
        scope_flag = " --global"
    return f"{command}{scope_flag}"


__all__ = [
    "ALL_RUNTIMES",
    "RUNTIME_UNKNOWN",
    "SCOPE_GLOBAL",
    "SCOPE_LOCAL",
    "SOURCE_ENV",
    "SOURCE_GLOBAL",
    "SOURCE_LOCAL",
    "SOURCE_UNKNOWN",
    "EffectiveRuntimeResolution",
    "TodoCandidate",
    "UpdateCacheCandidate",
    "all_runtime_dirs",
    "detect_install_scope",
    "detect_active_runtime",
    "detect_active_runtime_with_gpd_install",
    "detect_runtime_for_gpd_use",
    "detect_runtime_install_target",
    "get_cache_dirs",
    "get_update_cache_candidates",
    "get_gpd_install_dirs",
    "get_todo_candidates",
    "get_todo_dirs",
    "get_update_cache_files",
    "normalize_runtime_name",
    "should_consider_todo_candidate",
    "should_consider_update_cache_candidate",
    "resolve_effective_runtime",
    "update_command_for_runtime",
]
