"""Claude Code runtime adapter."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    build_hook_command,
    cleanup_orphaned_hooks,
    copy_with_path_replacement,
    ensure_update_hook,
    read_settings,
    remove_stale_agents,
    replace_placeholders,
    verify_installed,
)
from gpd.adapters.install_utils import (
    finish_install as _finish_install,
)
from gpd.adapters.tool_names import CLAUDE_CODE, canonical

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter(RuntimeAdapter):
    """Adapter for Anthropic Claude Code (CLI)."""

    @property
    def runtime_name(self) -> str:
        return "claude-code"

    @property
    def display_name(self) -> str:
        return "Claude Code"

    @property
    def config_dir_name(self) -> str:
        return ".claude"

    @property
    def help_command(self) -> str:
        return "/gpd:help"

    @property
    def global_config_dir(self) -> Path:
        env = os.environ.get("CLAUDE_CONFIG_DIR")
        if env:
            return Path(env).expanduser()
        return Path.home() / ".claude"

    def translate_tool_name(self, canonical_name: str) -> str:
        canon = canonical(canonical_name)
        return CLAUDE_CODE.get(canon, canon)

    def generate_command(self, command_def: dict[str, object], target_dir: Path) -> Path:
        """Generate a Claude Code skill .md file from a GPD command definition."""
        name = str(command_def["name"])
        content = str(command_def.get("content", ""))
        commands_dir = target_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        out_path = commands_dir / f"{name}.md"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def generate_agent(self, agent_def: dict[str, object], target_dir: Path) -> Path:
        """Generate a Claude Code agent .md file."""
        name = str(agent_def["name"])
        content = str(agent_def.get("content", ""))
        agents_dir = target_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        out_path = agents_dir / f"{name}.md"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def generate_hook(self, hook_name: str, hook_config: dict[str, object]) -> dict[str, object]:
        """Generate a Claude Code hooks.json entry."""
        event = str(hook_config.get("event", "Notification"))
        command = str(hook_config.get("command", ""))
        matcher = hook_config.get("matcher")
        entry: dict[str, object] = {"command": command}
        if matcher:
            entry["matcher"] = str(matcher)
        return {"hooks": {event: [entry]}}

    # --- Template method hooks ---

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        commands_dest = target_dir / "commands" / "gpd"
        (target_dir / "commands").mkdir(parents=True, exist_ok=True)
        copy_with_path_replacement(commands_src, commands_dest, path_prefix, "claude")
        if verify_installed(commands_dest, "commands/gpd"):
            logger.info("Installed commands/gpd")
        else:
            failures.append("commands/gpd")
        return sum(1 for f in commands_dest.rglob("*.md") if f.is_file()) if commands_dest.exists() else 0

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        agents_dest = target_dir / "agents"
        _copy_agents_native(agents_src, agents_dest, path_prefix)
        if verify_installed(agents_dest, "agents"):
            logger.info("Installed agents")
        else:
            failures.append("agents")
        return sum(1 for f in agents_dest.iterdir() if f.is_file() and f.suffix == ".md") if agents_dest.exists() else 0

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        settings_path = target_dir / "settings.json"
        settings = cleanup_orphaned_hooks(read_settings(settings_path))
        statusline_command = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["statusline"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
        )
        update_check_command = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["check_update"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
        )
        ensure_update_hook(settings, update_check_command)

        # Wire MCP servers into the correct config file.
        # Claude Code reads mcpServers from:
        #   Global: ~/.claude.json
        #   Project: .mcp.json (in project root, parent of .claude/)
        import json as _json
        import sys

        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_servers = build_mcp_servers_dict(python_path=sys.executable)
        mcp_count = 0
        if mcp_servers:
            if is_global:
                mcp_config_path = Path.home() / ".claude.json"
            else:
                mcp_config_path = target_dir.parent / ".mcp.json"

            mcp_config: dict = {}
            if mcp_config_path.exists():
                try:
                    mcp_config = _json.loads(mcp_config_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    mcp_config = {}
            if not isinstance(mcp_config, dict):
                mcp_config = {}

            existing_mcp = mcp_config.get("mcpServers", {})
            if not isinstance(existing_mcp, dict):
                existing_mcp = {}
            existing_mcp.update(mcp_servers)
            mcp_config["mcpServers"] = existing_mcp

            mcp_config_path.write_text(_json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
            mcp_count = len(mcp_servers)

        return {
            "settingsPath": str(settings_path),
            "settings": settings,
            "statuslineCommand": statusline_command,
            "mcpServers": mcp_count,
        }

    def finish_install(
        self,
        settings_path: str | Path,
        settings: dict[str, object],
        statusline_command: str,
        should_install_statusline: bool,
        *,
        force_statusline: bool = False,
    ) -> None:
        """Apply statusline config and write settings atomically."""
        _finish_install(
            settings_path,
            settings,
            statusline_command,
            should_install_statusline,
            force_statusline=force_statusline,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _copy_agents_native(agents_src: Path, agents_dest: Path, path_prefix: str) -> None:
    """Copy agent .md files with placeholder replacement.

    Claude Code keeps native @ includes — no expansion needed.
    """
    if not agents_src.is_dir():
        return

    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()
    for agent_md in sorted(agents_src.glob("*.md")):
        content = agent_md.read_text(encoding="utf-8")
        content = replace_placeholders(content, path_prefix)
        (agents_dest / agent_md.name).write_text(content, encoding="utf-8")
        new_agent_names.add(agent_md.name)

    remove_stale_agents(agents_dest, new_agent_names)


__all__ = ["ClaudeCodeAdapter"]
