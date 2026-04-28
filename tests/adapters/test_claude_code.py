"""Tests for the Claude Code runtime adapter."""

from __future__ import annotations

import json
import os
import shlex
import shutil
from pathlib import Path

import pytest

from gpd.adapters.claude_code import ClaudeCodeAdapter
from gpd.adapters.install_utils import build_runtime_cli_bridge_command, hook_python_interpreter
from gpd.hooks.install_metadata import assess_install_target
from gpd.version import __version__, version_for_gpd_root
from tests.adapters.review_contract_test_utils import (
    assert_review_contract_prompt_surface,
    compile_review_contract_fixture_for_runtime,
)

WOLFRAM_MANAGED_SERVER_KEY = "gpd-wolfram"
WOLFRAM_MCP_API_KEY_ENV_VAR = "GPD_WOLFRAM_MCP_API_KEY"
WOLFRAM_MCP_ENDPOINT_ENV_VAR = "GPD_WOLFRAM_MCP_ENDPOINT"


@pytest.fixture()
def adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


def expected_claude_bridge(target: Path) -> str:
    return build_runtime_cli_bridge_command(
        "claude-code",
        target_dir=target,
        config_dir_name=".claude",
        is_global=False,
        explicit_target=False,
    )


def _assert_no_manifestless_gpd_artifacts(target: Path) -> None:
    assert not (target / "gpd-file-manifest.json").exists()
    assert not (target / "get-physics-done").exists()
    assert not (target / "commands" / "gpd").exists()
    assert not (target / "agents").exists()
    assert not (target / "hooks").exists()


def _make_checkout(tmp_path: Path, version: str) -> Path:
    """Create a minimal GPD source checkout with an explicit version."""
    repo_root = tmp_path / "checkout"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "get-physics-done",
                "version": version,
                "gpdPythonVersion": version,
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "get-physics-done"\nversion = "{version}"\n',
        encoding="utf-8",
    )

    gpd_root = repo_root / "src" / "gpd"
    (gpd_root / "commands").mkdir(parents=True, exist_ok=True)
    (gpd_root / "agents").mkdir(parents=True, exist_ok=True)
    (gpd_root / "hooks").mkdir(parents=True, exist_ok=True)
    for subdir in ("references", "templates", "workflows"):
        (gpd_root / "specs" / subdir).mkdir(parents=True, exist_ok=True)

    (gpd_root / "commands" / "help.md").write_text(
        "---\nname: gpd:help\ndescription: Help\n---\nHelp body.\n",
        encoding="utf-8",
    )
    (gpd_root / "agents" / "gpd-verifier.md").write_text(
        "---\nname: gpd-verifier\ndescription: Verify\n---\nVerifier body.\n",
        encoding="utf-8",
    )
    (gpd_root / "hooks" / "statusline.py").write_text("print('ok')\n", encoding="utf-8")
    (gpd_root / "hooks" / "check_update.py").write_text("print('ok')\n", encoding="utf-8")
    (gpd_root / "specs" / "references" / "ref.md").write_text("# references\n", encoding="utf-8")
    (gpd_root / "specs" / "templates" / "tpl.md").write_text("# templates\n", encoding="utf-8")
    (gpd_root / "specs" / "workflows" / "flow.md").write_text("# workflows\n", encoding="utf-8")
    return gpd_root


def _make_managed_home_python(tmp_path: Path) -> Path:
    managed_home = tmp_path / "managed-home"
    python_relpath = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    managed_python = managed_home / "venv" / python_relpath
    managed_python.parent.mkdir(parents=True, exist_ok=True)
    managed_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return managed_python


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

    def test_compile_markdown_prepends_review_contract_to_prompt(self) -> None:
        content = compile_review_contract_fixture_for_runtime("claude-code")

        assert_review_contract_prompt_surface(content)

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

    def test_install_completeness_requires_settings_json_after_finalize(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)

        adapter.install(gpd_root, target)

        assert adapter.missing_install_artifacts(target) == ("settings.json",)
        assert adapter.missing_install_verification_artifacts(target) == ()

    def test_install_completeness_requires_catalog_command_surface(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        shutil.rmtree(target / "commands" / "gpd")

        assert "commands/gpd" in adapter.missing_install_artifacts(target)

    def test_install_completeness_requires_catalog_agent_surface(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        shutil.rmtree(target / "agents")

        assert "agents/gpd-*.md" in adapter.missing_install_artifacts(target)

    def test_install_fails_closed_for_malformed_settings_json(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        settings_path = target / "settings.json"
        settings_path.write_text('{"hooks": [\n', encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert settings_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

    def test_install_fails_closed_for_structurally_invalid_settings_json(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        settings_path = target / "settings.json"
        settings_path.write_text(json.dumps({"hooks": []}), encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert settings_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

    def test_install_fails_closed_for_malformed_managed_mcp_config(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        mcp_config_path = target.parent / ".mcp.json"
        mcp_config_path.write_text('{"mcpServers": [\n', encoding="utf-8")
        before = mcp_config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert mcp_config_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

    def test_install_fails_closed_for_structurally_invalid_managed_mcp_config(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        mcp_config_path = target.parent / ".mcp.json"
        mcp_config_path.write_text(json.dumps({"mcpServers": []}), encoding="utf-8")
        before = mcp_config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert mcp_config_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

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
        assert "## Scientific Rigor Guardrails" in content

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
        assert version_file.read_text(encoding="utf-8") == (version_for_gpd_root(gpd_root) or __version__)

    def test_install_uses_checkout_version_over_runtime_metadata(
        self,
        adapter: ClaudeCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = _make_checkout(tmp_path, "9.9.9")
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)

        adapter.install(gpd_root, target)

        version_file = target / "get-physics-done" / "VERSION"
        assert version_file.read_text(encoding="utf-8") == "9.9.9"

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

    def test_install_rewrites_gpd_cli_calls_to_runtime_cli_bridge(
        self,
        adapter: ClaudeCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        expected_bridge = expected_claude_bridge(target)
        command = (target / "commands" / "gpd" / "settings.md").read_text(encoding="utf-8")
        workflow = (target / "get-physics-done" / "workflows" / "set-profile.md").read_text(encoding="utf-8")
        execute_phase = (target / "get-physics-done" / "workflows" / "execute-phase.md").read_text(encoding="utf-8")
        agent = (target / "agents" / "gpd-planner.md").read_text(encoding="utf-8")

        assert "`gpd convention set <key> <value>`" in command
        assert expected_bridge + " --raw init progress --include state,config" in workflow
        assert 'echo "ERROR: gpd initialization failed: $INIT"' in workflow
        assert f'if ! {expected_bridge} verify plan "$plan"; then' in execute_phase
        assert f'INIT=$({expected_bridge} --raw init plan-phase "${{PHASE}}")' in agent
        assert f"`{expected_bridge} convention set" not in command
        assert "gpd --raw init progress --include state,config" not in workflow
        assert 'if ! gpd verify plan "$plan"; then' not in execute_phase
        assert 'INIT=$(gpd --raw init plan-phase "${PHASE}")' not in agent

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

    def test_install_preserves_jsonc_settings_and_uses_managed_home_interpreter(
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
        managed_python = _make_managed_home_python(tmp_path)
        monkeypatch.delenv("GPD_PYTHON", raising=False)
        monkeypatch.setenv("GPD_HOME", str(tmp_path / "managed-home"))
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")
        monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

        selected_python = hook_python_interpreter()
        assert selected_python == str(managed_python)
        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["theme"] == "solarized"
        assert settings["statusLine"]["command"] == f"{shlex.quote(selected_python)} .claude/hooks/statusline.py"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert f"{shlex.quote(selected_python)} .claude/hooks/check_update.py" in cmds

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
        managed_python = _make_managed_home_python(tmp_path)
        monkeypatch.delenv("GPD_PYTHON", raising=False)
        monkeypatch.setenv("GPD_HOME", str(tmp_path / "managed-home"))
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")
        monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

        selected_python = hook_python_interpreter()
        assert selected_python == str(managed_python)
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
        assert cmds.count(f"{shlex.quote(selected_python)} .claude/hooks/check_update.py") == 1
        assert "python3 .claude/hooks/check_update.py" not in cmds

    def test_install_preserves_non_gpd_check_update_hook(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {"hooks": [{"type": "command", "command": "python3 /tmp/third-party/check_update.py"}]}
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)
        session_start = result["settings"].get("hooks", {}).get("SessionStart", [])
        commands = [
            hook["command"]
            for entry in session_start
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and isinstance(hook.get("command"), str)
        ]

        assert "python3 /tmp/third-party/check_update.py" in commands
        assert any(command.endswith(".claude/hooks/check_update.py") for command in commands)

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
        hook_python = hook_python_interpreter()
        expected_statusline_path = str(target / "hooks" / "statusline.py").replace("\\", "/")
        assert settings["statusLine"]["command"] == f"{shlex.quote(hook_python)} {expected_statusline_path}"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        expected_check_update_path = str(target / "hooks" / "check_update.py").replace("\\", "/")
        expected_check_update_cmd = f"{shlex.quote(hook_python)} {expected_check_update_path}"
        assert expected_check_update_cmd in cmds

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
        hook_python = hook_python_interpreter()
        expected = build_mcp_servers_dict(python_path=hook_python)["gpd-state"]
        server = parsed["mcpServers"]["gpd-state"]
        assert server["command"] == expected["command"]
        assert server["args"] == expected["args"]
        assert server["env"]["LOG_LEVEL"] == "INFO"
        assert server["env"]["EXTRA_FLAG"] == "1"
        assert server["cwd"] == "/tmp/custom-gpd"
        assert server["type"] == "stdio"
        assert parsed["mcpServers"]["custom-server"] == {"command": "node", "args": ["custom.js"]}

    def test_install_projects_wolfram_mcp_server_and_preserves_overrides(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        target = tmp_path / "workspace" / ".claude"
        target.mkdir(parents=True)
        mcp_config = target.parent / ".mcp.json"
        mcp_config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        WOLFRAM_MANAGED_SERVER_KEY: {
                            "command": "python3",
                            "args": ["-m", "legacy.wolfram"],
                            "cwd": "/tmp/custom-wolfram",
                            "type": "stdio",
                            "env": {"EXTRA_FLAG": "1"},
                        },
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv(WOLFRAM_MCP_API_KEY_ENV_VAR, "claude-test-key")
        monkeypatch.setenv(WOLFRAM_MCP_ENDPOINT_ENV_VAR, "https://example.invalid/api/mcp")

        result = adapter.install(gpd_root, target)

        parsed = json.loads(mcp_config.read_text(encoding="utf-8"))
        server = parsed["mcpServers"][WOLFRAM_MANAGED_SERVER_KEY]
        assert server["command"] == hook_python_interpreter()
        assert server["args"] == ["-m", "gpd.mcp.integrations.wolfram_bridge"]
        assert server["cwd"] == "/tmp/custom-wolfram"
        assert server["type"] == "stdio"
        assert server["env"] == {
            "EXTRA_FLAG": "1",
            WOLFRAM_MCP_ENDPOINT_ENV_VAR: "https://example.invalid/api/mcp",
        }
        assert parsed["mcpServers"]["custom-server"] == {"command": "node", "args": ["custom.js"]}
        assert "claude-test-key" not in mcp_config.read_text(encoding="utf-8")
        assert result["mcpServers"] == len(build_mcp_servers_dict(python_path=hook_python_interpreter())) + 1

    def test_install_omits_managed_wolfram_when_project_override_disables_it(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "integrations.json").write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")
        monkeypatch.setenv(WOLFRAM_MCP_API_KEY_ENV_VAR, "claude-test-key")

        adapter.install(gpd_root, target)

        parsed = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
        assert WOLFRAM_MANAGED_SERVER_KEY not in parsed.get("mcpServers", {})

    def test_install_translates_tool_references_in_agent_body(
        self,
        adapter: ClaudeCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = _make_checkout(tmp_path, "9.9.9")
        (gpd_root / "agents" / "gpd-body-checker.md").write_text(
            "---\n"
            "name: gpd-body-checker\n"
            "description: Check body translation\n"
            "allowed-tools:\n"
            "  - file_read\n"
            "  - shell\n"
            "---\n"
            "Use `file_read` to inspect the repo, then `shell` to run `gpd status`.\n"
            "If needed, ask_user and web_search before finishing.\n",
            encoding="utf-8",
        )

        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        body = (target / "agents" / "gpd-body-checker.md").read_text(encoding="utf-8").split("---", 2)[2]

        assert "file_read" not in body
        assert "shell" not in body
        assert "ask_user" not in body
        assert "web_search" not in body
        assert "Read" in body
        assert "Bash" in body
        assert "AskUserQuestion" in body
        assert "WebSearch" in body

    def test_global_install_scopes_claude_json_to_target_parent(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        target = tmp_path / "custom-root" / ".claude"
        target.mkdir(parents=True)

        adapter.install(gpd_root, target, is_global=True)

        scoped_claude_json = target.parent / ".claude.json"
        assert scoped_claude_json.exists()
        assert not (fake_home / ".claude.json").exists()

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

    def test_install_agents_replace_runtime_placeholders(
        self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """Assert _copy_agents_native passes runtime='claude-code' to replace_placeholders."""
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        verifier = (target / "agents" / "gpd-verifier.md").read_text(encoding="utf-8")
        assert "{GPD_CONFIG_DIR}" not in verifier
        assert "{GPD_RUNTIME_FLAG}" not in verifier
        assert "--claude" in verifier

    def test_install_translates_agent_frontmatter_tool_names(
        self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """Agent tool names must be translated to runtime-native names at install time.

        Claude Code may run subagents with explicit tools in a restricted
        sandbox; untranslated canonical names like ``file_write`` can cause
        silent write failures.
        """
        (gpd_root / "agents" / "gpd-tools-test.md").write_text(
            "---\nname: gpd-tools-test\ndescription: Tool name test\n"
            "tools: file_read, file_write, file_edit, shell, search_files, find_files\n"
            "---\nBody text.\n",
            encoding="utf-8",
        )
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        installed = (target / "agents" / "gpd-tools-test.md").read_text(encoding="utf-8")
        assert "file_read" not in installed
        assert "file_write" not in installed
        assert "file_edit" not in installed
        assert "Read" in installed
        assert "Write" in installed
        assert "Edit" in installed
        assert "Bash" in installed
        assert "Grep" in installed
        assert "Glob" in installed

    def test_install_preserves_shell_placeholders_for_claude_agents(
        self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        (gpd_root / "agents" / "gpd-shell-vars.md").write_text(
            "---\nname: gpd-shell-vars\ndescription: shell vars\n---\n"
            "Use ${PHASE_ARG} and $ARGUMENTS in prose.\n"
            'Inspect with `file_read("$artifact_path")`.\n'
            "```bash\n"
            'echo "$phase_dir" "$file"\n'
            "```\n"
            "Math stays $T$.\n",
            encoding="utf-8",
        )
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        checker = (target / "agents" / "gpd-shell-vars.md").read_text(encoding="utf-8")
        assert "Use ${PHASE_ARG} and $ARGUMENTS in prose." in checker
        assert "$artifact_path" in checker
        assert 'echo "$phase_dir" "$file"' in checker
        assert "Math stays $T$." in checker


class TestRuntimePermissions:
    def test_runtime_permissions_status_marks_yolo_as_relaunch_required(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.sync_runtime_permissions(target, autonomy="yolo")

        status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert status["config_aligned"] is True
        assert status["requires_relaunch"] is True
        assert "Restart the Claude Code session" in str(status["next_step"])

    def test_sync_runtime_permissions_yolo_sets_bypass_permissions(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        adapter.install(gpd_root, target)

        result = adapter.sync_runtime_permissions(target, autonomy="yolo")

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))

        assert settings["permissions"]["defaultMode"] == "bypassPermissions"
        assert manifest["gpd_runtime_permissions"]["mode"] == "yolo"
        assert result["sync_applied"] is True
        assert result["requires_relaunch"] is True

    def test_sync_runtime_permissions_restores_prior_claude_mode(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps({"permissions": {"defaultMode": "acceptEdits"}}, indent=2) + "\n",
            encoding="utf-8",
        )
        adapter.install(gpd_root, target)

        adapter.sync_runtime_permissions(target, autonomy="yolo")
        result = adapter.sync_runtime_permissions(target, autonomy="balanced")

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))

        assert settings["permissions"]["defaultMode"] == "acceptEdits"
        assert "gpd_runtime_permissions" not in manifest
        assert result["sync_applied"] is True

    def test_malformed_settings_json_fails_closed_for_status_and_sync(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        adapter.install(gpd_root, target)

        settings_path = target / "settings.json"
        settings_path.write_text('{"permissions": [\n', encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        status = adapter.runtime_permissions_status(target, autonomy="yolo")
        result = adapter.sync_runtime_permissions(target, autonomy="yolo")

        assert status["config_valid"] is False
        assert status["configured_mode"] == "malformed"
        assert status["config_aligned"] is False
        assert "malformed" in str(status["message"]).lower()
        assert result["config_valid"] is False
        assert result["changed"] is False
        assert result["sync_applied"] is False
        assert result["requires_relaunch"] is False
        assert "malformed" in str(result["warning"]).lower()
        assert settings_path.read_text(encoding="utf-8") == before

    def test_finalize_install_fails_closed_for_malformed_settings_json(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        settings_path = target / "settings.json"
        settings_path.write_text('{"permissions": [\n', encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.finalize_install(result)

        assert settings_path.read_text(encoding="utf-8") == before
        assessment = assess_install_target(target, expected_runtime=adapter.runtime_name)
        assert assessment.state == "owned_incomplete"
        assert "settings.json" in assessment.missing_install_artifacts

    @pytest.mark.parametrize("missing_field", ["settingsPath", "settings", "statuslineCommand"])
    def test_finalize_install_fails_closed_for_missing_deferred_payload_field(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        missing_field: str,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        result.pop(missing_field)

        with pytest.raises(RuntimeError, match="deferred install result is malformed"):
            adapter.finalize_install(result)

        assert not (target / "settings.json").exists()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("settingsPath", ["settings.json"]),
            ("settings", []),
            ("settings", {"hooks": []}),
            ("statuslineCommand", 123),
            ("shouldInstallStatusline", "yes"),
        ],
    )
    def test_finalize_install_fails_closed_for_invalid_deferred_payload_field(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        field: str,
        value: object,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        result[field] = value

        with pytest.raises(RuntimeError, match="deferred install result is malformed"):
            adapter.finalize_install(result)

        assert not (target / "settings.json").exists()

    def test_finalize_install_fails_closed_for_structurally_invalid_settings_json(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        settings_path = target / "settings.json"
        settings_path.write_text(json.dumps({"permissions": []}), encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.finalize_install(result)

        assert settings_path.read_text(encoding="utf-8") == before
        assessment = assess_install_target(target, expected_runtime=adapter.runtime_name)
        assert assessment.state == "owned_incomplete"
        assert "settings.json" in assessment.missing_install_artifacts


class TestUninstall:
    """Test uninstall cleans up GPD artifacts."""

    def test_uninstall_removes_gpd_dirs(self, adapter: ClaudeCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / "target" / ".claude"
        target.mkdir(parents=True)
        adapter.install(gpd_root, target)

        result = adapter.uninstall(target)

        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()
        assert not (target / "get-physics-done" / "bin" / "gpd").exists()
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
                        **build_mcp_servers_dict(python_path=hook_python_interpreter()),
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

    def test_local_uninstall_cleans_jsonc_workspace_mcp_config(
        self, adapter: ClaudeCodeAdapter, tmp_path: Path
    ) -> None:
        target = tmp_path / "workspace" / ".claude"
        target.mkdir(parents=True)

        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_config = target.parent / ".mcp.json"
        mcp_config.write_text(
            (
                "{\n"
                "  // local workspace servers\n"
                '  "mcpServers": {\n'
                f'    "gpd-state": {json.dumps(build_mcp_servers_dict(python_path=hook_python_interpreter())["gpd-state"])},\n'
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

    def test_local_uninstall_removes_wolfram_mcp_server_from_workspace_mcp_config(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "workspace" / ".claude"
        target.mkdir(parents=True)
        mcp_config = target.parent / ".mcp.json"
        mcp_config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        WOLFRAM_MANAGED_SERVER_KEY: {
                            "command": "python3",
                            "args": ["-m", "legacy.wolfram"],
                            "cwd": "/tmp/custom-wolfram",
                        },
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setenv(WOLFRAM_MCP_API_KEY_ENV_VAR, "claude-test-key")

        adapter.install(gpd_root, target)
        result = adapter.uninstall(target)

        cleaned = json.loads(mcp_config.read_text(encoding="utf-8"))
        assert WOLFRAM_MANAGED_SERVER_KEY not in cleaned["mcpServers"]
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

    def test_uninstall_preserves_non_gpd_sessionstart_statusline_hook(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings_path = target / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings.setdefault("hooks", {}).setdefault("SessionStart", []).append(
            {"hooks": [{"type": "command", "command": "python3 /tmp/third-party-statusline.py"}]}
        )
        settings["statusLine"] = {"type": "command", "command": "python3 /tmp/third-party-statusline.py"}
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
        assert cleaned["statusLine"]["command"] == "python3 /tmp/third-party-statusline.py"
        session_start = cleaned.get("hooks", {}).get("SessionStart", [])
        commands = [
            hook["command"]
            for entry in session_start
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and isinstance(hook.get("command"), str)
        ]
        assert "python3 /tmp/third-party-statusline.py" in commands

    def test_uninstall_preserves_third_party_hooks_inside_hooks_dirs(
        self,
        adapter: ClaudeCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".claude"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings_path = target / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["statusLine"] = {"type": "command", "command": "python3 /tmp/third-party/hooks/statusline.py"}
        session_start = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
        session_start.append(
            {"hooks": [{"type": "command", "command": "python3 /tmp/third-party/hooks/check_update.py"}]}
        )
        session_start.append({"hooks": [{"type": "command", "command": "python3 .claude/hooks/check_update.py"}]})
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
        assert cleaned["statusLine"]["command"] == "python3 /tmp/third-party/hooks/statusline.py"
        session_start = cleaned.get("hooks", {}).get("SessionStart", [])
        commands = [
            hook["command"]
            for entry in session_start
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and isinstance(hook.get("command"), str)
        ]
        assert "python3 /tmp/third-party/hooks/check_update.py" in commands
        assert "python3 .claude/hooks/check_update.py" not in commands
