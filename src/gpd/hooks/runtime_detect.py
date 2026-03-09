"""Runtime detection for GPD hooks.

Detects which AI coding runtime (Claude Code, Codex, Gemini CLI, OpenCode)
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

# Map runtime → home-relative config directory name
RUNTIME_DIR_NAMES: dict[str, str] = {
    RUNTIME_CLAUDE: ".claude",
    RUNTIME_CODEX: ".codex",
    RUNTIME_GEMINI: ".gemini",
    RUNTIME_OPENCODE: os.path.join(".config", "opencode"),
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


def detect_active_runtime() -> str:
    """Detect which AI coding runtime is currently active.

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


def runtime_dir(runtime: str) -> Path:
    """Return the home-relative config directory for a runtime."""
    return Path.home() / RUNTIME_DIR_NAMES.get(runtime, RUNTIME_DIR_NAMES[RUNTIME_CLAUDE])


def all_runtime_dirs() -> list[Path]:
    """Return config directories for all known runtimes."""
    home = Path.home()
    return [home / d for d in RUNTIME_DIR_NAMES.values()]


def get_todo_dirs() -> list[Path]:
    """Return todo directories for all known runtimes."""
    return [d / "todos" for d in all_runtime_dirs()]


def get_cache_dirs() -> list[Path]:
    """Return cache directories for all known runtimes."""
    return [d / "cache" for d in all_runtime_dirs()]


def get_gpd_install_dirs() -> list[Path]:
    """Return GPD installation directories for all known runtimes (both local and global)."""
    cwd = Path.cwd()
    home = Path.home()
    dirs: list[Path] = []
    for d_name in RUNTIME_DIR_NAMES.values():
        dirs.append(cwd / d_name / "get-physics-done")
    for d_name in RUNTIME_DIR_NAMES.values():
        dirs.append(home / d_name / "get-physics-done")
    return dirs


def update_command_for_runtime(runtime: str) -> str:
    """Return the appropriate gpd install command for a given runtime."""
    if runtime == RUNTIME_UNKNOWN:
        return "gpd install"
    return f"gpd install --runtime {runtime}"
