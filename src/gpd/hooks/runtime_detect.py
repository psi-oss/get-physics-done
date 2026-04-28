"""Runtime detection for GPD hooks.

Adapter metadata is the source of truth for runtime names, command syntax,
env-var activation signals, and config-directory layout.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import gpd.adapters as adapters_module
from gpd.adapters.install_utils import (
    CACHE_DIR_NAME,
    GPD_INSTALL_DIR_NAME,
    UPDATE_CACHE_FILENAME,
)
from gpd.adapters.runtime_catalog import (
    get_runtime_descriptor,
    get_shared_install_metadata,
    has_global_config_env_override,
    list_runtime_names,
    resolve_global_config_dir,
    resolve_global_config_dir_candidates,
)
from gpd.adapters.runtime_catalog import (
    normalize_runtime_name as _normalize_runtime_name,
)
from gpd.core.constants import ENV_DATA_DIR, ENV_GPD_ACTIVE_RUNTIME, HOME_DATA_DIR_NAME, TODOS_DIR_NAME
from gpd.hooks.install_metadata import (
    assess_install_target,
    install_scope_from_manifest,
    load_install_manifest_runtime_status,
)

RUNTIME_UNKNOWN = "unknown"
SCOPE_GLOBAL = "global"
SCOPE_LOCAL = "local"
SOURCE_ENV = "env"
SOURCE_LOCAL = "local"
SOURCE_GLOBAL = "global"
SOURCE_UNKNOWN = "unknown"
RUNTIME_NEUTRAL_UPDATE_COMMAND = get_shared_install_metadata().bootstrap_command


def supported_runtime_names() -> tuple[str, ...]:
    """Return the current runtime inventory from the adapter registry."""
    return tuple(list_runtime_names())


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
    runtime: str = field(default_factory=lambda: RUNTIME_UNKNOWN)
    source: str = SOURCE_UNKNOWN
    has_gpd_install: bool = False
    install_scope: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeInstallTarget:
    config_dir: Path
    install_scope: str


def _source_for_install_scope(install_scope: str | None, *, fallback: str) -> str:
    """Map install-scope provenance onto public runtime-detection source labels."""
    if install_scope == SCOPE_LOCAL:
        return SOURCE_LOCAL
    if install_scope == SCOPE_GLOBAL:
        return SOURCE_GLOBAL
    return fallback


def _adapter(runtime: str):
    try:
        return adapters_module.get_adapter(runtime)
    except KeyError:
        return None


def normalize_runtime_name(value: str | None) -> str | None:
    """Resolve a runtime id, display name, or alias to a canonical runtime name."""
    return _normalize_runtime_name(value)


def _explicit_runtime_override() -> str | None:
    """Return an explicit runtime override supplied by GPD-owned shell surfaces."""
    return normalize_runtime_name(os.environ.get(ENV_GPD_ACTIVE_RUNTIME))


def _prioritized_runtimes(preferred_runtime: str | None = None) -> list[str]:
    """Return runtimes in explicit priority order, optionally promoting one runtime to the front."""
    runtime_names = supported_runtime_names()
    if preferred_runtime not in runtime_names:
        return list(runtime_names)
    return [preferred_runtime] + [runtime for runtime in runtime_names if runtime != preferred_runtime]


def _global_runtime_dirs(runtime: str, *, home: Path | None = None) -> tuple[Path, ...]:
    """Resolve authoritative global config directories for *runtime* in lookup order."""
    try:
        descriptor = get_runtime_descriptor(runtime)
    except KeyError:
        raise KeyError(runtime) from None
    return resolve_global_config_dir_candidates(descriptor, home=home)


def _env_override_runtime_dirs(runtime: str, *, home: Path | None = None) -> tuple[Path, ...]:
    """Return explicit env-resolved config dirs."""
    try:
        descriptor = get_runtime_descriptor(runtime)
    except KeyError:
        raise KeyError(runtime) from None
    if not has_global_config_env_override(descriptor):
        return ()
    return (resolve_global_config_dir(descriptor, home=home),)


def _local_runtime_dir(runtime: str, cwd: Path | None = None) -> Path:
    """Return the workspace-local config directory for a runtime."""
    try:
        descriptor = get_runtime_descriptor(runtime)
    except KeyError:
        raise KeyError(runtime) from None
    return Path(cwd or Path.cwd()) / descriptor.config_dir_name


def _local_runtime_dirs(runtime: str, cwd: Path | None = None, home: Path | None = None) -> tuple[Path, ...]:
    """Return local config dirs from the current workspace up through ancestors."""
    try:
        descriptor = get_runtime_descriptor(runtime)
    except KeyError:
        raise KeyError(runtime) from None
    resolved_cwd = Path(cwd or Path.cwd())
    resolved_home = Path(home or Path.home())
    global_dirs = {path.resolve(strict=False) for path in _global_runtime_dirs(runtime, home=resolved_home)}
    candidates: list[Path] = []
    for index, base in enumerate((resolved_cwd, *resolved_cwd.parents)):
        candidate = base / descriptor.config_dir_name
        if index > 0 and candidate.resolve(strict=False) in global_dirs:
            continue
        candidates.append(candidate)
    return tuple(candidates)


def _local_runtime_dirs_for_lookup(
    runtime: str,
    cwd: Path | None = None,
    home: Path | None = None,
) -> tuple[Path, ...]:
    """Return default local dir plus ancestor local dirs that are real installs."""
    local_dirs = _local_runtime_dirs(runtime, cwd, home=home)
    if not local_dirs:
        return ()
    first_dir = local_dirs[0]
    first_dir_has_install = _has_gpd_install(first_dir, expected_runtime=runtime)
    first_dir_has_local_install = _has_gpd_install_for_scope(
        first_dir,
        SCOPE_LOCAL,
        expected_runtime=runtime,
    )
    leading_dirs = (first_dir,) if not first_dir_has_install or first_dir_has_local_install else ()
    return (
        *leading_dirs,
        *[
            local_dir
            for local_dir in local_dirs[1:]
            if _has_gpd_install_for_scope(local_dir, SCOPE_LOCAL, expected_runtime=runtime)
        ],
    )


def _manifest_runtime_status(config_dir: Path) -> tuple[str, str | None]:
    """Return the manifest parse state and normalized runtime when available."""
    manifest_state, _manifest, runtime = load_install_manifest_runtime_status(config_dir)
    return manifest_state, runtime


def _runtime_from_manifest_or_path(config_dir: Path) -> str | None:
    """Infer the owning runtime for *config_dir* from its manifest.

    Managed surfaces fail closed without an authoritative manifest. Path shape
    alone is not strong enough ownership evidence because runtime defaults and
    env-resolved global dirs can overlap with foreign or torn installs.
    """
    manifest_state, manifest_runtime = _manifest_runtime_status(config_dir)
    if manifest_state == "ok":
        return manifest_runtime or RUNTIME_UNKNOWN
    return None


def _has_gpd_install(
    config_dir: Path,
    *,
    expected_runtime: str | None = None,
) -> bool:
    """Return True when *config_dir* has stable markers of a GPD install."""
    return assess_install_target(config_dir, expected_runtime=expected_runtime).state == "owned_complete"


def _has_gpd_install_for_scope(
    config_dir: Path,
    expected_scope: str,
    *,
    expected_runtime: str | None = None,
) -> bool:
    """Return True when *config_dir* is a complete install for the requested scope."""
    if not _has_gpd_install(config_dir, expected_runtime=expected_runtime):
        return False
    manifest_scope = install_scope_from_manifest(config_dir)
    return manifest_scope == expected_scope


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

    if include_local:
        for local_dir in _local_runtime_dirs(runtime, resolved_cwd, home=resolved_home):
            if _has_gpd_install_for_scope(local_dir, SCOPE_LOCAL, expected_runtime=runtime):
                return True
    if include_global:
        for env_dir in _env_override_runtime_dirs(runtime, home=resolved_home):
            if _has_gpd_install(env_dir, expected_runtime=runtime):
                return True
        for global_dir in _global_runtime_dirs(runtime, home=resolved_home):
            if _has_gpd_install_for_scope(global_dir, SCOPE_GLOBAL, expected_runtime=runtime):
                return True
    return False


def runtime_has_gpd_install(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    include_local: bool = True,
    include_global: bool = True,
) -> bool:
    """Return whether a supported runtime has a concrete GPD install."""
    normalized_runtime = normalize_runtime_name(runtime) or runtime
    if normalized_runtime not in supported_runtime_names():
        return False
    return _runtime_dir_has_gpd_install(
        normalized_runtime,
        cwd=cwd,
        home=home,
        include_local=include_local,
        include_global=include_global,
    )


def _detect_runtime_install_target(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> RuntimeInstallTarget | None:
    """Return the concrete config dir currently serving a runtime install, if any."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    for local_dir in _local_runtime_dirs(runtime, resolved_cwd, home=resolved_home):
        if _has_gpd_install_for_scope(local_dir, SCOPE_LOCAL, expected_runtime=runtime):
            return RuntimeInstallTarget(
                config_dir=local_dir,
                install_scope=install_scope_from_manifest(local_dir) or SCOPE_LOCAL,
            )

    for env_dir in _env_override_runtime_dirs(runtime, home=resolved_home):
        if _has_gpd_install(env_dir, expected_runtime=runtime):
            return RuntimeInstallTarget(
                config_dir=env_dir,
                install_scope=install_scope_from_manifest(env_dir) or SCOPE_GLOBAL,
            )

    for global_dir in _global_runtime_dirs(runtime, home=resolved_home):
        if _has_gpd_install_for_scope(global_dir, SCOPE_GLOBAL, expected_runtime=runtime):
            return RuntimeInstallTarget(
                config_dir=global_dir,
                install_scope=install_scope_from_manifest(global_dir) or SCOPE_GLOBAL,
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
        return EffectiveRuntimeResolution()

    if not require_gpd_install:
        for runtime in ordered_runtimes:
            try:
                descriptor = get_runtime_descriptor(runtime)
            except KeyError:
                continue
            for env_var in descriptor.activation_env_vars:
                if os.environ.get(env_var):
                    install_scope = detect_install_scope(runtime, cwd=resolved_cwd, home=resolved_home)
                    has_install = install_scope is not None
                    return EffectiveRuntimeResolution(
                        runtime=runtime,
                        source=SOURCE_ENV,
                        has_gpd_install=has_install,
                        install_scope=install_scope,
                    )

        for runtime in ordered_runtimes:
            for local_dir in _local_runtime_dirs(runtime, resolved_cwd, home=resolved_home):
                if _has_gpd_install_for_scope(local_dir, SCOPE_LOCAL, expected_runtime=runtime):
                    install_scope = install_scope_from_manifest(local_dir) or SCOPE_LOCAL
                    return EffectiveRuntimeResolution(
                        runtime=runtime,
                        source=_source_for_install_scope(install_scope, fallback=SOURCE_LOCAL),
                        has_gpd_install=True,
                        install_scope=install_scope,
                    )

        for runtime in ordered_runtimes:
            for env_dir in _env_override_runtime_dirs(runtime, home=resolved_home):
                if _has_gpd_install(env_dir, expected_runtime=runtime):
                    install_scope = install_scope_from_manifest(env_dir) or SCOPE_GLOBAL
                    return EffectiveRuntimeResolution(
                        runtime=runtime,
                        source=_source_for_install_scope(install_scope, fallback=SOURCE_GLOBAL),
                        has_gpd_install=True,
                        install_scope=install_scope,
                    )

        for runtime in ordered_runtimes:
            for global_dir in _global_runtime_dirs(runtime, home=resolved_home):
                if _has_gpd_install_for_scope(global_dir, SCOPE_GLOBAL, expected_runtime=runtime):
                    install_scope = install_scope_from_manifest(global_dir) or SCOPE_GLOBAL
                    return EffectiveRuntimeResolution(
                        runtime=runtime,
                        source=_source_for_install_scope(install_scope, fallback=SOURCE_GLOBAL),
                        has_gpd_install=True,
                        install_scope=install_scope,
                    )

        return EffectiveRuntimeResolution()

    active_runtime = detect_active_runtime(cwd=resolved_cwd, home=resolved_home)
    runtime_names = supported_runtime_names()
    if active_runtime in runtime_names:
        install_target = _detect_runtime_install_target(active_runtime, cwd=resolved_cwd, home=resolved_home)
        if install_target is not None:
            local_dirs = _local_runtime_dirs(active_runtime, resolved_cwd, home=resolved_home)
            fallback_source = SOURCE_LOCAL if install_target.config_dir in local_dirs else SOURCE_GLOBAL
            return EffectiveRuntimeResolution(
                runtime=active_runtime,
                source=_source_for_install_scope(install_target.install_scope, fallback=fallback_source),
                has_gpd_install=True,
                install_scope=install_target.install_scope,
            )

    return EffectiveRuntimeResolution()


def detect_active_runtime(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Detect which AI agent runtime is currently active."""
    return resolve_effective_runtime(cwd=cwd, home=home).runtime


def detect_active_runtime_with_gpd_install(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Detect the active runtime only when that runtime also has a GPD install."""
    return resolve_effective_runtime(cwd=cwd, home=home, require_gpd_install=True).runtime


def detect_local_runtime_with_gpd_install(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Detect a workspace-local runtime install without falling back to globals."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    active_runtime = detect_active_runtime(cwd=resolved_cwd, home=resolved_home)
    runtime_names = supported_runtime_names()
    for runtime in _prioritized_runtimes(active_runtime if active_runtime in runtime_names else None):
        for local_dir in _local_runtime_dirs(runtime, resolved_cwd, home=resolved_home):
            if _has_gpd_install_for_scope(local_dir, SCOPE_LOCAL, expected_runtime=runtime):
                return runtime
    return RUNTIME_UNKNOWN


def detect_runtime_for_gpd_use(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Return the runtime GPD should target for installed surfaces.

    Prefer a runtime that both appears active and has a concrete GPD install.
    Fall back to the plain active-runtime heuristic when no installed runtime
    can be identified so lookup surfaces can still prioritize the active
    runtime's cache and todo paths.
    """
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()

    installed_runtime = detect_active_runtime_with_gpd_install(cwd=resolved_cwd, home=resolved_home)
    if installed_runtime != RUNTIME_UNKNOWN:
        return installed_runtime

    active_runtime = detect_active_runtime(cwd=resolved_cwd, home=resolved_home)
    runtime_names = supported_runtime_names()
    for runtime in _prioritized_runtimes(active_runtime if active_runtime in runtime_names else None):
        if _detect_runtime_install_target(runtime, cwd=resolved_cwd, home=resolved_home) is not None:
            return runtime
    return active_runtime


def detect_runtime_install_target(
    runtime: str,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> RuntimeInstallTarget | None:
    """Return the concrete config dir currently serving *runtime*, if any."""
    normalized_runtime = normalize_runtime_name(runtime)
    resolved_runtime = normalized_runtime or runtime
    if resolved_runtime not in supported_runtime_names():
        return None
    return _detect_runtime_install_target(resolved_runtime, cwd=cwd, home=home)


def detect_install_scope(
    runtime: str | None = None,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> str | None:
    """Detect whether the active install for *runtime* is local or global."""
    normalized_runtime = normalize_runtime_name(runtime) if runtime is not None else None
    resolved_runtime = normalized_runtime or runtime or detect_runtime_for_gpd_use(cwd=cwd, home=home)
    if resolved_runtime not in supported_runtime_names():
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
    local_dirs = _local_runtime_dirs_for_lookup(runtime, resolved_cwd, home=resolved_home)
    install_target = _detect_runtime_install_target(runtime, cwd=resolved_cwd, home=resolved_home)

    ordered_dirs: list[tuple[Path, str]] = []
    if install_target is not None:
        ordered_dirs.append((install_target.config_dir, install_target.install_scope))

    runtime_dirs = [(local_dir, SCOPE_LOCAL) for local_dir in local_dirs]
    runtime_dirs.extend((global_dir, SCOPE_GLOBAL) for global_dir in _global_runtime_dirs(runtime, home=resolved_home))
    for runtime_dir, scope in runtime_dirs:
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
    normalized_preferred_runtime = normalize_runtime_name(preferred_runtime) or preferred_runtime
    if normalized_preferred_runtime in supported_runtime_names():
        return normalized_preferred_runtime
    return detect_runtime_for_gpd_use(cwd=cwd, home=home)


def all_runtime_dirs(*, include_local: bool = False, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return config directories for all known runtimes."""
    dirs: list[Path] = []
    runtime_names = supported_runtime_names()
    if include_local:
        resolved_cwd = cwd or Path.cwd()
        dirs.extend(_local_runtime_dir(runtime, resolved_cwd) for runtime in runtime_names)

    resolved_home = home or Path.home()
    dirs.extend(
        global_dir for runtime in runtime_names for global_dir in _global_runtime_dirs(runtime, home=resolved_home)
    )
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
        return [
            candidate.path for candidate in get_todo_candidates(cwd=cwd, home=home, preferred_runtime=preferred_runtime)
        ]
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
    runtime_names = supported_runtime_names()
    candidates: list[TodoCandidate] = []

    if prioritized_runtime in runtime_names:
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

    for runtime in runtime_names:
        for local_dir in _local_runtime_dirs_for_lookup(runtime, resolved_cwd, home=resolved_home):
            candidates.append(
                TodoCandidate(
                    local_dir / TODOS_DIR_NAME,
                    runtime=runtime,
                    scope=SCOPE_LOCAL,
                )
            )
        for global_dir in _global_runtime_dirs(runtime, home=resolved_home):
            candidates.append(
                TodoCandidate(
                    global_dir / TODOS_DIR_NAME,
                    runtime=runtime,
                    scope=SCOPE_GLOBAL,
                )
            )
    return _unique_todo_candidates(candidates)


def get_cache_dirs(*, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return cache directories for local and global runtime installs."""
    return [d / CACHE_DIR_NAME for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]


def home_update_cache_file(*, home: Path | None = None) -> Path:
    """Return the canonical home-scoped update-cache file path."""
    data_dir = os.environ.get(ENV_DATA_DIR, "").strip()
    if data_dir and (home is None or Path(home).expanduser().resolve(strict=False) == Path.home().resolve(strict=False)):
        data_root = Path(data_dir).expanduser()
    elif home is not None:
        data_root = Path(home).expanduser().resolve(strict=False) / HOME_DATA_DIR_NAME
    else:
        data_root = Path.home() / HOME_DATA_DIR_NAME
    return data_root / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME


def get_update_cache_files(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[Path]:
    """Return all candidate update-cache files in priority scan order."""
    return [
        candidate.path
        for candidate in get_update_cache_candidates(cwd=cwd, home=home, preferred_runtime=preferred_runtime)
    ]


def get_update_cache_candidates(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[UpdateCacheCandidate]:
    """Return candidate update-cache files with runtime/scope attribution."""
    resolved_cwd = cwd or Path.cwd()
    explicit_home = home is not None
    resolved_home = home or Path.home()
    prioritized_runtime = _resolved_priority_runtime(preferred_runtime, cwd=resolved_cwd, home=resolved_home)
    runtime_names = supported_runtime_names()
    candidates: list[UpdateCacheCandidate] = []

    if prioritized_runtime in runtime_names:
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

    for runtime in runtime_names:
        for local_dir in _local_runtime_dirs_for_lookup(runtime, resolved_cwd, home=resolved_home):
            candidates.append(
                UpdateCacheCandidate(
                    local_dir / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME,
                    runtime=runtime,
                    scope=SCOPE_LOCAL,
                )
            )
        for global_dir in _global_runtime_dirs(runtime, home=resolved_home):
            candidates.append(
                UpdateCacheCandidate(
                    global_dir / CACHE_DIR_NAME / UPDATE_CACHE_FILENAME,
                    runtime=runtime,
                    scope=SCOPE_GLOBAL,
                )
            )
    candidates.append(UpdateCacheCandidate(home_update_cache_file(home=resolved_home if explicit_home else None)))
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
    runtime = normalize_runtime_name(candidate.runtime) or candidate.runtime
    if runtime not in supported_runtime_names():
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

    if manifest_state == "missing":
        return False
    if not _has_gpd_install(candidate_config_dir, expected_runtime=runtime):
        return False

    normalized_active_runtime = normalize_runtime_name(active_installed_runtime) or active_installed_runtime
    if normalized_active_runtime in (None, "", RUNTIME_UNKNOWN):
        return True

    # A caller may supply an active runtime hint that does not match the
    # actual filesystem. Only use that hint to suppress other runtime caches
    # when the hinted runtime still has a concrete install.
    if not runtime_has_gpd_install(normalized_active_runtime, cwd=cwd, home=home):
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
    runtime = normalize_runtime_name(candidate.runtime) or candidate.runtime
    if runtime not in supported_runtime_names():
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

    if manifest_state == "missing":
        return False
    if not _has_gpd_install(candidate_config_dir, expected_runtime=runtime):
        return False

    normalized_active_runtime = normalize_runtime_name(active_installed_runtime) or active_installed_runtime
    if normalized_active_runtime in (None, "", RUNTIME_UNKNOWN):
        return True

    if not runtime_has_gpd_install(normalized_active_runtime, cwd=cwd, home=home):
        return True

    return False


def get_gpd_install_dirs(
    *, prefer_active: bool = False, cwd: Path | None = None, home: Path | None = None
) -> list[Path]:
    """Return GPD installation directories for all known runtimes."""
    if not prefer_active:
        return [d / GPD_INSTALL_DIR_NAME for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]

    dirs: list[Path] = []
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    prioritized_runtime = detect_runtime_for_gpd_use(cwd=resolved_cwd, home=resolved_home)
    runtime_names = supported_runtime_names()

    if prioritized_runtime in runtime_names:
        for runtime_dir, _scope in _ordered_runtime_dirs_for_lookup(
            prioritized_runtime,
            cwd=resolved_cwd,
            home=resolved_home,
        ):
            dirs.append(runtime_dir / GPD_INSTALL_DIR_NAME)

    for runtime in runtime_names:
        if runtime == prioritized_runtime:
            continue
        dirs.extend(
            local_dir / GPD_INSTALL_DIR_NAME
            for local_dir in _local_runtime_dirs_for_lookup(runtime, resolved_cwd, home=resolved_home)
        )
        dirs.extend(
            global_dir / GPD_INSTALL_DIR_NAME for global_dir in _global_runtime_dirs(runtime, home=resolved_home)
        )
    return _unique_paths(dirs)


def update_command_for_runtime(runtime: str, scope: str | None = None) -> str:
    """Return the public update command for a given runtime install.

    When the runtime cannot be identified, fall back to the canonical
    runtime-neutral bootstrap command instead of an invalid runtime surface.
    """
    runtime = normalize_runtime_name(runtime) or runtime
    base = RUNTIME_NEUTRAL_UPDATE_COMMAND
    try:
        command = adapters_module.get_adapter(runtime).update_command
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
    "supported_runtime_names",
    "detect_install_scope",
    "detect_active_runtime",
    "detect_active_runtime_with_gpd_install",
    "detect_local_runtime_with_gpd_install",
    "detect_runtime_for_gpd_use",
    "detect_runtime_install_target",
    "get_cache_dirs",
    "get_update_cache_candidates",
    "get_gpd_install_dirs",
    "get_todo_candidates",
    "get_todo_dirs",
    "get_update_cache_files",
    "normalize_runtime_name",
    "runtime_has_gpd_install",
    "should_consider_todo_candidate",
    "should_consider_update_cache_candidate",
    "resolve_effective_runtime",
    "update_command_for_runtime",
]
