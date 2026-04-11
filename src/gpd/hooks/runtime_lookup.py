"""Shared runtime-lookup decisions for hook surfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gpd.adapters.runtime_catalog import normalize_runtime_name
from gpd.hooks.payload_roots import PayloadRoots
from gpd.hooks.runtime_detect import (
    RUNTIME_UNKNOWN,
    SCOPE_LOCAL,
    detect_runtime_install_target,
    supported_runtime_names,
)


@dataclass(frozen=True)
class RuntimeLookupContext:
    """Resolved runtime-owned lookup inputs for one hook payload."""

    lookup_dir: str
    active_runtime: str | None


def _project_dir_is_trusted(explicit_project_dir: bool, project_dir_trusted: bool | None) -> bool:
    return project_dir_trusted if project_dir_trusted is not None else explicit_project_dir


def normalize_runtime_hint(runtime: str | None) -> str | None:
    if runtime is None:
        return None
    normalized = normalize_runtime_name(runtime) or runtime.strip() or None
    if normalized in (None, RUNTIME_UNKNOWN):
        return None
    return normalized if normalized in supported_runtime_names() else None


def _normalized_lookup_dir(path: str | Path) -> str:
    """Return a normalized string path for hook lookup routing."""
    return str(Path(path).expanduser().resolve(strict=False))


def _has_local_runtime_install(cwd: Path) -> bool:
    for runtime in supported_runtime_names():
        install_target = detect_runtime_install_target(runtime, cwd=cwd)
        if install_target is not None and install_target.install_scope == SCOPE_LOCAL:
            return True
    return False


def resolve_runtime_lookup_active_runtime(
    *,
    workspace_dir: str,
    project_root: str,
    explicit_project_dir: bool,
    project_dir_trusted: bool | None = None,
    runtime_resolver: Callable[[str | None], str | None],
) -> str | None:
    """Resolve the active runtime without letting nested installs hijack explicit project roots."""
    if _project_dir_is_trusted(explicit_project_dir, project_dir_trusted):
        return normalize_runtime_hint(runtime_resolver(project_root))

    return normalize_runtime_hint(runtime_resolver(workspace_dir))


def resolve_runtime_lookup_dir(
    *,
    workspace_dir: str,
    project_root: str,
    explicit_project_dir: bool,
    project_dir_trusted: bool | None = None,
    active_runtime: str | None = None,
) -> str:
    """Return the cwd hook surfaces should use for runtime-owned lookups."""
    normalized_runtime = normalize_runtime_hint(active_runtime)
    if _project_dir_is_trusted(explicit_project_dir, project_dir_trusted):
        resolved_workspace = Path(workspace_dir).expanduser().resolve(strict=False)
        resolved_project = Path(project_root).expanduser().resolve(strict=False)
        if normalized_runtime is None:
            if _has_local_runtime_install(resolved_project):
                return _normalized_lookup_dir(resolved_project)
            return _normalized_lookup_dir(resolved_project)
        project_target = detect_runtime_install_target(normalized_runtime, cwd=resolved_project)
        if project_target is not None and project_target.install_scope == SCOPE_LOCAL:
            return _normalized_lookup_dir(resolved_project)
        install_target = detect_runtime_install_target(normalized_runtime, cwd=resolved_workspace)
        if install_target is not None and install_target.install_scope == SCOPE_LOCAL:
            return _normalized_lookup_dir(resolved_workspace)
        return _normalized_lookup_dir(resolved_project)

    return _normalized_lookup_dir(workspace_dir)


def resolve_runtime_lookup_context(
    *,
    workspace_dir: str,
    project_root: str,
    explicit_project_dir: bool,
    project_dir_trusted: bool | None = None,
    runtime_resolver: Callable[[str | None], str | None],
) -> RuntimeLookupContext:
    """Resolve both the runtime attribution and the lookup directory for one hook payload."""
    active_runtime = resolve_runtime_lookup_active_runtime(
        workspace_dir=workspace_dir,
        project_root=project_root,
        explicit_project_dir=explicit_project_dir,
        project_dir_trusted=project_dir_trusted,
        runtime_resolver=runtime_resolver,
    )
    return RuntimeLookupContext(
        lookup_dir=resolve_runtime_lookup_dir(
            workspace_dir=workspace_dir,
            project_root=project_root,
            explicit_project_dir=explicit_project_dir,
            project_dir_trusted=project_dir_trusted,
            active_runtime=active_runtime,
        ),
        active_runtime=active_runtime,
    )


def resolve_runtime_lookup_context_from_payload_roots(
    roots: PayloadRoots,
    *,
    runtime_resolver: Callable[[str | None], str | None],
) -> RuntimeLookupContext:
    """Resolve runtime lookup decisions from payload-root provenance."""
    return resolve_runtime_lookup_context(
        workspace_dir=roots.workspace_dir,
        project_root=roots.project_root,
        explicit_project_dir=roots.project_dir_present,
        project_dir_trusted=roots.project_dir_trusted,
        runtime_resolver=runtime_resolver,
    )
