"""Tests for the Claude Code runtime adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from gpd.adapters.claude_code import ClaudeCodeAdapter
from gpd.version import __version__


@pytest.fixture()
def adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


class TestProperties:
    """Test adapter properties match expected values."""

    def test_runtime_name(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.runtime_name == "claude-code"

    def test_display_name(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.display_name == "Claude Code"

    def test_config_dir_name(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.config_dir_name == ".claude"

    def test_help_command(self, adapter: ClaudeCodeAdapter) -> None:
        assert adapter.help_command == "/gpd:help"


class TestInstall:
    """Test full install flow."""

    def test_install_creates_all_dirs(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        assert (target / "commands" / "gpd").is_dir()
        assert (target / "get-physics-done").is_dir()
        assert (target / "agents").is_dir()
        assert (target / "hooks").is_dir()
        assert (target / "gpd-file-manifest.json").exists()
        # settings.json is written by finish_install(), not install()
        # install() returns the settings dict for the caller to pass to finish_install()

    def test_install_commands_have_placeholder_replacement(
        self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        # Find help.md in commands/gpd/
        help_file = target / "commands" / "gpd" / "help.md"
        assert help_file.exists()
        content = help_file.read_text(encoding="utf-8")
        assert "{GPD_INSTALL_DIR}" not in content

    def test_install_agents_have_placeholder_replacement(
        self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        agent_files = list((target / "agents").glob("gpd-*.md"))
        assert len(agent_files) >= 2
        for agent_file in agent_files:
            content = agent_file.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content

    def test_install_writes_version(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        version_file = target / "get-physics-done" / "VERSION"
        assert version_file.exists()
        assert version_file.read_text(encoding="utf-8") == __version__

    def test_install_copies_hooks(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        assert (target / "hooks" / "statusline.py").exists()
        assert (target / "hooks" / "check_update.py").exists()

    def test_install_returns_summary(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        result = adapter.install(gpd_root, target)

        assert result["runtime"] == "claude-code"
        assert isinstance(result["commands"], int)
        assert isinstance(result["agents"], int)
        assert result["commands"] > 0
        assert result["agents"] > 0

    def test_install_configures_update_hook(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        result = adapter.install(gpd_root, target)

        # install() returns settings with hooks configured (not yet written to disk)
        settings = result["settings"]
        hooks = settings.get("hooks", {})
        session_start = hooks.get("SessionStart", [])
        assert len(session_start) > 0
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert any("check_update" in c for c in cmds)

    def test_update_command_translates_allowed_tools_for_claude(
        self,
        adapter: ClaudeCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        content = (target / "commands" / "gpd" / "update.md").read_text(encoding="utf-8")
        assert "allowed-tools:" in content
        assert "  - Bash" in content
        assert "  - AskUserQuestion" in content
        assert "  - shell" not in content

    def test_install_preserves_jsonc_settings_and_uses_current_interpreter(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        (target / "settings.json").write_text(
            '{\n  // keep user settings\n  "theme": "solarized",\n}\n',
            encoding="utf-8",
        )
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")

        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["theme"] == "solarized"
        assert settings["statusLine"]["command"] == "/custom/venv/bin/python .claude/hooks/statusline.py"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert "/custom/venv/bin/python .claude/hooks/check_update.py" in cmds

    def test_reinstall_rewrites_stale_managed_update_hook(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {"hooks": [{"type": "command", "command": "python3 .claude/hooks/check_update.py"}]},
                            {"hooks": [{"type": "command", "command": "python3 .claude/hooks/check_update.py"}]},
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")

        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert cmds.count("/custom/venv/bin/python .claude/hooks/check_update.py") == 1
        assert "python3 .claude/hooks/check_update.py" not in cmds

    def test_install_with_explicit_target_uses_absolute_hook_paths(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "custom-claude"
        target.mkdir(parents=True)

        result = adapter.install(gpd_root, target, is_global=False, explicit_target=True)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["statusLine"]["command"] == f"{sys.executable or 'python3'} {(target / 'hooks' / 'statusline.py')}"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert f"{sys.executable or 'python3'} {(target / 'hooks' / 'check_update.py')}" in cmds

    def test_install_preserves_existing_mcp_overrides(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        target = tmp_path / "workspace" / ".claude"
        target.mkdir(parents=True)
        mcp_config = target.parent / ".mcp.json"
        mcp_config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gpd-state": {
                            "command": "python3",
                            "args": ["-m", "old.state_server"],
                            "env": {"LOG_LEVEL": "INFO", "EXTRA_FLAG": "1"},
                            "cwd": "/tmp/custom-gpd",
                            "type": "stdio",
                        },
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        adapter.install(gpd_root, target)

        parsed = json.loads(mcp_config.read_text(encoding="utf-8"))
        expected = build_mcp_servers_dict(python_path=sys.executable)["gpd-state"]
        server = parsed["mcpServers"]["gpd-state"]
        assert server["command"] == expected["command"]
        assert server["args"] == expected["args"]
        assert server["env"]["LOG_LEVEL"] == "INFO"
        assert server["env"]["EXTRA_FLAG"] == "1"
        assert server["cwd"] == "/tmp/custom-gpd"
        assert server["type"] == "stdio"
        assert parsed["mcpServers"]["custom-server"] == {"command": "node", "args": ["custom.js"]}

    def test_install_raises_on_missing_dirs(self, adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
        bad_root = tmp_path / "empty"
        bad_root.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        with pytest.raises(FileNotFoundError, match="Package integrity"):
            adapter.install(bad_root, target)

    def test_install_gpd_content_has_subdirs(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        gpd_dest = target / "get-physics-done"
        for subdir in ("references", "templates", "workflows"):
            assert (gpd_dest / subdir).is_dir(), f"Missing {subdir}/"

    def test_install_removes_stale_agents(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        # Pre-create a stale agent
        agents_dir = target / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "gpd-old-agent.md").write_text("stale", encoding="utf-8")
        # Non-GPD agent should survive
        (agents_dir / "custom-agent.md").write_text("keep", encoding="utf-8")

        adapter.install(gpd_root, target)

        assert not (agents_dir / "gpd-old-agent.md").exists()
        assert (agents_dir / "custom-agent.md").exists()


class TestUninstall:
    """Test uninstall cleans up GPD artifacts."""

    def test_uninstall_removes_gpd_dirs(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        result = adapter.uninstall(target)

        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()
        assert not (target / "gpd-file-manifest.json").exists()
        assert "removed" in result

    def test_global_uninstall_removes_mcp_servers_from_claude_json(
        self,
        adapter: ClaudeCodeAdapter,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(target))

        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        claude_json = tmp_path / ".claude.json"
        claude_json.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        **build_mcp_servers_dict(python_path=sys.executable),
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                }
            ),
            encoding="utf-8",
        )

        result = adapter.uninstall(target)

        cleaned = json.loads(claude_json.read_text(encoding="utf-8"))
        assert "custom-server" in cleaned["mcpServers"]
        assert len(cleaned["mcpServers"]) == 1
        assert "MCP servers from .claude.json" in result["removed"]

    def test_global_uninstall_does_not_touch_workspace_mcp_config(
        self,
        adapter: ClaudeCodeAdapter,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(target))

        workspace_mcp = tmp_path / ".mcp.json"
        workspace_mcp.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gpd-state": {"command": "python", "args": ["-m", "gpd.mcp.servers.state_server"]},
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        claude_json = tmp_path / ".claude.json"
        claude_json.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gpd-state": {"command": "python", "args": ["-m", "gpd.mcp.servers.state_server"]},
                    }
                }
            ),
            encoding="utf-8",
        )

        result = adapter.uninstall(target)

        workspace_cleaned = json.loads(workspace_mcp.read_text(encoding="utf-8"))
        assert "gpd-state" in workspace_cleaned["mcpServers"]
        assert "custom-server" in workspace_cleaned["mcpServers"]
        assert "MCP servers from .mcp.json" not in result["removed"]

    def test_local_uninstall_cleans_jsonc_workspace_mcp_config(self, adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
        target = tmp_path / "workspace" / ".claude"
        target.mkdir(parents=True)

        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_config = target.parent / ".mcp.json"
        mcp_config.write_text(
            (
                "{\n"
                "  // local workspace servers\n"
                '  "mcpServers": {\n'
                f'    "gpd-state": {json.dumps(build_mcp_servers_dict(python_path=sys.executable)["gpd-state"])},\n'
                '    "custom-server": {"command": "node", "args": ["custom.js"]},\n'
                "  },\n"
                "}\n"
            ),
            encoding="utf-8",
        )

        result = adapter.uninstall(target)

        cleaned = json.loads(mcp_config.read_text(encoding="utf-8"))
        assert "gpd-state" not in cleaned["mcpServers"]
        assert cleaned["mcpServers"] == {"custom-server": {"command": "node", "args": ["custom.js"]}}
        assert "MCP servers from .mcp.json" in result["removed"]

    def test_uninstall_removes_gpd_agents_only(
        self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        # Add a non-GPD agent
        (target / "agents" / "custom-agent.md").write_text("keep", encoding="utf-8")

        adapter.uninstall(target)

        assert not any(f.name.startswith("gpd-") for f in (target / "agents").iterdir())
        assert (target / "agents" / "custom-agent.md").exists()

    def test_uninstall_on_empty_dir(self, adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
        target = tmp_path / "empty"
        target.mkdir()
        result = adapter.uninstall(target)
        assert result["removed"] == []
