"""GPD-Exp CLI — launches Claude Code with the appropriate experiment skill.

Thin launcher that translates command-line arguments into a Claude Code
slash command, shows a branded startup screen, and launches an interactive
Claude session.

Usage:
    gpd-exp "does gravity vary with altitude?"
    gpd-exp "question" --design-only
    gpd-exp --status [experiment-id]
    gpd-exp --run [experiment-id]
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import sys
from pathlib import Path

from gpd.version import __version__

GPD_EXP_LOGO = r"""
   ██████╗ ██████╗ ██████╗       ███████╗██╗  ██╗██████╗
  ██╔════╝ ██╔══██╗██╔══██╗      ██╔════╝╚██╗██╔╝██╔══██╗
  ██║  ███╗██████╔╝██║  ██║█████╗█████╗   ╚███╔╝ ██████╔╝
  ██║   ██║██╔═══╝ ██║  ██║╚════╝██╔══╝   ██╔██╗ ██╔═══╝
  ╚██████╔╝██║     ██████╔╝      ███████╗██╔╝ ██╗██║
   ╚═════╝ ╚═╝     ╚═════╝       ╚══════╝╚═╝  ╚═╝╚═╝
"""

_SYSTEM_PROMPT = """\
IMPORTANT IDENTITY CONTEXT: You are running inside GPD-Exp, an autonomous \
experiment design and execution pipeline for physics research. When a user \
gives you a research question, follow the /gpd:new-experiment skill \
workflow precisely — do NOT just chat about the topic. Run the pipeline.

You have access to the gpd.exp Python package (PydanticAI agents, domain \
functions, contracts) installed via uv. Use `uv run --directory` to invoke \
agents for structured experiment design.
"""


def _detect_model() -> str:
    """Detect the active model from env var or runtime settings.

    Priority: GPD_MODEL env var > runtime settings file > default.
    Supports Claude Code, Codex, Gemini CLI, and OpenCode via the adapters system.
    """
    _DISPLAY_NAMES = {"opus": "Opus 4.6", "sonnet": "Sonnet 4.6", "haiku": "Haiku 4.5"}
    default = _DISPLAY_NAMES["opus"]

    # 1. Explicit env var (provider-agnostic)
    env_model = os.environ.get("GPD_MODEL")
    if env_model:
        # Strip provider prefix for display (e.g. "anthropic:claude-sonnet-4-5-..." → alias lookup)
        alias = env_model.rsplit(":", 1)[-1] if ":" in env_model else env_model
        for short, display in _DISPLAY_NAMES.items():
            if short in alias.lower():
                return display
        return alias

    # 2. Detect from active runtime settings
    settings_candidates = _runtime_settings_paths()
    for path in settings_candidates:
        try:
            data = json.loads(path.read_text())
            alias = str(data.get("model", ""))
            if alias:
                return _DISPLAY_NAMES.get(alias, alias)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue

    return default


def _runtime_settings_paths() -> list[Path]:
    """Return candidate settings.json paths for known runtimes."""
    paths: list[Path] = []

    # Claude Code: CLAUDE_CONFIG_DIR or ~/.claude
    claude_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    paths.append(Path(claude_dir) / "settings.json" if claude_dir else Path.home() / ".claude" / "settings.json")

    # Codex: ~/.codex
    paths.append(Path.home() / ".codex" / "settings.json")

    # OpenCode: OPENCODE_CONFIG_DIR or ~/.opencode
    oc_dir = os.environ.get("OPENCODE_CONFIG_DIR")
    paths.append(Path(oc_dir) / "settings.json" if oc_dir else Path.home() / ".opencode" / "settings.json")

    return paths


def _show_logo() -> None:
    """Print the branded startup screen."""
    bold_magenta = "\033[1;35m"
    bold = "\033[1m"
    dim = "\033[2m"
    reset = "\033[0m"

    print(f"{bold_magenta}{GPD_EXP_LOGO}{reset}")
    print(f"  {bold}GPD-Exp v{__version__}{reset}")
    print(f"  {dim}Autonomous Experiment Pipeline{reset}")
    print(f"  {dim}Model: {_detect_model()}{reset}")
    print()


def main() -> None:
    """Parse arguments and launch Claude Code with the right skill."""
    parser = argparse.ArgumentParser(
        prog="gpd-exp",
        description="Launch an autonomous experiment pipeline via Claude Code",
    )
    parser.add_argument("question", nargs="?", default=None, help="Research question to investigate")
    parser.add_argument("--design-only", action="store_true", help="Stop after experiment design (skip execution)")
    parser.add_argument("--status", nargs="?", const="", metavar="ID", help="Check experiment status")
    parser.add_argument("--run", nargs="?", const="", metavar="ID", help="Execute an already-designed experiment")

    args = parser.parse_args()

    # Find claude binary
    claude = shutil.which("claude")
    if claude is None:
        print("Error: 'claude' not found on PATH. Install Claude Code first.", file=sys.stderr)
        sys.exit(1)

    # Build the slash command + prompt (None = interactive session)
    cmd: str | None = None
    if args.status is not None:
        cmd = f"/gpd:check-status {args.status}".strip()
    elif args.run is not None:
        cmd = f"/gpd:run-experiment {args.run}".strip()
    elif args.question:
        cmd = f'/gpd:new-experiment "{args.question}"'
        if args.design_only:
            cmd += " --design-only"

    # Show branded startup
    _show_logo()

    # Resolve the gpd-exp package directory (for --add-dir so Claude can access it)
    gpd_dir = _find_package_dir()

    # Build Claude Code arguments
    argv = [claude, "--append-system-prompt", _SYSTEM_PROMPT]
    if gpd_dir:
        argv.extend(["--add-dir", gpd_dir])

    if cmd is not None:
        # Use "--" to terminate options before the prompt, since --add-dir
        # is variadic and would otherwise consume the prompt as a directory.
        argv.append("--")
        argv.append(cmd)
    # else: launch interactive Claude Code session with no initial prompt

    # Replace this process with Claude Code (like gpd+ does)
    os.execvp(claude, argv)


def _find_package_dir() -> str | None:
    """Locate the gpd-exp package source directory.

    Priority: GPD_EXP_DIR env var > workspace detection > importlib.metadata.
    """
    # 1. Explicit env var
    env_dir = os.environ.get("GPD_EXP_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        if (p / "pyproject.toml").is_file():
            return str(p)

    # 2. Workspace detection (cwd may be inside a PSI monorepo)
    cwd_candidate = Path.cwd() / "packages" / "gpd-exp"
    if (cwd_candidate / "pyproject.toml").is_file():
        return str(cwd_candidate)

    # 3. importlib.metadata — find the installed package location
    try:
        dist = importlib.metadata.distribution("gpd")
        dist_files = dist.files
        if dist_files:
            # dist.files paths are relative to the package's install root
            # The dist._path attribute points to the .dist-info directory
            dist_info = getattr(dist, "_path", None)
            if dist_info and dist_info.is_dir():
                # Walk up from .dist-info to find pyproject.toml (editable install)
                site_dir = dist_info.parent
                for parent in [site_dir] + list(site_dir.parents):
                    if (parent / "pyproject.toml").is_file() and (parent / "src" / "gpd").is_dir():
                        return str(parent)
    except importlib.metadata.PackageNotFoundError:
        pass

    return None
