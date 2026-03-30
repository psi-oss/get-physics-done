"""Shared runtime-owned payload policy selection for hook surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import gpd.hooks.install_context as hook_layout
from gpd.adapters.runtime_catalog import get_hook_payload_policy, get_runtime_capabilities
from gpd.core.root_resolution import resolve_project_root
from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_active_runtime_with_gpd_install

HookSurface = Literal["notify", "statusline"]


def _surface_is_explicit(runtime: str | None, *, surface: HookSurface) -> bool:
    if not runtime:
        return False
    try:
        capabilities = get_runtime_capabilities(runtime)
    except Exception:
        return False
    if surface == "notify":
        return capabilities.notify_surface == "explicit"
    return capabilities.statusline_surface == "explicit"


def resolve_hook_surface_runtime(
    *,
    hook_file: str | Path,
    cwd: str | Path | None,
    surface: HookSurface,
) -> str | None:
    """Return the authoritative runtime for one hook surface invocation."""
    self_install = hook_layout.detect_self_owned_install(hook_file)
    if self_install is not None and _surface_is_explicit(self_install.runtime, surface=surface):
        return self_install.runtime

    workspace_path = resolve_project_root(cwd) if cwd is not None else None
    runtime = detect_active_runtime_with_gpd_install(cwd=workspace_path)
    return None if runtime == RUNTIME_UNKNOWN else runtime


def resolve_hook_payload_policy(
    *,
    hook_file: str | Path,
    cwd: str | Path | None,
    surface: HookSurface,
):
    """Return the runtime-aware hook payload policy for one surface invocation."""
    runtime = resolve_hook_surface_runtime(hook_file=hook_file, cwd=cwd, surface=surface)
    return get_hook_payload_policy(runtime)
