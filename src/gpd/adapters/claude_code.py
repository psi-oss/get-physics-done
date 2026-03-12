"""Claude Code runtime adapter."""

from __future__ import annotations

import logging
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    _is_hook_command_for_script,
    build_hook_command,
    copy_with_path_replacement,
    ensure_update_hook,
    parse_jsonc,
    protect_runtime_agent_prompt,
    read_settings,
    remove_stale_agents,
    replace_placeholders,
    verify_installed,
    write_settings,
)
from gpd.adapters.install_utils import (
    finish_install as _finish_install,
)

logger = logging.getLogger(__name__)

_TOOL_NAME_MAP: dict[str, str] = {
    "file_read": "Read",
    "file_write": "Write",
    "file_edit": "Edit",
    "shell": "Bash",
    "search_files": "Grep",
    "find_files": "Glob",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "notebook_edit": "NotebookEdit",
    "agent": "Agent",
    "ask_user": "AskUserQuestion",
    "todo_write": "TodoWrite",
    "task": "Task",
    "slash_command": "SlashCommand",
    "tool_search": "ToolSearch",
}


class ClaudeCodeAdapter(RuntimeAdapter):
    """Adapter for Anthropic Claude Code (CLI)."""

    tool_name_map = _TOOL_NAME_MAP

    @property
    def runtime_name(self) -> str:
        return "claude-code"

    # --- Template method hooks ---

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        commands_dest = target_dir / "commands" / "gpd"
        (target_dir / "commands").mkdir(parents=True, exist_ok=True)
        copy_with_path_replacement(
            commands_src,
            commands_dest,
            path_prefix,
            self.runtime_name,
            self._current_install_scope_flag(),
            markdown_transform=self.translate_shared_markdown,
        )
        if verify_installed(commands_dest, "commands/gpd"):
            logger.info("Installed commands/gpd")
        else:
            failures.append("commands/gpd")
        return sum(1 for f in commands_dest.rglob("*.md") if f.is_file()) if commands_dest.exists() else 0

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        agents_dest = target_dir / "agents"
        _copy_agents_native(
            agents_src,
            agents_dest,
            path_prefix,
            self.runtime_name,
            self._current_install_scope_flag(),
        )
        if verify_installed(agents_dest, "agents"):
            logger.info("Installed agents")
        else:
            failures.append("agents")
        return sum(1 for f in agents_dest.iterdir() if f.is_file() and f.suffix == ".md") if agents_dest.exists() else 0

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        settings_path = target_dir / "settings.json"
        settings = read_settings(settings_path)
        statusline_command = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["statusline"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        update_check_command = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["check_update"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        ensure_update_hook(
            settings,
            update_check_command,
            target_dir=target_dir,
            config_dir_name=self.config_dir_name,
        )

        # Wire MCP servers into the correct config file.
        # Claude Code reads mcpServers from:
        #   Global: ~/.claude.json
        #   Project: .mcp.json (in project root, parent of .claude/)
        import json as _json
        import sys

        from gpd.mcp.builtin_servers import build_mcp_servers_dict, merge_managed_mcp_servers

        mcp_servers = build_mcp_servers_dict(python_path=sys.executable)
        mcp_count = 0
        if mcp_servers:
            mcp_config_path = _mcp_config_path(target_dir, is_global=is_global)

            mcp_config: dict = {}
            if mcp_config_path.exists():
                try:
                    mcp_config = parse_jsonc(mcp_config_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    mcp_config = {}
            if not isinstance(mcp_config, dict):
                mcp_config = {}

            existing_mcp = mcp_config.get("mcpServers", {})
            mcp_config["mcpServers"] = merge_managed_mcp_servers(existing_mcp, mcp_servers)

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

    def finalize_install(
        self,
        install_result: dict[str, object],
        *,
        force_statusline: bool = False,
    ) -> None:
        """Persist settings.json-backed configuration after install."""
        settings_path = install_result.get("settingsPath")
        settings = install_result.get("settings")
        statusline_command = install_result.get("statuslineCommand")
        if isinstance(settings_path, (str, Path)) and isinstance(settings, dict) and isinstance(statusline_command, str):
            self.finish_install(
                settings_path,
                settings,
                statusline_command,
                True,
                force_statusline=force_statusline,
            )

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from Claude Code config and clean the matching MCP config."""
        manifest = read_settings(target_dir / "gpd-file-manifest.json")
        install_scope = manifest.get("install_scope")
        result = super().uninstall(target_dir)

        if install_scope == "global":
            is_global_target = True
        elif install_scope == "local":
            is_global_target = False
        else:
            try:
                is_global_target = target_dir.expanduser().resolve() == self.global_config_dir.expanduser().resolve()
            except OSError:
                is_global_target = target_dir.expanduser() == self.global_config_dir.expanduser()

        settings_path = target_dir / "settings.json"
        if settings_path.exists():
            settings = read_settings(settings_path)
            modified = False

            status_line = settings.get("statusLine")
            if isinstance(status_line, dict):
                cmd = status_line.get("command", "")
                if _is_hook_command_for_script(
                    cmd,
                    HOOK_SCRIPTS["statusline"],
                    target_dir=target_dir,
                    config_dir_name=self.config_dir_name,
                ):
                    del settings["statusLine"]
                    modified = True

            hooks = settings.get("hooks")
            if isinstance(hooks, dict):
                session_start = hooks.get("SessionStart")
                if isinstance(session_start, list):
                    before = len(session_start)
                    session_start[:] = [
                        entry
                        for entry in session_start
                        if not _entry_has_gpd_hook(entry, target_dir=target_dir, config_dir_name=self.config_dir_name)
                    ]
                    if len(session_start) < before:
                        modified = True
                    if not session_start:
                        del hooks["SessionStart"]
                    if not hooks:
                        del settings["hooks"]

            if modified:
                write_settings(settings_path, settings)

        if not is_global_target:
            import json as _json

            mcp_config_path = target_dir.parent / ".mcp.json"
            if mcp_config_path.exists():
                try:
                    mcp_config = parse_jsonc(mcp_config_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    mcp_config = None
                if isinstance(mcp_config, dict) and isinstance(mcp_config.get("mcpServers"), dict):
                    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

                    removed_keys = [key for key in list(mcp_config["mcpServers"]) if key in GPD_MCP_SERVER_KEYS]
                    if removed_keys:
                        for key in removed_keys:
                            del mcp_config["mcpServers"][key]
                        if not mcp_config["mcpServers"]:
                            del mcp_config["mcpServers"]
                        mcp_config_path.write_text(_json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
                        result["removed"].append(f"MCP servers from {mcp_config_path.name}")
            return result

        mcp_config_path = _mcp_config_path(target_dir, is_global=True)
        if not mcp_config_path.exists():
            return result

        import json as _json

        from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

        mcp_config = read_settings(mcp_config_path)
        mcp_servers = mcp_config.get("mcpServers")
        if not isinstance(mcp_servers, dict):
            return result

        removed_keys = [key for key in list(mcp_servers) if key in GPD_MCP_SERVER_KEYS]
        if not removed_keys:
            return result

        for key in removed_keys:
            del mcp_servers[key]
        if not mcp_servers:
            del mcp_config["mcpServers"]

        mcp_config_path.write_text(_json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
        result["removed"].append("MCP servers from .claude.json")
        return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _copy_agents_native(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    runtime: str,
    install_scope: str | None = None,
) -> None:
    """Copy agent .md files with placeholder replacement.

    Claude Code keeps native @ includes — no expansion needed.
    """
    if not agents_src.is_dir():
        return

    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()
    for agent_md in sorted(agents_src.glob("*.md")):
        content = agent_md.read_text(encoding="utf-8")
        content = replace_placeholders(content, path_prefix, runtime, install_scope=install_scope)
        content = protect_runtime_agent_prompt(content, runtime)
        (agents_dest / agent_md.name).write_text(content, encoding="utf-8")
        new_agent_names.add(agent_md.name)

    remove_stale_agents(agents_dest, new_agent_names)


def _mcp_config_path(target_dir: Path, *, is_global: bool) -> Path:
    """Return the Claude MCP config path associated with *target_dir*.

    The adapter should keep config mutation scoped to the install target instead
    of always reaching out to the caller's real home directory.
    """
    return target_dir.parent / (".claude.json" if is_global else ".mcp.json")


def _entry_has_gpd_hook(
    entry: object,
    *,
    target_dir: Path | None,
    config_dir_name: str | None,
) -> bool:
    """Check if a settings.json hook entry points at GPD-managed hooks."""
    if not isinstance(entry, dict):
        return False
    entry_hooks = entry.get("hooks")
    if not isinstance(entry_hooks, list):
        return False
    return any(
        isinstance(hook, dict)
        and isinstance(hook.get("command"), str)
        and (
            _is_hook_command_for_script(
                hook["command"],
                HOOK_SCRIPTS["check_update"],
                target_dir=target_dir,
                config_dir_name=config_dir_name,
            )
            or _is_hook_command_for_script(
                hook["command"],
                HOOK_SCRIPTS["statusline"],
                target_dir=target_dir,
                config_dir_name=config_dir_name,
            )
        )
        for hook in entry_hooks
    )


__all__ = ["ClaudeCodeAdapter"]
