"""Runtime detection for GPD hooks.

Adapter metadata is the source of truth for runtime names, command syntax,
env-var activation signals, and config-directory layout.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from gpd.adapters import get_adapter, iter_adapters
from gpd.adapters.install_utils import MANIFEST_NAME, expand_tilde
from gpd.core.constants import PLANNING_DIR_NAME

RUNTIME_CLAUDE = "claude-code"
RUNTIME_CODEX = "codex"
RUNTIME_GEMINI = "gemini"
RUNTIME_OPENCODE = "opencode"
RUNTIME_UNKNOWN = "unknown"
SCOPE_GLOBAL = "global"
SCOPE_LOCAL = "local"

ALL_RUNTIMES = [adapter.runtime_name for adapter in iter_adapters()]


def _adapter(runtime: str):
    try:
        return get_adapter(runtime)
    except KeyError:
        return None


def _prioritized_runtimes(preferred_runtime: str | None = None) -> list[str]:
    """Return runtimes in default order, optionally promoting one runtime to the front."""
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


def detect_active_runtime(*, cwd: Path | None = None, home: Path | None = None) -> str:
    """Detect which AI agent runtime is currently active."""
    for adapter in iter_adapters():
        for env_var in adapter.activation_env_vars:
            if os.environ.get(env_var):
                return adapter.runtime_name

    resolved_cwd = cwd or Path.cwd()
    for runtime in ALL_RUNTIMES:
        if _local_runtime_dir(runtime, resolved_cwd).is_dir():
            return runtime

    resolved_home = home or Path.home()
    for runtime in ALL_RUNTIMES:
        if _global_runtime_dir(runtime, home=resolved_home).is_dir():
            return runtime

    return RUNTIME_UNKNOWN


def detect_install_scope(
    runtime: str | None = None,
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> str | None:
    """Detect whether the active install for *runtime* is local or global."""
    resolved_runtime = runtime or detect_active_runtime(cwd=cwd, home=home)
    if resolved_runtime not in ALL_RUNTIMES:
        return None

    resolved_cwd = cwd or Path.cwd()
    local_dir = _local_runtime_dir(resolved_runtime, resolved_cwd)
    if local_dir.is_dir():
        return _manifest_install_scope(local_dir) or SCOPE_LOCAL

    resolved_home = home or Path.home()
    global_dir = _global_runtime_dir(resolved_runtime, home=resolved_home)
    if global_dir.is_dir():
        return _manifest_install_scope(global_dir) or SCOPE_GLOBAL

    return None


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


def all_runtime_dirs(*, include_local: bool = False, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return config directories for all known runtimes."""
    dirs: list[Path] = []
    if include_local:
        resolved_cwd = cwd or Path.cwd()
        dirs.extend(_local_runtime_dir(runtime, resolved_cwd) for runtime in ALL_RUNTIMES)

    resolved_home = home or Path.home()
    dirs.extend(_global_runtime_dir(runtime, home=resolved_home) for runtime in ALL_RUNTIMES)
    return _unique_paths(dirs)


def get_todo_dirs(*, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return todo directories for local and global runtime installs."""
    return [d / "todos" for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]


def get_cache_dirs(*, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return cache directories for local and global runtime installs."""
    return [d / "cache" for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]


def get_update_cache_files(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
    preferred_runtime: str | None = None,
) -> list[Path]:
    """Return all candidate update-cache files in priority scan order."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    prioritized_runtime = preferred_runtime or detect_active_runtime(cwd=resolved_cwd, home=resolved_home)
    paths: list[Path] = []

    if prioritized_runtime in ALL_RUNTIMES:
        paths.append(_local_runtime_dir(prioritized_runtime, resolved_cwd) / "cache" / "gpd-update-check.json")
        paths.append(_global_runtime_dir(prioritized_runtime, home=resolved_home) / "cache" / "gpd-update-check.json")

    paths.append(resolved_home / PLANNING_DIR_NAME / "cache" / "gpd-update-check.json")
    paths.extend(d / "gpd-update-check.json" for d in get_cache_dirs(cwd=resolved_cwd, home=resolved_home))
    return _unique_paths(paths)


def get_gpd_install_dirs(*, prefer_active: bool = False, cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return GPD installation directories for all known runtimes."""
    if not prefer_active:
        return [d / "get-physics-done" for d in all_runtime_dirs(include_local=True, cwd=cwd, home=home)]

    dirs: list[Path] = []
    resolved_cwd = cwd or Path.cwd()
    resolved_home = home or Path.home()
    for runtime in _prioritized_runtimes(detect_active_runtime(cwd=resolved_cwd, home=resolved_home)):
        dirs.append(_local_runtime_dir(runtime, resolved_cwd) / "get-physics-done")
        dirs.append(_global_runtime_dir(runtime, home=resolved_home) / "get-physics-done")
    return _unique_paths(dirs)


def update_command_for_runtime(runtime: str, scope: str | None = None) -> str:
    """Return the public bootstrap command to update a given runtime install."""
    install_flag_map = {
        RUNTIME_CLAUDE: "--claude",
        RUNTIME_CODEX: "--codex",
        RUNTIME_GEMINI: "--gemini",
        RUNTIME_OPENCODE: "--opencode",
    }
    install_flag = install_flag_map.get(runtime)
    base = "npx -y get-physics-done"
    if install_flag is None:
        return base

    scope_flag = ""
    if scope == SCOPE_LOCAL:
        scope_flag = " --local"
    elif scope == SCOPE_GLOBAL:
        scope_flag = " --global"
    return f"{base} {install_flag}{scope_flag}"


__all__ = [
    "ALL_RUNTIMES",
    "RUNTIME_CLAUDE",
    "RUNTIME_CODEX",
    "RUNTIME_GEMINI",
    "RUNTIME_OPENCODE",
    "RUNTIME_UNKNOWN",
    "SCOPE_GLOBAL",
    "SCOPE_LOCAL",
    "all_runtime_dirs",
    "detect_install_scope",
    "detect_active_runtime",
    "expand_tilde",
    "get_cache_dirs",
    "get_gpd_install_dirs",
    "get_todo_dirs",
    "get_update_cache_files",
    "update_command_for_runtime",
]
