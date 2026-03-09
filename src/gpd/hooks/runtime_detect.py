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
    RUNTIME_OPENCODE: os.path.join(".config", "opencode"),
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


def get_gpd_install_dirs() -> list[Path]:
    """Return GPD installation directories for all known runtimes (both local and global)."""
    return [d / "get-physics-done" for d in all_runtime_dirs(include_local=True)]


def update_command_for_runtime(runtime: str) -> str:
    """Return the appropriate gpd install command for a given runtime."""
    cli_runtime = RUNTIME_CLI_NAMES.get(runtime)
    if cli_runtime is None:
        return "gpd install"
    return f"gpd install {cli_runtime}"
