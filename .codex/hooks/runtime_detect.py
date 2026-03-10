"""Runtime detection for GPD hooks.

Adapter metadata is the source of truth for runtime names, command syntax,
env-var activation signals, and config-directory layout.
"""

from __future__ import annotations

import os
from pathlib import Path

from gpd.adapters import get_adapter, iter_adapters
from gpd.adapters.install_utils import expand_tilde
from gpd.core.constants import PLANNING_DIR_NAME

RUNTIME_CLAUDE = "claude-code"
RUNTIME_CODEX = "codex"
RUNTIME_GEMINI = "gemini"
RUNTIME_OPENCODE = "opencode"
RUNTIME_UNKNOWN = "unknown"

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


def detect_active_runtime() -> str:
    """Detect which AI agent runtime is currently active."""
    for adapter in iter_adapters():
        for env_var in adapter.activation_env_vars:
            if os.environ.get(env_var):
                return adapter.runtime_name

    cwd = Path.cwd()
    for runtime in ALL_RUNTIMES:
        if _local_runtime_dir(runtime, cwd).is_dir():
            return runtime

    home = Path.home()
    for runtime in ALL_RUNTIMES:
        if _global_runtime_dir(runtime, home=home).is_dir():
            return runtime

    return RUNTIME_UNKNOWN


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


def all_runtime_dirs(*, include_local: bool = False) -> list[Path]:
    """Return config directories for all known runtimes."""
    dirs: list[Path] = []
    if include_local:
        cwd = Path.cwd()
        dirs.extend(_local_runtime_dir(runtime, cwd) for runtime in ALL_RUNTIMES)

    home = Path.home()
    dirs.extend(_global_runtime_dir(runtime, home=home) for runtime in ALL_RUNTIMES)
    return _unique_paths(dirs)


def get_todo_dirs() -> list[Path]:
    """Return todo directories for local and global runtime installs."""
    return [d / "todos" for d in all_runtime_dirs(include_local=True)]


def get_cache_dirs() -> list[Path]:
    """Return cache directories for local and global runtime installs."""
    return [d / "cache" for d in all_runtime_dirs(include_local=True)]


def get_update_cache_files() -> list[Path]:
    """Return all candidate update-cache files in priority scan order."""
    preferred_runtime = detect_active_runtime()
    paths: list[Path] = []
    cwd = Path.cwd()
    home = Path.home()

    if preferred_runtime in ALL_RUNTIMES:
        paths.append(_local_runtime_dir(preferred_runtime, cwd) / "cache" / "gpd-update-check.json")
        paths.append(_global_runtime_dir(preferred_runtime, home=home) / "cache" / "gpd-update-check.json")

    paths.append(home / PLANNING_DIR_NAME / "cache" / "gpd-update-check.json")
    paths.extend(d / "gpd-update-check.json" for d in get_cache_dirs())
    return _unique_paths(paths)


def get_gpd_install_dirs(*, prefer_active: bool = False) -> list[Path]:
    """Return GPD installation directories for all known runtimes."""
    if not prefer_active:
        return [d / "get-physics-done" for d in all_runtime_dirs(include_local=True)]

    dirs: list[Path] = []
    cwd = Path.cwd()
    home = Path.home()
    for runtime in _prioritized_runtimes(detect_active_runtime()):
        dirs.append(_local_runtime_dir(runtime, cwd) / "get-physics-done")
        dirs.append(_global_runtime_dir(runtime, home=home) / "get-physics-done")
    return _unique_paths(dirs)


def update_command_for_runtime(runtime: str) -> str:
    """Return the public bootstrap command to update a given runtime install."""
    install_flag_map = {
        RUNTIME_CLAUDE: "--claude",
        RUNTIME_CODEX: "--codex",
        RUNTIME_GEMINI: "--gemini",
        RUNTIME_OPENCODE: "--opencode",
    }
    install_flag = install_flag_map.get(runtime)
    base = "npx -y github:physicalsuperintelligence/get-physics-done"
    if install_flag is None:
        return base
    return f"{base} {install_flag}"


__all__ = [
    "ALL_RUNTIMES",
    "RUNTIME_CLAUDE",
    "RUNTIME_CODEX",
    "RUNTIME_GEMINI",
    "RUNTIME_OPENCODE",
    "RUNTIME_UNKNOWN",
    "all_runtime_dirs",
    "detect_active_runtime",
    "expand_tilde",
    "get_cache_dirs",
    "get_gpd_install_dirs",
    "get_todo_dirs",
    "get_update_cache_files",
    "update_command_for_runtime",
]
