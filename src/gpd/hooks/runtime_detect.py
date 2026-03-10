"""Runtime detection for GPD hooks.

Detects which AI agent (Claude Code, Codex, Gemini CLI, OpenCode)
is active based on environment variables and directory existence.
Provides shared constants for runtime directory paths.
"""

import os
from pathlib import Path

# Runtime identifiers
RUNTIME_CLAUDE = "claude"
RUNTIME_CODEX = "codex"
RUNTIME_GEMINI = "gemini"
RUNTIME_OPENCODE = "opencode"
RUNTIME_UNKNOWN = "unknown"

# Map runtime → CLI install name
RUNTIME_CLI_NAMES: dict[str, str] = {
    RUNTIME_CLAUDE: "claude-code",
    RUNTIME_CODEX: "codex",
    RUNTIME_GEMINI: "gemini",
    RUNTIME_OPENCODE: "opencode",
}

# Map runtime → home-relative config directory name
RUNTIME_DIR_NAMES: dict[str, str] = {
    RUNTIME_CLAUDE: ".claude",
    RUNTIME_CODEX: ".codex",
    RUNTIME_GEMINI: ".gemini",
    RUNTIME_OPENCODE: ".config/opencode",
}

# Map runtime → cwd-relative config directory name for local installs
LOCAL_RUNTIME_DIR_NAMES: dict[str, str] = {
    RUNTIME_CLAUDE: ".claude",
    RUNTIME_CODEX: ".codex",
    RUNTIME_GEMINI: ".gemini",
    RUNTIME_OPENCODE: ".opencode",
}

# Environment variables that indicate a specific runtime is active
_RUNTIME_ENV_SIGNALS: list[tuple[str, str]] = [
    ("CLAUDE_CODE_SESSION", RUNTIME_CLAUDE),
    ("CLAUDE_CODE", RUNTIME_CLAUDE),
    ("CODEX_SESSION", RUNTIME_CODEX),
    ("CODEX_CLI", RUNTIME_CODEX),
    ("GEMINI_CLI", RUNTIME_GEMINI),
    ("OPENCODE_SESSION", RUNTIME_OPENCODE),
]

# All runtimes in priority order (used for fallback scanning)
ALL_RUNTIMES = [RUNTIME_CLAUDE, RUNTIME_CODEX, RUNTIME_GEMINI, RUNTIME_OPENCODE]


def _prioritized_runtimes(preferred_runtime: str | None = None) -> list[str]:
    """Return runtimes in default order, optionally promoting one runtime to the front."""
    if preferred_runtime not in ALL_RUNTIMES:
        return list(ALL_RUNTIMES)
    return [preferred_runtime] + [runtime for runtime in ALL_RUNTIMES if runtime != preferred_runtime]


def detect_active_runtime() -> str:
    """Detect which AI agent is currently active.

    Checks environment variables first, then falls back to directory existence.
    Returns one of: "claude", "codex", "gemini", "opencode", "unknown".
    """
    # 1. Check environment variables (most reliable signal)
    for env_var, runtime in _RUNTIME_ENV_SIGNALS:
        if os.environ.get(env_var):
            return runtime

    # 2. Fall back to checking which runtime directories exist
    home = Path.home()
    for runtime in ALL_RUNTIMES:
        runtime_dir = home / RUNTIME_DIR_NAMES[runtime]
        if runtime_dir.is_dir():
            return runtime

    return RUNTIME_UNKNOWN


def runtime_to_adapter_name(runtime: str) -> str:
    """Translate a detection result to the adapter registry name.

    detect_active_runtime() returns short names like ``"claude"`` while
    the adapter registry uses CLI names like ``"claude-code"``.  This helper
    bridges the two using :data:`RUNTIME_CLI_NAMES`.
    """
    return RUNTIME_CLI_NAMES.get(runtime, runtime)


def runtime_dir(runtime: str) -> Path:
    """Return the home-relative config directory for a runtime."""
    return Path.home() / RUNTIME_DIR_NAMES.get(runtime, RUNTIME_DIR_NAMES[RUNTIME_CLAUDE])


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
    """Return config directories for all known runtimes.

    When ``include_local`` is true, include workspace-local runtime configs
    before the home-directory configs.
    """
    dirs: list[Path] = []
    if include_local:
        cwd = Path.cwd()
        dirs.extend(cwd / LOCAL_RUNTIME_DIR_NAMES[runtime] for runtime in ALL_RUNTIMES)

    home = Path.home()
    dirs.extend(home / RUNTIME_DIR_NAMES[runtime] for runtime in ALL_RUNTIMES)
    return _unique_paths(dirs)


def get_todo_dirs() -> list[Path]:
    """Return todo directories for local and global runtime installs."""
    return [d / "todos" for d in all_runtime_dirs(include_local=True)]


def get_cache_dirs() -> list[Path]:
    """Return cache directories for local and global runtime installs."""
    return [d / "cache" for d in all_runtime_dirs(include_local=True)]


def get_update_cache_files() -> list[Path]:
    """Return all candidate update-cache files in priority scan order."""
    return [Path.home() / ".gpd" / "cache" / "gpd-update-check.json"] + [
        d / "gpd-update-check.json" for d in get_cache_dirs()
    ]


def get_gpd_install_dirs(*, prefer_active: bool = False) -> list[Path]:
    """Return GPD installation directories for all known runtimes.

    When ``prefer_active`` is true, check the active runtime's local/global
    install locations before scanning other runtimes.
    """
    if not prefer_active:
        return [d / "get-physics-done" for d in all_runtime_dirs(include_local=True)]

    dirs: list[Path] = []
    cwd = Path.cwd()
    home = Path.home()
    for runtime in _prioritized_runtimes(detect_active_runtime()):
        dirs.append(cwd / LOCAL_RUNTIME_DIR_NAMES[runtime] / "get-physics-done")
        dirs.append(home / RUNTIME_DIR_NAMES[runtime] / "get-physics-done")
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
