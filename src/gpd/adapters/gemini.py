"""Gemini CLI runtime adapter.

Gemini CLI uses:
- ``.md`` agent files with YAML frontmatter (tools as YAML array, no ``color:``)
- ``.toml`` command files (TOML with ``prompt`` and ``description`` fields)
- ``settings.json`` for hooks, statusline, and ``experimental.enableAgents``
- ``@`` include directives must be expanded at install time (no native support)
- ``<sub>`` HTML tags must be stripped (terminal rendering)
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    _is_hook_command_for_script,
    build_hook_command,
    compile_markdown_for_runtime,
    convert_tool_references_in_body,
    ensure_update_hook,
    process_attribution,
    protect_runtime_agent_prompt,
    read_settings,
    remove_stale_agents,
    render_markdown_frontmatter,
    split_markdown_frontmatter,
    strip_sub_tags,
    verify_installed,
    write_manifest,
    write_settings,
)
from gpd.adapters.install_utils import (
    finish_install as _finish_install,
)
from gpd.adapters.tool_names import build_runtime_alias_map, reference_translation_map, translate_for_runtime

logger = logging.getLogger(__name__)

_TOOL_NAME_MAP: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "replace",
    "shell": "run_shell_command",
    "search_files": "search_file_content",
    "find_files": "glob",
    "web_search": "google_web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "write_todos",
    "task": "task",
    "slash_command": "slash_command",
    "tool_search": "tool_search",
}
_TOOL_ALIAS_MAP = build_runtime_alias_map(_TOOL_NAME_MAP)
_AUTO_DISCOVERED_TOOLS = frozenset({"task"})
_DROP_MCP_FRONTMATTER_TOOLS = True
_TOOL_REFERENCE_MAP = reference_translation_map(
    _TOOL_NAME_MAP,
    alias_map=_TOOL_ALIAS_MAP,
    auto_discovered_tools=_AUTO_DISCOVERED_TOOLS,
    drop_mcp_frontmatter_tools=_DROP_MCP_FRONTMATTER_TOOLS,
)


def _convert_gemini_tool_name(tool_name: str) -> str | None:
    """Convert a canonical GPD tool name or runtime alias to Gemini CLI format.

    Returns ``None`` if the tool should be excluded from the Gemini config
    (MCP tools are auto-discovered at runtime and ``task`` is auto-registered).
    """
    return translate_for_runtime(
        tool_name,
        _TOOL_NAME_MAP,
        auto_discovered_tools=_AUTO_DISCOVERED_TOOLS,
        drop_mcp_frontmatter_tools=_DROP_MCP_FRONTMATTER_TOOLS,
    )


# ---------------------------------------------------------------------------
# Frontmatter conversion
# ---------------------------------------------------------------------------


def _convert_frontmatter_to_gemini(content: str) -> str:
    """Convert canonical GPD agent/file frontmatter to Gemini CLI format.

    - ``allowed-tools:`` → ``tools:`` as YAML array
    - Tool names converted to Gemini built-in names
    - ``color:`` removed (causes validation error in Gemini CLI)
    - ``mcp__*`` tools excluded (auto-discovered at runtime)
    - ``<sub>`` tags in body stripped for terminal rendering
    """
    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return strip_sub_tags(content)

    lines = frontmatter.split("\n")
    new_lines: list[str] = []
    in_allowed_tools = False
    tools: list[str] = []

    for line in lines:
        trimmed = line.strip()

        # Convert allowed-tools YAML array to tools list
        if trimmed.startswith("allowed-tools:"):
            in_allowed_tools = True
            continue

        # Handle inline tools: field (comma-separated string)
        if trimmed.startswith("tools:"):
            tools_value = trimmed[6:].strip()
            if tools_value:
                parsed = [t.strip() for t in tools_value.split(",") if t.strip()]
                for t in parsed:
                    mapped = _convert_gemini_tool_name(t)
                    if mapped:
                        tools.append(mapped)
            else:
                # tools: with no value means YAML array follows
                in_allowed_tools = True
            continue

        # Strip color field (causes validation error in Gemini CLI)
        if trimmed.startswith("color:"):
            continue

        # Collect allowed-tools/tools array items
        if in_allowed_tools:
            if trimmed.startswith("- "):
                mapped = _convert_gemini_tool_name(trimmed[2:].strip())
                if mapped:
                    tools.append(mapped)
                continue
            elif trimmed and not trimmed.startswith("-"):
                in_allowed_tools = False

        if not in_allowed_tools:
            new_lines.append(line)

    # Deduplicate tools while preserving order
    seen: set[str] = set()
    unique_tools: list[str] = []
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            unique_tools.append(tool)

    # Add tools as YAML array (Gemini requires array format)
    if unique_tools:
        new_lines.append("tools:")
        for tool in unique_tools:
            new_lines.append(f"  - {tool}")

    new_frontmatter = "\n".join(new_lines).strip()
    return render_markdown_frontmatter(preamble, new_frontmatter, separator, strip_sub_tags(body))


# ---------------------------------------------------------------------------
# TOML conversion for commands
# ---------------------------------------------------------------------------


def _convert_to_gemini_toml(content: str) -> str:
    """Convert Claude Code markdown command to Gemini TOML format.

    Extracts selected frontmatter fields and puts body into ``prompt``.
    Uses TOML multi-line literal strings (``'''``) to avoid escape issues
    with backslashes in LaTeX/physics content.
    """
    _preamble, frontmatter, _separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return f"prompt = {json.dumps(content)}\n"
    body = body.strip()

    # Extract selected frontmatter fields
    description = ""
    context_mode = ""
    for line in frontmatter.split("\n"):
        trimmed = line.strip()
        if trimmed.startswith("description:"):
            description = trimmed[12:].strip()
        elif trimmed.startswith("context_mode:"):
            context_mode = trimmed[13:].strip()

    toml = ""
    if description:
        toml += f"description = {json.dumps(description)}\n"
    if context_mode:
        toml += f"context_mode = {json.dumps(context_mode)}\n"

    # Use TOML multi-line literal strings (''') to avoid escape issues.
    # Fall back to JSON encoding if content contains '''.
    if "'''" in body:
        toml += f"prompt = {json.dumps(body)}\n"
    else:
        toml += f"prompt = '''\n{body}\n'''\n"

    return toml


# ---------------------------------------------------------------------------
# Agent installation
# ---------------------------------------------------------------------------


def _copy_agents_gemini(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    gpd_src_root: Path | None = None,
    attribution: str | None = "",
    install_scope: str | None = None,
) -> None:
    """Install agent .md files with Gemini-specific conversions.

    - Replace path placeholders
    - Process attribution
    - Expand ``@`` includes (Gemini doesn't support native ``@`` includes)
    - Convert frontmatter (allowed-tools → tools array, strip color)
    - Convert tool name references in body text
    - Remove stale gpd-* agents not in the new set
    """
    if not agents_src.is_dir():
        return

    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()
    for agent_md in sorted(agents_src.glob("*.md")):
        content = compile_markdown_for_runtime(
            agent_md.read_text(encoding="utf-8"),
            runtime="gemini",
            path_prefix=path_prefix,
            install_scope=install_scope,
            src_root=gpd_src_root,
        )
        content = process_attribution(content, attribution)
        content = protect_runtime_agent_prompt(content, "gemini")
        content = _convert_frontmatter_to_gemini(content)
        content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)

        (agents_dest / agent_md.name).write_text(content, encoding="utf-8")
        new_agent_names.add(agent_md.name)

    remove_stale_agents(agents_dest, new_agent_names)


# ---------------------------------------------------------------------------
# Command installation (nested structure, .toml format)
# ---------------------------------------------------------------------------


def _install_commands_as_toml(
    commands_src: Path,
    commands_dest: Path,
    path_prefix: str,
    gpd_src_root: Path,
    attribution: str | None = "",
    install_scope: str | None = None,
) -> None:
    """Install commands as .toml files in nested ``commands/gpd/`` structure.

    Gemini commands are TOML files with ``description`` and ``prompt`` fields.
    """
    if not commands_src.is_dir():
        return

    # Clean destination before copy
    if commands_dest.exists():
        shutil.rmtree(commands_dest)
    commands_dest.mkdir(parents=True, exist_ok=True)

    _copy_commands_recursive(commands_src, commands_dest, path_prefix, attribution, gpd_src_root, install_scope)


def _copy_commands_recursive(
    src_dir: Path,
    dest_dir: Path,
    path_prefix: str,
    attribution: str | None,
    gpd_src_root: Path,
    install_scope: str | None = None,
) -> None:
    """Recursively copy commands, converting .md to .toml for Gemini."""
    for entry in sorted(src_dir.iterdir()):
        if entry.is_dir():
            sub_dest = dest_dir / entry.name
            sub_dest.mkdir(parents=True, exist_ok=True)
            _copy_commands_recursive(entry, sub_dest, path_prefix, attribution, gpd_src_root, install_scope)
        elif entry.suffix == ".md":
            content = compile_markdown_for_runtime(
                entry.read_text(encoding="utf-8"),
                runtime="gemini",
                path_prefix=path_prefix,
                install_scope=install_scope,
                src_root=gpd_src_root,
            )
            content = process_attribution(content, attribution)
            content = strip_sub_tags(content)
            content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)
            toml_content = _convert_to_gemini_toml(content)
            toml_path = dest_dir / entry.with_suffix(".toml").name
            toml_path.write_text(toml_content, encoding="utf-8")
        else:
            shutil.copy2(entry, dest_dir / entry.name)


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------


class GeminiAdapter(RuntimeAdapter):
    """Adapter for Google Gemini CLI."""

    tool_name_map = _TOOL_NAME_MAP
    auto_discovered_tools = _AUTO_DISCOVERED_TOOLS
    drop_mcp_frontmatter_tools = _DROP_MCP_FRONTMATTER_TOOLS
    strip_sub_tags_in_shared_markdown = True

    @property
    def runtime_name(self) -> str:
        return "gemini"

    def install(
        self,
        gpd_root: Path,
        target_dir: Path,
        *,
        is_global: bool = False,
        explicit_target: bool = False,
    ) -> dict[str, object]:
        """Install GPD and persist Gemini settings as part of the install.

        Unlike Claude Code, Gemini requires ``settings.json`` to enable
        ``experimental.enableAgents`` for the installed agents to function.
        A bare content copy is therefore an incomplete Gemini install.
        """
        previous_finalize_pending = getattr(self, "_gemini_finalize_pending", False)
        self._gemini_finalize_pending = True
        try:
            result = super().install(gpd_root, target_dir, is_global=is_global, explicit_target=explicit_target)
        finally:
            self._gemini_finalize_pending = previous_finalize_pending

        return result

    # --- Template method hooks ---

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        commands_dest = target_dir / "commands" / "gpd"
        (target_dir / "commands").mkdir(parents=True, exist_ok=True)
        _install_commands_as_toml(
            commands_src,
            commands_dest,
            path_prefix,
            gpd_root / "specs",
            attribution=self.get_commit_attribution(),
            install_scope=self._current_install_scope_flag(),
        )
        if verify_installed(commands_dest, "commands/gpd"):
            logger.info("Installed commands/gpd (TOML format)")
        else:
            failures.append("commands/gpd")
        return sum(1 for f in commands_dest.rglob("*.toml") if f.is_file()) if commands_dest.exists() else 0

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        agents_dest = target_dir / "agents"
        gpd_dest = target_dir / "get-physics-done"
        _copy_agents_gemini(
            agents_src,
            agents_dest,
            path_prefix,
            gpd_dest,
            attribution=self.get_commit_attribution(),
            install_scope=self._current_install_scope_flag(),
        )
        if verify_installed(agents_dest, "agents"):
            logger.info("Installed agents")
        else:
            failures.append("agents")
        return sum(1 for f in agents_dest.iterdir() if f.is_file() and f.suffix == ".md") if agents_dest.exists() else 0

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        settings_path = target_dir / "settings.json"
        settings = read_settings(settings_path)

        # Enable experimental agents (required for custom sub-agents in Gemini CLI)
        experimental = settings.get("experimental")
        enable_agents_was_present = isinstance(experimental, dict) and experimental.get("enableAgents") is True
        if not isinstance(experimental, dict):
            experimental = {}
            settings["experimental"] = experimental
        if not experimental.get("enableAgents"):
            experimental["enableAgents"] = True
            logger.info("Enabled experimental agents")
        self._managed_enable_agents = not enable_agents_was_present

        # Build hook commands (Python hooks, same as Claude Code)
        statusline_cmd = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["statusline"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        update_check_cmd = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["check_update"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        ensure_update_hook(
            settings,
            update_check_cmd,
            target_dir=target_dir,
            config_dir_name=self.config_dir_name,
        )

        # Wire MCP servers into settings so they start automatically.
        import sys

        from gpd.mcp.builtin_servers import build_mcp_servers_dict, merge_managed_mcp_servers

        mcp_servers = build_mcp_servers_dict(python_path=sys.executable)
        if mcp_servers:
            existing_mcp = settings.get("mcpServers", {})
            settings["mcpServers"] = merge_managed_mcp_servers(existing_mcp, mcp_servers)

        return {
            "settingsPath": str(settings_path),
            "settings": settings,
            "statuslineCommand": statusline_cmd,
            "mcpServers": len(mcp_servers),
        }

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        """Record manifest metadata for shared config keys GPD actually introduced."""
        manifest = write_manifest(
            target_dir,
            version,
            install_scope=self._current_install_scope_flag(),
        )
        if getattr(self, "_managed_enable_agents", False):
            manifest["managed_config"] = {"experimental.enableAgents": True}
            (target_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

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
        """Persist Gemini settings when install produced an in-memory config."""
        if install_result.get("settingsWritten"):
            return

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
            install_result["settingsWritten"] = True

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from a Gemini CLI .gemini/ directory.

        Extends base uninstall with Gemini-specific settings.json cleanup.
        """
        manifest = read_settings(target_dir / MANIFEST_NAME)
        managed_config = manifest.get("managed_config")
        remove_managed_enable_agents = (
            isinstance(managed_config, dict) and managed_config.get("experimental.enableAgents") is True
        )

        result = super().uninstall(target_dir)

        settings_path = target_dir / "settings.json"
        if settings_path.exists():
            settings = read_settings(settings_path)
            modified = False

            # Remove GPD statusline
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

            # Remove GPD hooks from SessionStart
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

            # Remove experimental.enableAgents only when GPD introduced it.
            experimental = settings.get("experimental")
            if (
                remove_managed_enable_agents
                and isinstance(experimental, dict)
                and experimental.get("enableAgents") is True
            ):
                del experimental["enableAgents"]
                if not experimental:
                    del settings["experimental"]
                modified = True

            # Remove GPD MCP servers
            mcp_servers = settings.get("mcpServers")
            if isinstance(mcp_servers, dict):
                from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

                removed_keys = [key for key in list(mcp_servers) if key in GPD_MCP_SERVER_KEYS]
                if removed_keys:
                    for key in removed_keys:
                        del mcp_servers[key]
                    if not mcp_servers:
                        del settings["mcpServers"]
                    modified = True

            if modified:
                write_settings(settings_path, settings)
                logger.info("Cleaned up Gemini settings.json (statusline, hooks, experimental, MCP)")

        return result

    def _verify(self, target_dir: Path) -> None:
        """Verify the Gemini install is usable, including persisted settings."""
        super()._verify(target_dir)

        if getattr(self, "_gemini_finalize_pending", False):
            return

        settings_path = target_dir / "settings.json"
        if not settings_path.exists():
            raise RuntimeError("Gemini install incomplete: settings.json was not written")

        settings = read_settings(settings_path)
        experimental = settings.get("experimental")
        if not isinstance(experimental, dict) or experimental.get("enableAgents") is not True:
            raise RuntimeError("Gemini install incomplete: experimental.enableAgents is not enabled")

        hooks = settings.get("hooks")
        session_start = hooks.get("SessionStart") if isinstance(hooks, dict) else None
        if not isinstance(session_start, list) or not any(
            _entry_has_gpd_hook(entry, target_dir=target_dir, config_dir_name=self.config_dir_name)
            for entry in session_start
        ):
            raise RuntimeError("Gemini install incomplete: update hook not configured")

        mcp_servers = settings.get("mcpServers")
        if not isinstance(mcp_servers, dict) or not mcp_servers:
            raise RuntimeError("Gemini install incomplete: MCP servers are not configured")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _entry_has_gpd_hook(
    entry: object,
    *,
    target_dir: Path | None,
    config_dir_name: str | None,
) -> bool:
    """Check if a hook entry contains the GPD-managed Gemini update hook."""
    if not isinstance(entry, dict):
        return False
    entry_hooks = entry.get("hooks")
    if not isinstance(entry_hooks, list):
        return False
    return any(
        isinstance(h, dict)
        and isinstance(h.get("command"), str)
        and _is_hook_command_for_script(
            h["command"],
            HOOK_SCRIPTS["check_update"],
            target_dir=target_dir,
            config_dir_name=config_dir_name,
        )
        for h in entry_hooks
    )


__all__ = ["GeminiAdapter"]
