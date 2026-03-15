"""Claude Code runtime adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    _is_hook_command_for_script,
    build_hook_command,
    compile_markdown_for_runtime,
    copy_with_path_replacement,
    ensure_update_hook,
    hook_python_interpreter,
    parse_jsonc,
    read_settings,
    remove_stale_agents,
    translate_frontmatter_tool_names,
    verify_installed,
    write_settings,
)
from gpd.adapters.install_utils import (
    finish_install as _finish_install,
)
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME

logger = logging.getLogger(__name__)

_SHELL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh"})

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

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(ClaudeCodeAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            return _rewrite_gpd_cli_invocations(translated, target_dir)

        copy_with_path_replacement(
            commands_src,
            commands_dest,
            path_prefix,
            self.runtime_name,
            self._current_install_scope_flag(),
            markdown_transform=_translate,
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
            translate_tool_name=self.translate_frontmatter_tool_name,
            content_transform=lambda content: _rewrite_gpd_cli_invocations(content, target_dir),
        )
        if verify_installed(agents_dest, "agents"):
            logger.info("Installed agents")
        else:
            failures.append("agents")
        return sum(1 for f in agents_dest.iterdir() if f.is_file() and f.suffix == ".md") if agents_dest.exists() else 0

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        """Install shared specs content with a pinned Claude CLI launcher."""

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(ClaudeCodeAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            return _rewrite_gpd_cli_invocations(translated, target_dir)

        from gpd.adapters.install_utils import install_gpd_content

        failures.extend(
            install_gpd_content(
                gpd_root / "specs",
                target_dir,
                path_prefix,
                self.runtime_name,
                install_scope=self._current_install_scope_flag(),
                markdown_transform=_translate,
            )
        )

    def _install_version(self, target_dir: Path, version: str, failures: list[str]) -> None:
        """Write VERSION and install the pinned Claude GPD launcher."""
        super()._install_version(target_dir, version, failures)
        try:
            _ensure_claude_cli_launcher(target_dir)
        except OSError:
            failures.append("get-physics-done/bin/gpd")

    def _verify(self, target_dir: Path) -> None:
        """Verify the Claude Code install includes the pinned GPD launcher."""
        if not _managed_claude_cli_launcher_path(target_dir).exists():
            raise RuntimeError("Claude Code install incomplete: pinned GPD launcher is not installed")

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

        from gpd.mcp.builtin_servers import build_mcp_servers_dict, merge_managed_mcp_servers

        mcp_servers = build_mcp_servers_dict(python_path=hook_python_interpreter())
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
    translate_tool_name: Callable[[str], str | None] | None = None,
    content_transform: Callable[[str], str] | None = None,
) -> None:
    """Copy agent .md files with placeholder replacement and tool-name translation.

    Claude Code keeps native @ includes — no expansion needed.
    Tool-name translation ensures installed agents use runtime-native names
    (e.g. ``Read`` instead of ``file_read``), which affects how Claude Code
    resolves subagent tool permissions.
    """
    if not agents_src.is_dir():
        return

    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()
    for agent_md in sorted(agents_src.glob("*.md")):
        content = compile_markdown_for_runtime(
            agent_md.read_text(encoding="utf-8"),
            runtime=runtime,
            path_prefix=path_prefix,
            install_scope=install_scope,
            protect_agent_prompt_body=True,
        )
        if translate_tool_name is not None:
            content = translate_frontmatter_tool_names(content, translate_tool_name)
        if content_transform is not None:
            content = content_transform(content)
        (agents_dest / agent_md.name).write_text(content, encoding="utf-8")
        new_agent_names.add(agent_md.name)

    remove_stale_agents(agents_dest, new_agent_names)


def _managed_claude_cli_launcher_path(target_dir: Path) -> Path:
    """Return the pinned GPD CLI launcher path for Claude-installed shell calls."""
    return target_dir / "get-physics-done" / "bin" / "gpd"


def _claude_shell_launcher(target_dir: Path) -> str:
    """Return the shell-safe Claude launcher command for GPD CLI calls."""
    return json.dumps(str(_managed_claude_cli_launcher_path(target_dir).resolve()))


def _rewrite_gpd_cli_invocations(content: str, target_dir: Path) -> str:
    """Rewrite shell-command ``gpd`` invocations to the pinned Claude launcher.

    Restrict rewrites to fenced shell code blocks and only when ``gpd`` appears
    in a command position. This keeps user-facing prose and quoted shell
    strings like ``echo "ERROR: gpd initialization failed"`` intact.
    """
    launcher = _claude_shell_launcher(target_dir)
    rewritten: list[str] = []
    in_shell_fence = False

    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if in_shell_fence:
                in_shell_fence = False
            else:
                fence_language = stripped[3:].strip().lower()
                in_shell_fence = fence_language in _SHELL_FENCE_LANGUAGES
            rewritten.append(line)
            continue

        if in_shell_fence:
            rewritten.append(_rewrite_gpd_shell_line(line, launcher))
            continue

        rewritten.append(line)

    return "".join(rewritten)


def _rewrite_gpd_shell_line(line: str, launcher: str) -> str:
    """Rewrite only command-position ``gpd`` tokens on a shell line."""
    pieces: list[str] = []
    index = 0
    in_single = False
    in_double = False

    while index < len(line):
        char = line[index]
        previous = line[index - 1] if index > 0 else ""

        if char == "'" and not in_double:
            in_single = not in_single
            pieces.append(char)
            index += 1
            continue

        if char == '"' and not in_single and previous != "\\":
            in_double = not in_double
            pieces.append(char)
            index += 1
            continue

        if (
            not in_single
            and not in_double
            and line.startswith("gpd", index)
            and _is_gpd_command_start(line, index)
            and _is_gpd_token_end(line, index + 3)
        ):
            pieces.append(launcher)
            index += 3
            continue

        pieces.append(char)
        index += 1

    return "".join(pieces)


def _is_gpd_command_start(line: str, index: int) -> bool:
    """Return whether ``gpd`` starts a shell command token at *index*."""
    probe = index - 1
    while probe >= 0 and line[probe] in " \t":
        probe -= 1

    if probe < 0:
        return True

    if line[probe] in "|;(":
        return True

    if probe >= 1 and line[probe - 1 : probe + 1] in {"&&", "||", "$("}:
        return True

    return False


def _is_gpd_token_end(line: str, end_index: int) -> bool:
    """Return whether the token ending at *end_index* is a standalone ``gpd``."""
    if end_index >= len(line):
        return True
    return line[end_index].isspace() or line[end_index] in {'"', "'", "`"}


def _claude_launcher_checkout_src() -> str | None:
    """Return the checkout ``src`` path the Claude launcher should pin, if any."""
    from gpd.version import checkout_root

    root = checkout_root()
    if root is None:
        return None

    checkout_src = (root / "src").resolve(strict=False)
    if not checkout_src.is_dir():
        return None
    return str(checkout_src)


def _ensure_claude_cli_launcher(target_dir: Path) -> Path:
    """Write the workspace-pinned GPD launcher Claude shell commands should invoke."""
    launcher_path = _managed_claude_cli_launcher_path(target_dir)
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_lines = [
        "#!/bin/sh",
        "# Managed by Get Physics Done (GPD).",
        "# The launcher already pins execution, so skip CLI checkout re-exec heuristics.",
        f"export {ENV_GPD_ACTIVE_RUNTIME}=claude-code",
        "export GPD_DISABLE_CHECKOUT_REEXEC=1",
    ]
    checkout_src = _claude_launcher_checkout_src()
    if checkout_src:
        launcher_lines.extend(
            [
                f"CHECKOUT_SRC={json.dumps(checkout_src)}",
                'if [ -n "${PYTHONPATH:-}" ]; then',
                '  export PYTHONPATH="$CHECKOUT_SRC:$PYTHONPATH"',
                "else",
                '  export PYTHONPATH="$CHECKOUT_SRC"',
                "fi",
            ]
        )
    launcher_lines.append(f'exec {json.dumps(hook_python_interpreter())} -m gpd.cli "$@"')
    launcher_path.write_text("\n".join(launcher_lines) + "\n", encoding="utf-8")
    launcher_path.chmod(0o755)
    return launcher_path


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
