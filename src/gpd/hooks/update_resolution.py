"""Shared update-cache resolution for hook surfaces."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import gpd.hooks.install_context as hook_layout
from gpd.adapters.install_utils import CACHE_DIR_NAME, UPDATE_CACHE_FILENAME

DebugLogger = Callable[[str], None]


def _read_update_cache(cache_file: Path, *, debug: DebugLogger) -> dict[str, object] | None:
    if not cache_file.exists():
        return None
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception as exc:
        debug(f"Failed to parse update cache {cache_file}: {exc}")
        return None
    if not isinstance(cache, dict):
        debug(f"Ignoring non-object update cache {cache_file}")
        return None
    return cache


def resolve_update_cache_inputs(
    *,
    cwd: str | Path | None,
    home: str | Path | None = None,
    active_installed_runtime: str | None = None,
    preferred_runtime: str | None = None,
) -> tuple[Path | None, Path, str | None, str | None]:
    """Return the shared runtime-preference inputs for update-cache lookup."""
    lookup = hook_layout.resolve_hook_lookup_context(
        cwd=cwd,
        home=home,
        active_installed_runtime=active_installed_runtime,
        preferred_runtime=preferred_runtime,
    )
    return lookup.lookup_cwd, lookup.resolved_home, lookup.active_runtime, lookup.preferred_runtime


def ordered_update_cache_candidates(
    *,
    cwd: str | Path | None,
    home: str | Path | None = None,
    active_installed_runtime: str | None = None,
    preferred_runtime: str | None = None,
) -> list[object]:
    """Return update-cache candidates in the shared precedence order."""
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        get_update_cache_candidates,
        normalize_runtime_name,
        should_consider_update_cache_candidate,
        supported_runtime_names,
    )

    workspace_path, resolved_home, active_runtime, resolved_preferred_runtime = resolve_update_cache_inputs(
        cwd=cwd,
        home=home,
        active_installed_runtime=active_installed_runtime,
        preferred_runtime=preferred_runtime,
    )
    cache_candidates = get_update_cache_candidates(
        cwd=workspace_path,
        home=resolved_home,
        preferred_runtime=resolved_preferred_runtime,
    )
    relevant_candidates = [
        candidate
        for candidate in cache_candidates
        if should_consider_update_cache_candidate(
            candidate,
            active_installed_runtime=active_runtime,
            cwd=workspace_path,
            home=resolved_home,
        )
    ]
    runtime_names = supported_runtime_names()
    explicit_active_runtime = normalize_runtime_name(active_installed_runtime)
    no_active_runtime = (
        explicit_active_runtime is None if active_installed_runtime is not None else active_runtime in (None, "", RUNTIME_UNKNOWN)
    )
    if no_active_runtime and resolved_preferred_runtime in runtime_names:
        preferred_candidates = [
            candidate for candidate in relevant_candidates if getattr(candidate, "runtime", None) == resolved_preferred_runtime
        ]
        if preferred_candidates:
            fallback_candidates = [candidate for candidate in relevant_candidates if getattr(candidate, "runtime", None) is None]
            seen_paths: set[Path] = set()
            preferred_first: list[object] = []
            for candidate in [*preferred_candidates, *fallback_candidates]:
                candidate_path = getattr(candidate, "path", None)
                if not isinstance(candidate_path, Path) or candidate_path in seen_paths:
                    continue
                seen_paths.add(candidate_path)
                preferred_first.append(candidate)
            relevant_candidates = preferred_first
    return relevant_candidates


def primary_update_cache_file(candidates: list[object], *, home: str | Path | None = None) -> Path:
    """Return the cache file that should receive the next background update result."""
    if candidates:
        candidate_path = getattr(candidates[0], "path", None)
        if isinstance(candidate_path, Path):
            return candidate_path
    from gpd.hooks.runtime_detect import home_update_cache_file

    return home_update_cache_file(home=home)


def _candidate_config_dir(candidate_path: object) -> Path | None:
    """Return the runtime config dir for a standard runtime update-cache path."""
    if not isinstance(candidate_path, Path):
        return None
    if candidate_path.name != UPDATE_CACHE_FILENAME or candidate_path.parent.name != CACHE_DIR_NAME:
        return None
    return candidate_path.parent.parent


def _manifest_matches_candidate(candidate: object, *, config_dir: Path) -> bool:
    """Return whether candidate metadata agrees with an authoritative install manifest."""
    from gpd.hooks.install_metadata import (
        load_install_manifest_runtime_status,
        load_install_manifest_scope_status,
    )
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, normalize_runtime_name

    candidate_runtime = normalize_runtime_name(getattr(candidate, "runtime", None))
    if candidate_runtime in (None, RUNTIME_UNKNOWN):
        candidate_runtime = None
    candidate_scope = getattr(candidate, "scope", None)

    runtime_state, _runtime_manifest, manifest_runtime = load_install_manifest_runtime_status(config_dir)
    if runtime_state != "ok" or manifest_runtime is None:
        return False
    if candidate_runtime is not None and candidate_runtime != manifest_runtime:
        return False

    scope_state, _scope_manifest, manifest_scope = load_install_manifest_scope_status(config_dir)
    if scope_state != "ok" or manifest_scope is None:
        return False
    return candidate_scope is None or candidate_scope == manifest_scope


def latest_update_cache(
    *,
    hook_file: str | Path,
    cwd: str | Path | None,
    debug: DebugLogger,
) -> tuple[dict[str, object] | None, object | None]:
    """Return the highest-priority valid update cache and its candidate metadata."""
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_runtime_install_target,
    )

    workspace_path, resolved_home, active_installed_runtime, preferred_runtime = resolve_update_cache_inputs(cwd=cwd)
    self_install = hook_layout.detect_self_owned_install(hook_file)
    active_install_target = (
        detect_runtime_install_target(active_installed_runtime, cwd=workspace_path, home=resolved_home)
        if active_installed_runtime not in (None, "", RUNTIME_UNKNOWN)
        else None
    )
    self_candidate = None
    if hook_layout.should_prefer_self_owned_install(
        self_install,
        active_install_target=active_install_target,
        active_runtime=active_installed_runtime,
        workspace_path=workspace_path,
    ):
        if self_install is not None:
            self_candidate = hook_layout.self_owned_update_cache_candidate(self_install)
            cache = _read_update_cache(self_candidate.path, debug=debug)
            if cache is not None:
                return cache, self_candidate

    fallback_hit: tuple[dict[str, object], object] | None = None
    for candidate in ordered_update_cache_candidates(
        cwd=workspace_path,
        preferred_runtime=preferred_runtime,
        active_installed_runtime=active_installed_runtime,
    ):
        cache = _read_update_cache(candidate.path, debug=debug)
        if cache is None:
            continue
        if getattr(candidate, "runtime", None):
            return cache, candidate
        if fallback_hit is None:
            fallback_hit = (cache, candidate)

    if fallback_hit is not None:
        return fallback_hit
    if self_candidate is not None:
        return None, self_candidate
    return None, None


def update_command_for_candidate(
    candidate: object | None,
    *,
    hook_file: str | Path,
    cwd: str | Path | None,
) -> str | None:
    """Return the repair/update command for one resolved update-cache candidate."""
    from gpd.hooks.install_metadata import installed_update_command, load_install_manifest_state
    from gpd.hooks.runtime_detect import (
        RUNTIME_UNKNOWN,
        detect_active_runtime_with_gpd_install,
        detect_install_scope,
        runtime_has_gpd_install,
        update_command_for_runtime,
    )

    candidate_path = getattr(candidate, "path", None)
    candidate_config_dir = _candidate_config_dir(candidate_path)
    if candidate_config_dir is not None:
        manifest_state, _manifest = load_install_manifest_state(candidate_config_dir)
        if manifest_state != "missing":
            if not _manifest_matches_candidate(candidate, config_dir=candidate_config_dir):
                return None
            return installed_update_command(candidate_config_dir)

    self_install = hook_layout.detect_self_owned_install(hook_file)
    if self_install is not None and candidate_path == self_install.cache_file:
        return installed_update_command(self_install.config_dir)

    lookup = hook_layout.resolve_hook_lookup_context(cwd=cwd)
    workspace_path = lookup.lookup_cwd
    scope_lookup_cwd = workspace_path if cwd is not None else None
    runtime = getattr(candidate, "runtime", None) or RUNTIME_UNKNOWN
    scope = getattr(candidate, "scope", None)
    if runtime != RUNTIME_UNKNOWN and not runtime_has_gpd_install(
        runtime,
        cwd=workspace_path,
        home=lookup.resolved_home,
    ):
        runtime = RUNTIME_UNKNOWN
        scope = None
    if runtime == RUNTIME_UNKNOWN:
        runtime = detect_active_runtime_with_gpd_install(cwd=scope_lookup_cwd, home=lookup.resolved_home)
    if scope is None and runtime != RUNTIME_UNKNOWN:
        scope = detect_install_scope(runtime, cwd=scope_lookup_cwd, home=lookup.resolved_home)
    return update_command_for_runtime(runtime, scope=scope)
