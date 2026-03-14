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
from gpd.core.constants import PLANNING_DIR_NAME, TODOS_DIR_NAME

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
class EffectiveRuntimeResolution:
    runtime: str = RUNTIME_UNKNOWN
    source: str = SOURCE_UNKNOWN
    has_gpd_install: bool = False
    install_scope: str | None = None


def _adapter(runtime: str):
    try:
        return get_adapter(runtime)
    except KeyError:
        return None


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


def _has_gpd_install(config_dir: Path) -> bool:
    """Return True when *config_dir* appears to contain a GPD install."""
    if (config_dir / MANIFEST_NAME).is_file():
        return True

    gpd_dir = config_dir / GPD_INSTALL_DIR_NAME
    return gpd_dir.is_dir()


def _install_marker_quality(config_dir: Path) -> int:
    """Rank how confidently *config_dir* represents a real GPD install."""
    if (config_dir / MANIFEST_NAME).is_file():
        return 2
    if (config_dir / GPD_INSTALL_DIR_NAME).is_dir():
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

    if include_local and _has_gpd_install(_local_runtime_dir(runtime, resolved_cwd)):
        return True
    if include_global and _has_gpd_install(_global_runtime_dir(runtime, home=resolved_home)):
        return True
    return False


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
    ordered_runtimes = _prioritized_runtimes(preferred_runtime)

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

    if require_gpd_install:
        for minimum_quality in (2, 1):
            for runtime in ordered_runtimes:
                local_dir = _local_runtime_dir(runtime, resolved_cwd)
                local_quality = _install_marker_quality(local_dir)
                if local_dir.is_dir() and local_quality >= minimum_quality:
                    return EffectiveRuntimeResolution(
                        runtime=runtime,
                        source=SOURCE_LOCAL,
                        has_gpd_install=True,
                        install_scope=_manifest_install_scope(local_dir) or SCOPE_LOCAL,
                    )

                global_dir = _global_runtime_dir(runtime, home=resolved_home)
                global_quality = _install_marker_quality(global_dir)
                if global_dir.is_dir() and global_quality >= minimum_quality:
                    return EffectiveRuntimeResolution(
                        runtime=runtime,
                        source=SOURCE_GLOBAL,
                        has_gpd_install=True,
                        install_scope=_manifest_install_scope(global_dir) or SCOPE_GLOBAL,
                    )
        return EffectiveRuntimeResolution()

    for runtime in ordered_runtimes:
        local_dir = _local_runtime_dir(runtime, resolved_cwd)
        if local_dir.is_dir():
            install_scope = detect_install_scope(runtime, cwd=resolved_cwd, home=resolved_home)
            has_install = install_scope is not None
            return EffectiveRuntimeResolution(
                runtime=runtime,
                source=SOURCE_LOCAL,
                has_gpd_install=has_install,
                install_scope=install_scope,
            )

    for runtime in ordered_runtimes:
        global_dir = _global_runtime_dir(runtime, home=resolved_home)
        if global_dir.is_dir():
            install_scope = detect_install_scope(runtime, cwd=resolved_cwd, home=resolved_home)
            has_install = install_scope is not None
            return EffectiveRuntimeResolution(
                runtime=runtime,
                source=SOURCE_GLOBAL,
                has_gpd_install=has_install,
                install_scope=install_scope,
            )

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
    can be identified. This keeps GPD-owned command formatting and runtime-
    scoped lookup surfaces aligned with the install that can actually service
    them, without redefining the broader notion of the active runtime.
    """
    installed_runtime = detect_active_runtime_with_gpd_install(cwd=cwd, home=home)
    if installed_runtime != RUNTIME_UNKNOWN:
        return installed_runtime
    return detect_active_runtime(cwd=cwd, home=home)


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

    resolved_cwd = cwd or Path.cwd()
    local_dir = _local_runtime_dir(resolved_runtime, resolved_cwd)
    if _has_gpd_install(local_dir):
        return _manifest_install_scope(local_dir) or SCOPE_LOCAL

    resolved_home = home or Path.home()
    global_dir = _global_runtime_dir(resolved_runtime, home=resolved_home)
    if _has_gpd_install(global_dir):
        return _manifest_install_scope(global_dir) or SCOPE_GLOBAL

    return None


def _ordered_runtime_dirs_for_lookup(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> list[tuple[Path, str]]:
    """Return local/global runtime dirs, preferring the detected install scope first."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    scope = detect_install_scope(runtime, cwd=resolved_cwd, home=resolved_home)

    ordered_scopes = (SCOPE_GLOBAL, SCOPE_LOCAL) if scope == SCOPE_GLOBAL else (SCOPE_LOCAL, SCOPE_GLOBAL)
    dirs_by_scope = {
        SCOPE_LOCAL: _local_runtime_dir(runtime, resolved_cwd),
        SCOPE_GLOBAL: _global_runtime_dir(runtime, home=resolved_home),
    }
    return [(dirs_by_scope[ordered_scope], ordered_scope) for ordered_scope in ordered_scopes]


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


def _resolved_priority_runtime(
    preferred_runtime: str | None,
    *,
    cwd: Path,
    home: Path,
) -> str:
    """Return an explicit preferred runtime when valid, else detect the GPD-serving runtime."""
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
        return [d / TODOS_DIR_NAME for d in _runtime_dirs_in_priority_order(cwd=cwd, home=home)]
    return [d / TODOS_DIR_NAME for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]


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
        prioritized_dirs: list[tuple[Path, str]]
        if preferred_runtime in ALL_RUNTIMES:
            prioritized_dirs = _ordered_runtime_dirs_for_lookup(
                prioritized_runtime,
                cwd=resolved_cwd,
                home=resolved_home,
            )
        else:
            prioritized_dirs = [
                (_local_runtime_dir(prioritized_runtime, resolved_cwd), SCOPE_LOCAL),
                (_global_runtime_dir(prioritized_runtime, home=resolved_home), SCOPE_GLOBAL),
            ]
        for runtime_dir, scope in prioritized_dirs:
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

    installed_scope = detect_install_scope(runtime, cwd=cwd, home=home)
    if installed_scope is not None:
        return candidate.scope in (None, installed_scope)

    if active_installed_runtime in (None, "", RUNTIME_UNKNOWN):
        return True

    # A caller may supply an active runtime hint that no longer matches the
    # actual filesystem. Only use that hint to suppress other runtime caches
    # when the hinted runtime still has a concrete install.
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
    """Return the public bootstrap command to update a given runtime install."""
    base = "npx -y get-physics-done"
    try:
        command = get_adapter(runtime).update_command
    except KeyError:
        command = base

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
    "UpdateCacheCandidate",
    "all_runtime_dirs",
    "detect_install_scope",
    "detect_active_runtime",
    "detect_active_runtime_with_gpd_install",
    "detect_runtime_for_gpd_use",
    "get_cache_dirs",
    "get_update_cache_candidates",
    "get_gpd_install_dirs",
    "get_todo_dirs",
    "get_update_cache_files",
    "should_consider_update_cache_candidate",
    "resolve_effective_runtime",
    "update_command_for_runtime",
]
