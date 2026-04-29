"""Claude Code runtime adapter."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    DEFAULT_RUNTIME_BRIDGE_SHELL_FENCE_LANGUAGES,
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    _is_hook_command_for_script,
    build_hook_command,
    compile_markdown_for_runtime,
    convert_tool_references_in_body,
    copy_with_path_replacement,
    ensure_update_hook,
    hook_python_interpreter,
    parse_jsonc,
    prune_empty_ancestors,
    read_settings,
    remove_empty_json_object_file,
    remove_stale_agents,
    rewrite_gpd_cli_invocations_to_runtime_bridge,
    translate_frontmatter_tool_names,
    verify_installed,
    write_settings,
)
from gpd.adapters.install_utils import (
    finish_install as _finish_install,
)
from gpd.mcp import managed_integrations as _managed_integrations

logger = logging.getLogger(__name__)


def _claude_settings_shape_is_valid(settings: dict[str, object]) -> bool:
    hooks = settings.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        return False
    if isinstance(hooks, dict):
        session_start = hooks.get("SessionStart")
        if session_start is not None and not isinstance(session_start, list):
            return False

    permissions = settings.get("permissions")
    if permissions is not None and not isinstance(permissions, dict):
        return False
    return True


def _claude_mcp_config_shape_is_valid(config: dict[str, object]) -> bool:
    mcp_servers = config.get("mcpServers")
    if mcp_servers is None:
        return True
    if not isinstance(mcp_servers, dict):
        return False
    return all(isinstance(entry, dict) for entry in mcp_servers.values())


def _read_claude_settings_state(settings_path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Return parsed Claude settings and a malformed marker when parsing fails."""
    if not settings_path.exists():
        return None, None
    try:
        parsed = parse_jsonc(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "malformed"
    if not isinstance(parsed, dict):
        return None, "malformed"
    if not _claude_settings_shape_is_valid(parsed):
        return None, "malformed"
    return parsed, None


def _validated_deferred_install_payload(
    install_result: Mapping[str, object],
) -> tuple[str | Path, dict[str, object], str, bool]:
    """Return deferred settings payload or fail closed before finalization."""
    settings_path = install_result.get("settingsPath")
    settings = install_result.get("settings")
    statusline_command = install_result.get("statuslineCommand")
    should_install_statusline = install_result.get("shouldInstallStatusline", True)

    if not isinstance(settings_path, (str, Path)):
        raise RuntimeError("Claude Code deferred install result is malformed; refusing to finalize install.")
    if not isinstance(settings, dict):
        raise RuntimeError("Claude Code deferred install result is malformed; refusing to finalize install.")
    if not _claude_settings_shape_is_valid(settings):
        raise RuntimeError("Claude Code deferred install result is malformed; refusing to finalize install.")
    if not isinstance(statusline_command, str):
        raise RuntimeError("Claude Code deferred install result is malformed; refusing to finalize install.")
    if type(should_install_statusline) is not bool:
        raise RuntimeError("Claude Code deferred install result is malformed; refusing to finalize install.")

    return settings_path, settings, statusline_command, should_install_statusline


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

    def project_markdown_surface(
        self,
        content: str,
        *,
        surface_kind: str,
        path_prefix: str,
        command_name: str | None = None,
        bridge_command: str | None = None,
    ) -> str:
        if surface_kind != "command":
            return super().project_markdown_surface(
                content,
                surface_kind=surface_kind,
                path_prefix=path_prefix,
                command_name=command_name,
                bridge_command=bridge_command,
            )
        if bridge_command is None:
            raise ValueError("bridge_command is required for projected Claude Code command surfaces")
        return _render_claude_command_markdown(content, bridge_command=bridge_command)

    # --- Template method hooks ---

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        commands_dest = target_dir / "commands" / "gpd"
        (target_dir / "commands").mkdir(parents=True, exist_ok=True)
        bridge_command = self.runtime_cli_bridge_command(target_dir)

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(ClaudeCodeAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            return _render_claude_command_markdown(translated, bridge_command=bridge_command)

        copy_with_path_replacement(
            commands_src,
            commands_dest,
            path_prefix,
            self.runtime_name,
            self._current_install_scope_flag(),
            markdown_transform=_translate,
            workflow_paths=True,
            workflow_target_dir=target_dir,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        if verify_installed(commands_dest):
            logger.info("Installed commands/gpd")
        else:
            failures.append("commands/gpd")
        return sum(1 for f in commands_dest.rglob("*.md") if f.is_file()) if commands_dest.exists() else 0

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        agents_dest = target_dir / "agents"
        bridge_command = self.runtime_cli_bridge_command(target_dir)
        _copy_agents_native(
            agents_src,
            agents_dest,
            path_prefix,
            self.runtime_name,
            self._current_install_scope_flag(),
            translate_tool_name=self.translate_frontmatter_tool_name,
            content_transform=lambda content: _rewrite_gpd_cli_invocations(content, bridge_command),
            body_tool_reference_map=self.tool_reference_translation_map(),
        )
        if verify_installed(agents_dest):
            logger.info("Installed agents")
        else:
            failures.append("agents")
        return sum(1 for f in agents_dest.iterdir() if f.is_file() and f.suffix == ".md") if agents_dest.exists() else 0

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        """Install shared specs content with the shared runtime CLI bridge."""
        bridge_command = self.runtime_cli_bridge_command(target_dir)

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(ClaudeCodeAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            return _rewrite_gpd_cli_invocations(translated, bridge_command)

        from gpd.adapters.install_utils import install_gpd_content

        failures.extend(
            install_gpd_content(
                gpd_root / "specs",
                target_dir,
                path_prefix,
                self.runtime_name,
                install_scope=self._current_install_scope_flag(),
                markdown_transform=_translate,
                explicit_target=getattr(self, "_install_explicit_target", False),
            )
        )

    def _install_version(self, target_dir: Path, version: str, failures: list[str]) -> None:
        """Write VERSION into the shared GPD content tree."""
        super()._install_version(target_dir, version, failures)

    def _verify(self, target_dir: Path) -> None:
        """Verify the Claude Code install satisfies the shared contract."""
        super()._verify(target_dir)

    def runtime_install_required_relpaths(self) -> tuple[str, ...]:
        """Return Claude-owned files required for a complete install."""
        return ("settings.json",)

    def install_verification_relpaths(self) -> tuple[str, ...]:
        """Defer settings.json validation until finalize_install()."""
        return self.install_detection_relpaths()

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing or malformed Claude-owned install artifacts."""
        missing = list(super().missing_install_artifacts(target_dir))
        settings_path = target_dir / "settings.json"
        if settings_path.exists():
            _, settings_parse_error = _read_claude_settings_state(settings_path)
            if settings_parse_error is not None and "settings.json" not in missing:
                missing.append("settings.json")
        return tuple(missing)

    def _preflight_runtime_config(self, target_dir: Path, is_global: bool) -> None:
        """Fail before copying files when Claude-owned config is malformed."""
        settings_path = target_dir / "settings.json"
        _, settings_parse_error = _read_claude_settings_state(settings_path)
        if settings_parse_error is not None:
            raise RuntimeError("Claude Code settings.json is malformed; refusing to overwrite it during install.")
        self._preflight_project_integrations_config(target_dir, is_global)

        project_cwd = None if is_global or getattr(self, "_install_explicit_target", False) else target_dir.parent
        mcp_servers = _build_managed_mcp_servers(cwd=project_cwd)
        if not mcp_servers:
            return

        mcp_config_path = _mcp_config_path(target_dir, is_global=is_global)
        if not mcp_config_path.exists():
            return

        try:
            mcp_config = parse_jsonc(mcp_config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise RuntimeError(
                f"{mcp_config_path.name} is malformed; refusing to overwrite Claude MCP config during install."
            ) from exc
        if not isinstance(mcp_config, dict) or not _claude_mcp_config_shape_is_valid(mcp_config):
            raise RuntimeError(
                f"{mcp_config_path.name} is malformed; refusing to overwrite Claude MCP config during install."
            )

    def _install_rollback_paths(self, gpd_root: Path, target_dir: Path, is_global: bool) -> tuple[Path, ...]:
        return (
            *super()._install_rollback_paths(gpd_root, target_dir, is_global),
            _mcp_config_path(target_dir, is_global=is_global),
        )

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        settings_path = target_dir / "settings.json"
        settings_state, settings_parse_error = _read_claude_settings_state(settings_path)
        if settings_parse_error is not None:
            raise RuntimeError("Claude Code settings.json is malformed; refusing to overwrite it during install.")
        settings = settings_state or {}
        should_install_statusline = self._installed_hook_script_available(HOOK_SCRIPTS["statusline"])
        should_install_update_hook = self._installed_hook_script_available(HOOK_SCRIPTS["check_update"])
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
        if should_install_update_hook:
            ensure_update_hook(
                settings,
                update_check_command,
                target_dir=target_dir,
                config_dir_name=self.config_dir_name,
            )
        else:
            logger.warning("Skipping update check hook because hooks/check_update.py is not GPD-managed")

        # Wire MCP servers into the correct config file.
        # Claude Code reads mcpServers from:
        #   Global: ~/.claude.json
        #   Project: .mcp.json (in project root, parent of .claude/)
        import json as _json

        from gpd.mcp.builtin_servers import merge_managed_mcp_servers

        project_cwd = None if is_global or getattr(self, "_install_explicit_target", False) else target_dir.parent
        mcp_servers = _build_managed_mcp_servers(cwd=project_cwd)
        mcp_count = 0
        if mcp_servers:
            mcp_config_path = _mcp_config_path(target_dir, is_global=is_global)

            mcp_config: dict = {}
            if mcp_config_path.exists():
                try:
                    mcp_config = parse_jsonc(mcp_config_path.read_text(encoding="utf-8"))
                except (ValueError, OSError) as exc:
                    raise RuntimeError(
                        f"{mcp_config_path.name} is malformed; refusing to overwrite Claude MCP config during install."
                    ) from exc
            if not isinstance(mcp_config, dict):
                raise RuntimeError(
                    f"{mcp_config_path.name} is malformed; refusing to overwrite Claude MCP config during install."
                )
            if not _claude_mcp_config_shape_is_valid(mcp_config):
                raise RuntimeError(
                    f"{mcp_config_path.name} is malformed; refusing to overwrite Claude MCP config during install."
                )

            existing_mcp = mcp_config.get("mcpServers", {})
            mcp_config["mcpServers"] = merge_managed_mcp_servers(existing_mcp, mcp_servers)

            mcp_config_path.write_text(_json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
            mcp_count = len(mcp_servers)

        return {
            "settingsPath": str(settings_path),
            "settings": settings,
            "statuslineCommand": statusline_command,
            "shouldInstallStatusline": should_install_statusline,
            "mcpServers": mcp_count,
        }

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Report whether Claude Code is configured for GPD autonomy alignment."""
        settings_path = target_dir / "settings.json"
        settings, settings_parse_error = _read_claude_settings_state(settings_path)
        config_valid = settings_parse_error is None
        settings = settings or {}
        permissions = settings.get("permissions")
        permissions_dict = permissions if isinstance(permissions, dict) else {}
        default_mode = (
            permissions_dict.get("defaultMode") if isinstance(permissions_dict.get("defaultMode"), str) else None
        )
        bypass_disabled = permissions_dict.get("disableBypassPermissionsMode") == "disable"
        desired_mode = "yolo" if autonomy == "yolo" else "default"
        managed_state = self._runtime_permissions_manifest_state(target_dir) or {}
        managed_by_gpd = managed_state.get("mode") == "yolo"
        config_aligned = (
            False
            if not config_valid
            else default_mode == "bypassPermissions"
            if desired_mode == "yolo"
            else not managed_by_gpd
        )
        requires_relaunch = desired_mode == "yolo" and config_aligned
        next_step: str | None = None
        message = "Claude Code is using its normal permission mode."
        if not config_valid:
            message = "Claude Code settings.json is malformed; GPD will not treat it as a defaulted permission state."
        elif desired_mode == "yolo":
            if bypass_disabled:
                config_aligned = False
                requires_relaunch = False
                message = (
                    "Claude Code bypassPermissions is disabled by managed settings, so GPD cannot enable "
                    "prompt-free runtime mode automatically."
                )
            elif default_mode == "bypassPermissions":
                message = "Claude Code will open in bypassPermissions mode on the next launch."
                next_step = (
                    "Restart the Claude Code session, or switch the current session to bypassPermissions, "
                    "before expecting uninterrupted yolo execution."
                )
            else:
                message = "Claude Code is not yet configured to open in bypassPermissions mode."
        elif managed_by_gpd:
            message = (
                "Claude Code is still pinned to a GPD-managed bypassPermissions default from an earlier yolo sync."
            )
        return {
            "runtime": self.runtime_name,
            "desired_mode": desired_mode,
            "configured_mode": "malformed" if not config_valid else default_mode or "default",
            "config_aligned": config_aligned,
            "requires_relaunch": requires_relaunch,
            "managed_by_gpd": managed_by_gpd,
            "settings_path": str(settings_path),
            "config_valid": config_valid,
            "config_parse_error": settings_parse_error,
            "message": message,
            "next_step": next_step,
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Align Claude Code defaultMode with GPD autonomy."""
        settings_path = target_dir / "settings.json"
        settings, settings_parse_error = _read_claude_settings_state(settings_path)
        if settings_parse_error is not None:
            status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
            return {
                **status,
                "changed": False,
                "sync_applied": False,
                "requires_relaunch": False,
                "warning": "Claude Code settings.json is malformed; GPD will not overwrite it.",
            }
        settings = settings or {}
        permissions = settings.get("permissions")
        permissions_dict = dict(permissions) if isinstance(permissions, dict) else {}
        settings_had_permissions = isinstance(permissions, dict)
        managed_state = self._runtime_permissions_manifest_state(target_dir) or {}
        changed = False
        sync_applied = False

        if autonomy == "yolo":
            if permissions_dict.get("disableBypassPermissionsMode") == "disable":
                status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
                return {
                    **status,
                    "changed": False,
                    "sync_applied": False,
                    "requires_relaunch": False,
                    "warning": (
                        "Claude Code bypassPermissions is disabled by managed settings; switch runtimes or "
                        "remove the managed restriction to get uninterrupted yolo execution."
                    ),
                }
            current_mode = (
                permissions_dict.get("defaultMode") if isinstance(permissions_dict.get("defaultMode"), str) else None
            )
            if current_mode != "bypassPermissions":
                restore_state = {
                    "had_permissions": settings_had_permissions,
                    "had_default_mode": "defaultMode" in permissions_dict,
                    "default_mode": permissions_dict.get("defaultMode"),
                }
                permissions_dict["defaultMode"] = "bypassPermissions"
                settings["permissions"] = permissions_dict
                write_settings(settings_path, settings)
                self._set_runtime_permissions_manifest_state(
                    target_dir,
                    {
                        "mode": "yolo",
                        "restore": restore_state,
                    },
                )
                changed = True
            status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
            sync_applied = bool(status.get("config_aligned"))
            return {
                **status,
                "changed": changed,
                "sync_applied": sync_applied,
                "requires_relaunch": changed,
                "next_step": (
                    "Restart the Claude Code session, or switch the current session to bypassPermissions, "
                    "before expecting uninterrupted yolo execution."
                )
                if changed
                else None,
            }

        restore_state = managed_state.get("restore") if isinstance(managed_state, dict) else None
        if managed_state.get("mode") == "yolo" and isinstance(restore_state, dict):
            if restore_state.get("had_default_mode"):
                permissions_dict["defaultMode"] = restore_state.get("default_mode")
            else:
                permissions_dict.pop("defaultMode", None)
            if permissions_dict:
                settings["permissions"] = permissions_dict
            elif settings_had_permissions:
                settings.pop("permissions", None)
            write_settings(settings_path, settings)
            self._set_runtime_permissions_manifest_state(target_dir, None)
            changed = True

        status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
        sync_applied = bool(status.get("config_aligned"))
        result = {
            **status,
            "changed": changed,
            "sync_applied": sync_applied,
            "requires_relaunch": changed,
        }
        if changed:
            result["next_step"] = "Restart Claude Code to return the current session to its normal permission mode."
        elif status.get("configured_mode") == "bypassPermissions":
            result["message"] = (
                "Claude Code is still configured for bypassPermissions, but GPD left it untouched because "
                "that setting was not created by a prior GPD yolo sync."
            )
        return result

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
        settings_path, settings, statusline_command, should_install_statusline = _validated_deferred_install_payload(
            install_result
        )
        _, settings_parse_error = _read_claude_settings_state(Path(settings_path))
        if settings_parse_error is not None:
            raise RuntimeError("Claude Code settings.json is malformed; refusing to overwrite it during finalize.")
        self.finish_install(
            settings_path,
            settings,
            statusline_command,
            should_install_statusline,
            force_statusline=force_statusline,
        )

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from Claude Code config and clean the matching MCP config."""
        manifest = read_settings(target_dir / MANIFEST_NAME)
        install_scope = manifest.get("install_scope")
        has_authoritative_manifest = self._has_authoritative_install_manifest(target_dir)
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

            runtime_permission_state = manifest.get("gpd_runtime_permissions")
            restore_state = (
                runtime_permission_state.get("restore")
                if isinstance(runtime_permission_state, dict) and runtime_permission_state.get("mode") == "yolo"
                else None
            )
            if isinstance(restore_state, dict):
                permissions = settings.get("permissions")
                permissions_dict = dict(permissions) if isinstance(permissions, dict) else {}
                if restore_state.get("had_default_mode"):
                    permissions_dict["defaultMode"] = restore_state.get("default_mode")
                else:
                    permissions_dict.pop("defaultMode", None)
                if permissions_dict:
                    settings["permissions"] = permissions_dict
                else:
                    settings.pop("permissions", None)
                modified = True

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
            if has_authoritative_manifest and remove_empty_json_object_file(settings_path):
                result["removed"].append(settings_path.name)

        if not is_global_target:
            import json as _json

            mcp_config_path = target_dir.parent / ".mcp.json"
            if mcp_config_path.exists():
                try:
                    mcp_config = parse_jsonc(mcp_config_path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    mcp_config = None
                if isinstance(mcp_config, dict) and isinstance(mcp_config.get("mcpServers"), dict):
                    removed_keys = [key for key in list(mcp_config["mcpServers"]) if key in _managed_mcp_server_keys()]
                    if removed_keys:
                        for key in removed_keys:
                            del mcp_config["mcpServers"][key]
                        if not mcp_config["mcpServers"]:
                            del mcp_config["mcpServers"]
                        mcp_config_path.write_text(_json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
                        result["removed"].append(f"MCP servers from {mcp_config_path.name}")
                if has_authoritative_manifest and remove_empty_json_object_file(mcp_config_path):
                    result["removed"].append(mcp_config_path.name)
            for path in (
                target_dir / "commands",
                target_dir / "agents",
                target_dir / "hooks",
                target_dir / "cache",
                target_dir,
            ):
                prune_empty_ancestors(path, stop_at=target_dir.parent)
            return result

        mcp_config_path = _mcp_config_path(target_dir, is_global=True)
        if not mcp_config_path.exists():
            for path in (
                target_dir / "commands",
                target_dir / "agents",
                target_dir / "hooks",
                target_dir / "cache",
                target_dir,
            ):
                prune_empty_ancestors(path, stop_at=target_dir.parent)
            return result

        import json as _json

        mcp_config = read_settings(mcp_config_path)
        mcp_servers = mcp_config.get("mcpServers")
        if not isinstance(mcp_servers, dict):
            return result

        removed_keys = [key for key in list(mcp_servers) if key in _managed_mcp_server_keys()]
        if not removed_keys:
            for path in (
                target_dir / "commands",
                target_dir / "agents",
                target_dir / "hooks",
                target_dir / "cache",
                target_dir,
            ):
                prune_empty_ancestors(path, stop_at=target_dir.parent)
            return result

        for key in removed_keys:
            del mcp_servers[key]
        if not mcp_servers:
            del mcp_config["mcpServers"]

        mcp_config_path.write_text(_json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")
        result["removed"].append("MCP servers from .claude.json")
        if remove_empty_json_object_file(mcp_config_path):
            result["removed"].append(mcp_config_path.name)
        for path in (
            target_dir / "commands",
            target_dir / "agents",
            target_dir / "hooks",
            target_dir / "cache",
            target_dir,
        ):
            prune_empty_ancestors(path, stop_at=target_dir.parent)
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
    body_tool_reference_map: dict[str, str] | None = None,
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
        if body_tool_reference_map is None:
            from gpd.adapters import get_adapter

            body_tool_reference_map = get_adapter(runtime).tool_reference_translation_map()
        content = convert_tool_references_in_body(content, body_tool_reference_map)
        (agents_dest / agent_md.name).write_text(content, encoding="utf-8")
        new_agent_names.add(agent_md.name)

    remove_stale_agents(agents_dest, new_agent_names)


def _rewrite_gpd_cli_invocations(content: str, command: str) -> str:
    """Rewrite shell-command ``gpd`` invocations to the shared CLI bridge.

    Restrict rewrites to fenced shell code blocks and only when ``gpd`` appears
    in a command position. This keeps model-visible prose and inline code spans
    canonical while still pinning runnable shell steps to the runtime bridge.
    """
    return rewrite_gpd_cli_invocations_to_runtime_bridge(
        content,
        command,
        shell_fence_languages=DEFAULT_RUNTIME_BRIDGE_SHELL_FENCE_LANGUAGES,
    )


def _render_claude_command_markdown(content: str, *, bridge_command: str) -> str:
    """Render one canonical command markdown source into Claude Code command content."""
    return _rewrite_gpd_cli_invocations(content, bridge_command)


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


def _build_managed_mcp_servers(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Return shared MCP servers plus configured optional integrations."""
    from gpd.mcp.builtin_servers import build_mcp_servers_dict

    python_path = hook_python_interpreter()
    servers = build_mcp_servers_dict(python_path=python_path)
    servers.update(_build_managed_optional_mcp_servers(cwd=cwd, env=env, python_path=python_path))
    return servers


def _build_managed_optional_mcp_servers(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    python_path: str | None = None,
) -> dict[str, dict[str, object]]:
    """Return optional managed MCP servers that are currently configured."""
    python_path = python_path or hook_python_interpreter()
    return _managed_integrations.projected_managed_optional_mcp_servers(env, cwd=cwd, python_path=python_path)


def _managed_mcp_server_keys() -> frozenset[str]:
    """Return MCP server keys owned by GPD or managed optional integrations."""
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

    return frozenset(set(GPD_MCP_SERVER_KEYS) | set(_managed_integrations.managed_optional_mcp_server_keys()))


__all__ = ["ClaudeCodeAdapter"]
