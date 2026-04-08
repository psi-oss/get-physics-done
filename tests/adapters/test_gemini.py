"""Tests for the Gemini CLI runtime adapter."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from gpd.adapters.gemini import (
    _GEMINI_APPROVED_CONTRACT_PATH,
    GeminiAdapter,
    _convert_frontmatter_to_gemini,
    _convert_gemini_tool_name,
    _convert_to_gemini_toml,
    _render_gemini_policy_toml,
    _rewrite_gemini_shell_workflow_guidance,
    _rewrite_gpd_cli_invocations,
)
from gpd.adapters.install_utils import build_runtime_cli_bridge_command, hook_python_interpreter
from tests.adapters.review_contract_test_utils import (
    assert_review_contract_prompt_surface,
    compile_review_contract_fixture_for_runtime,
)


def expected_gemini_bridge(target: Path) -> str:
    return build_runtime_cli_bridge_command(
        "gemini",
        target_dir=target,
        config_dir_name=".gemini",
        is_global=False,
        explicit_target=False,
    )


def _make_managed_home_python(tmp_path: Path) -> Path:
    managed_home = tmp_path / "managed-home"
    python_relpath = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    managed_python = managed_home / "venv" / python_relpath
    managed_python.parent.mkdir(parents=True, exist_ok=True)
    managed_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return managed_python


@pytest.fixture()
def adapter() -> GeminiAdapter:
    return GeminiAdapter()


class TestProperties:
    def test_runtime_name(self, adapter: GeminiAdapter) -> None:
        assert adapter.runtime_name == "gemini"

    def test_display_name(self, adapter: GeminiAdapter) -> None:
        assert adapter.display_name == "Gemini CLI"

    def test_config_dir_name(self, adapter: GeminiAdapter) -> None:
        assert adapter.config_dir_name == ".gemini"

    def test_help_command(self, adapter: GeminiAdapter) -> None:
        assert adapter.help_command == "/gpd:help"


class TestConvertGeminiToolName:
    def test_known_mappings(self) -> None:
        assert _convert_gemini_tool_name("Read") == "read_file"
        assert _convert_gemini_tool_name("Bash") == "run_shell_command"
        assert _convert_gemini_tool_name("Grep") == "search_file_content"
        assert _convert_gemini_tool_name("WebSearch") == "google_web_search"

    def test_task_excluded(self) -> None:
        assert _convert_gemini_tool_name("Task") is None

    def test_mcp_excluded(self) -> None:
        assert _convert_gemini_tool_name("mcp__physics") is None

    def test_unknown_passthrough(self) -> None:
        assert _convert_gemini_tool_name("CustomTool") == "CustomTool"


class TestConvertFrontmatterToGemini:
    def test_no_frontmatter_passthrough(self) -> None:
        content = "Just body text"
        assert _convert_frontmatter_to_gemini(content) == content

    def test_color_stripped(self) -> None:
        content = "---\nname: test\ncolor: green\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "color:" not in result
        assert "name: test" in result

    def test_only_gemini_supported_agent_frontmatter_is_preserved(self) -> None:
        content = (
            "---\n"
            "name: test\n"
            "description: A test agent\n"
            "display_name: Test Agent\n"
            "commit_authority: orchestrator\n"
            "surface: internal\n"
            "role_family: analysis\n"
            "artifact_write_authority: scoped_write\n"
            "shared_state_authority: return_only\n"
            "model: gemini-2.5-pro\n"
            "temperature: 0.2\n"
            "max_turns: 5\n"
            "timeout_mins: 10\n"
            "---\n"
            "Body"
        )
        result = _convert_frontmatter_to_gemini(content)
        assert "name: test" in result
        assert "description: A test agent" in result
        assert "display_name: Test Agent" in result
        assert "model: gemini-2.5-pro" in result
        assert "temperature: 0.2" in result
        assert "max_turns: 5" in result
        assert "timeout_mins: 10" in result
        assert "commit_authority:" not in result
        assert "surface:" not in result
        assert "role_family:" not in result
        assert "artifact_write_authority:" not in result
        assert "shared_state_authority:" not in result

    def test_remote_agent_fields_are_preserved(self) -> None:
        content = (
            "---\n"
            "kind: remote\n"
            "name: test-remote\n"
            "description: Remote test agent\n"
            "agent_card_url: https://example.com/agent-card\n"
            "auth:\n"
            "  type: apiKey\n"
            "  key: secret-token\n"
            "---\n"
            "Body"
        )
        result = _convert_frontmatter_to_gemini(content)
        assert "kind: remote" in result
        assert "name: test-remote" in result
        assert "description: Remote test agent" in result
        assert "agent_card_url: https://example.com/agent-card" in result
        assert "auth:" in result
        assert "type: apiKey" in result
        assert "key: secret-token" in result

    def test_allowed_tools_to_tools_array(self) -> None:
        content = "---\nname: test\nallowed-tools:\n  - Read\n  - Bash\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "tools:" in result
        assert "read_file" in result
        assert "run_shell_command" in result
        assert "allowed-tools:" not in result

    def test_mcp_tools_excluded(self) -> None:
        content = "---\nname: test\nallowed-tools:\n  - Read\n  - mcp__physics\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "mcp__physics" not in result
        assert "read_file" in result

    def test_sub_tags_stripped(self) -> None:
        content = "---\nname: test\n---\nText with <sub>subscript</sub> here"
        result = _convert_frontmatter_to_gemini(content)
        assert "<sub>" not in result
        assert "*(subscript)*" in result

    def test_inline_tools_field(self) -> None:
        content = "---\nname: test\ntools: Read, Write, Bash\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "read_file" in result
        assert "write_file" in result
        assert "run_shell_command" in result

    def test_task_excluded_from_tools(self) -> None:
        content = "---\nname: test\nallowed-tools:\n  - Read\n  - Task\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "Task" not in result.split("---", 2)[1] if result.count("---") >= 2 else True

    def test_sub_tags_stripped_without_frontmatter(self) -> None:
        """Regression: <sub> tags must be stripped even when there is no frontmatter."""
        content = "Text with <sub>subscript</sub> here"
        result = _convert_frontmatter_to_gemini(content)
        assert "<sub>" not in result
        assert "*(subscript)*" in result

    def test_sub_tags_stripped_with_unclosed_frontmatter(self) -> None:
        """Regression: <sub> tags stripped even with malformed (unclosed) frontmatter."""
        content = "---\nname: test\nText with <sub>subscript</sub> here"
        result = _convert_frontmatter_to_gemini(content)
        assert "<sub>" not in result
        assert "*(subscript)*" in result

    def test_duplicate_tools_deduplicated(self) -> None:
        """Regression: tools appearing in both tools: and allowed-tools: are deduplicated."""
        content = "---\nname: test\ntools: Read, Write\nallowed-tools:\n  - Read\n  - Bash\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        # read_file should appear exactly once
        parts = result.split("---")
        frontmatter = parts[1] if len(parts) >= 3 else ""
        assert frontmatter.count("read_file") == 1

    def test_field_after_allowed_tools_preserved(self) -> None:
        """Non-array field following allowed-tools is preserved in output."""
        content = "---\nname: test\nallowed-tools:\n  - Read\n  - Bash\ndescription: A test\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "description: A test" in result
        assert "read_file" in result

    def test_description_with_triple_dash_is_preserved(self) -> None:
        content = "---\nname: test\ndescription: before --- after\nallowed-tools:\n  - Read\n---\nBody"
        result = _convert_frontmatter_to_gemini(content)
        assert "description: before --- after" in result
        assert "read_file" in result
        assert result.rstrip().endswith("Body")


class TestConvertToGeminiToml:
    def test_no_frontmatter(self) -> None:
        result = _convert_to_gemini_toml("Just a prompt body")
        assert "prompt" in result
        assert "Just a prompt body" in result
        assert "prompt = '''" in result

    def test_extracts_description(self) -> None:
        content = "---\nname: test\ndescription: My description\n---\nPrompt body"
        result = _convert_to_gemini_toml(content)
        assert 'description = "My description"' in result
        assert "Prompt body" in result

    def test_extracts_description_when_value_contains_triple_dash(self) -> None:
        content = "---\nname: test\ndescription: before --- after\n---\nPrompt body"
        result = _convert_to_gemini_toml(content)
        assert 'description = "before --- after"' in result
        assert "Prompt body" in result

    def test_extracts_context_mode(self) -> None:
        content = "---\nname: test\ncontext_mode: project-aware\n---\nPrompt body"
        result = _convert_to_gemini_toml(content)
        assert 'context_mode = "project-aware"' in result

    def test_preserves_project_reentry_capable_as_source_metadata_comment(self) -> None:
        content = (
            "---\n"
            "name: gpd:resume-work\n"
            "context_mode: project-required\n"
            "project_reentry_capable: true\n"
            "---\n"
            "Prompt body"
        )

        result = _convert_to_gemini_toml(content)

        assert 'context_mode = "project-required"' in result
        assert "# project_reentry_capable: true" in result
        assert "project_reentry_capable =" not in result

    def test_prepends_review_contract_to_prompt(self) -> None:
        content = compile_review_contract_fixture_for_runtime("gemini")

        result = _convert_to_gemini_toml(content)

        assert_review_contract_prompt_surface(result)

    def test_uses_multiline_literal_string(self) -> None:
        content = "---\ndescription: D\n---\nMultiline\nprompt"
        result = _convert_to_gemini_toml(content)
        assert "'''" in result

    def test_triple_quote_fallback(self) -> None:
        content = "---\ndescription: D\n---\nBody with ''' inside"
        result = _convert_to_gemini_toml(content)
        # Should fall back to JSON encoding (prompt = "Body with ''' inside")
        assert "prompt" in result
        # The prompt is JSON-encoded, not wrapped in '''
        assert "prompt = '''" not in result

    def test_no_frontmatter_with_non_bmp_unicode_uses_literal_prompt(self) -> None:
        result = _convert_to_gemini_toml("📄 Prompt body")

        assert "prompt = '''" in result
        assert "\\ud83d" not in result


class TestRewriteGeminiShellWorkflowGuidance:
    def test_rewrites_updated_set_profile_block_with_reentry_comment_and_flag(self) -> None:
        content = (
            "```bash\n"
            "gpd config ensure-section\n"
            "# Compatibility note for installer text checks:\n"
            "# INIT=$(gpd --raw init progress --include state,config)\n"
            "INIT=$(gpd --raw init progress --include state,config --no-project-reentry)\n"
            "if [ $? -ne 0 ]; then\n"
            '  echo "ERROR: gpd initialization failed: $INIT"\n'
            "  # STOP — display the error to the user and do not proceed.\n"
            "fi\n"
            "```"
        )

        result = _rewrite_gemini_shell_workflow_guidance(content)

        assert "Run these as separate shell calls in Gemini auto-edit mode." in result
        assert "gpd config ensure-section" in result
        assert "gpd --raw init progress --include state,config --no-project-reentry" in result
        assert "INIT=$(" not in result
        assert "if [ $? -ne 0 ]" not in result


class TestInstall:
    def test_install_creates_toml_commands(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        commands_dir = target / "commands" / "gpd"
        assert commands_dir.is_dir()
        toml_files = list(commands_dir.rglob("*.toml"))
        assert len(toml_files) > 0

    def test_update_command_inlines_workflow(self, adapter: GeminiAdapter, tmp_path: Path) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        content = (target / "commands" / "gpd" / "update.toml").read_text(encoding="utf-8")
        assert "Check for a newer GPD release" in content
        assert "<!-- [included: update.md] -->" in content
        assert re.search(r"^\s*@.*?/workflows/update\.md\s*$", content, flags=re.MULTILINE) is None

    def test_complete_milestone_command_inlines_bullet_list_includes(
        self,
        adapter: GeminiAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        content = (target / "commands" / "gpd" / "complete-milestone.toml").read_text(encoding="utf-8")
        assert "<!-- [included: complete-milestone.md] -->" in content
        assert "<!-- [included: milestone-archive.md] -->" in content
        assert "Mark a completed research stage" in content
        assert "# Milestone Archive Template" in content
        assert re.search(r"^\s*-\s*@.*?/workflows/complete-milestone\.md.*$", content, flags=re.MULTILINE) is None
        assert re.search(r"^\s*-\s*@.*?/templates/milestone-archive\.md.*$", content, flags=re.MULTILINE) is None

    def test_install_creates_agents(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        agent_files = list(agents_dir.glob("gpd-*.md"))
        assert len(agent_files) >= 2

    def test_install_agents_have_converted_frontmatter(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        for agent_file in (target / "agents").glob("gpd-*.md"):
            content = agent_file.read_text(encoding="utf-8")
            frontmatter = content
            if content.startswith("---\n"):
                _, frontmatter, _ = content.split("---\n", 2)
            assert "color:" not in content
            assert "allowed-tools:" not in content
            assert "commit_authority:" not in frontmatter
            assert "surface:" not in frontmatter
            assert "role_family:" not in frontmatter
            assert "artifact_write_authority:" not in frontmatter
            assert "shared_state_authority:" not in frontmatter

    def test_install_enables_experimental_agents(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings_on_disk = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        settings = result["settings"]
        assert settings.get("experimental", {}).get("enableAgents") is True
        assert settings_on_disk.get("experimental", {}).get("enableAgents") is True
        assert manifest["managed_config"]["experimental.enableAgents"] is True
        assert "tools.allowed" not in manifest["managed_config"]
        assert manifest["managed_config"]["policyPaths"] == [str((target / "policies").resolve())]
        assert sorted(manifest["managed_runtime_files"]) == ["policies/gpd-auto-edit.toml"]
        assert result["settingsWritten"] is True

    def test_install_does_not_claim_preexisting_experimental_agents(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps({"experimental": {"enableAgents": True}, "theme": "solarized"}) + "\n",
            encoding="utf-8",
        )

        adapter.install(gpd_root, target)

        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        assert "tools.allowed" not in manifest["managed_config"]
        assert manifest["managed_config"]["policyPaths"] == [str((target / "policies").resolve())]
        assert "experimental.enableAgents" not in manifest["managed_config"]

    def test_install_configures_update_hook(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = result["settings"]
        hooks = settings.get("hooks", {})
        session_start = hooks.get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert any("check_update" in c for c in cmds)
        persisted = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        persisted_cmds = [
            h.get("command", "")
            for entry in persisted.get("hooks", {}).get("SessionStart", [])
            for h in (entry.get("hooks") or [])
        ]
        assert any("check_update" in c for c in persisted_cmds)

    def test_install_preserves_jsonc_settings_and_uses_managed_home_interpreter(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
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
        assert settings["statusLine"]["command"] == f"{selected_python} .gemini/hooks/statusline.py"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert f"{selected_python} .gemini/hooks/check_update.py" in cmds

    def test_install_uses_gpd_python_override_for_hooks_and_mcp(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        monkeypatch.setenv("GPD_PYTHON", "/env/override/python")
        monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["statusLine"]["command"] == "/env/override/python .gemini/hooks/statusline.py"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert "/env/override/python .gemini/hooks/check_update.py" in cmds
        assert settings["mcpServers"]["gpd-state"]["command"] == "/env/override/python"

    def test_reinstall_rewrites_stale_managed_update_hook(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {"hooks": [{"type": "command", "command": "python3 .gemini/hooks/check_update.py"}]},
                            {"hooks": [{"type": "command", "command": "python3 .gemini/hooks/check_update.py"}]},
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
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert cmds.count(f"{selected_python} .gemini/hooks/check_update.py") == 1
        assert "python3 .gemini/hooks/check_update.py" not in cmds

    def test_install_preserves_non_gpd_check_update_hook(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "target" / ".gemini"
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
        settings = result["settings"]
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        commands = [
            hook["command"]
            for entry in session_start
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and isinstance(hook.get("command"), str)
        ]

        assert "python3 /tmp/third-party/check_update.py" in commands
        assert any(command.endswith(".gemini/hooks/check_update.py") for command in commands)

    def test_install_with_explicit_target_uses_absolute_hook_paths(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "custom-gemini"
        target.mkdir()

        result = adapter.install(gpd_root, target, is_global=False, explicit_target=True)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        hook_python = hook_python_interpreter()
        assert settings["statusLine"]["command"] == f"{hook_python} {(target / 'hooks' / 'statusline.py')}"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert f"{hook_python} {(target / 'hooks' / 'check_update.py')}" in cmds

    def test_install_preserves_existing_mcp_overrides(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        target = tmp_path / ".gemini"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gpd-state": {
                            "command": "python3",
                            "args": ["-m", "old.state_server"],
                            "env": {"LOG_LEVEL": "INFO", "EXTRA_FLAG": "1"},
                            "cwd": "/tmp/custom-gpd",
                            "timeout": 15000,
                        },
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        hook_python = hook_python_interpreter()
        expected = build_mcp_servers_dict(python_path=hook_python)["gpd-state"]
        server = settings["mcpServers"]["gpd-state"]
        assert server["command"] == expected["command"]
        assert server["args"] == expected["args"]
        assert server["env"]["LOG_LEVEL"] == "INFO"
        assert server["env"]["EXTRA_FLAG"] == "1"
        assert server["cwd"] == "/tmp/custom-gpd"
        assert server["timeout"] == 15000
        assert server["trust"] is True
        assert settings["mcpServers"]["custom-server"] == {"command": "node", "args": ["custom.js"]}

    def test_install_projects_managed_wolfram_mcp_without_secrets(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")
        monkeypatch.setenv("GPD_WOLFRAM_MCP_ENDPOINT", "https://example.invalid/api/mcp")

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        wolfram = settings["mcpServers"]["gpd-wolfram"]
        assert wolfram["command"] == "gpd-mcp-wolfram"
        assert wolfram["args"] == []
        assert wolfram["env"] == {"GPD_WOLFRAM_MCP_ENDPOINT": "https://example.invalid/api/mcp"}
        assert wolfram["trust"] is True
        assert "super-secret-token" not in json.dumps(wolfram)
        assert "GPD_WOLFRAM_MCP_API_KEY" not in json.dumps(wolfram)

    def test_install_preserves_existing_managed_wolfram_overrides(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")
        monkeypatch.setenv("GPD_WOLFRAM_MCP_ENDPOINT", "https://example.invalid/api/mcp")
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "gpd-wolfram": {
                            "command": "legacy-wolfram-bridge",
                            "args": ["--legacy"],
                            "env": {
                                "GPD_WOLFRAM_MCP_ENDPOINT": "https://custom.invalid/api/mcp",
                                "EXTRA_FLAG": "1",
                            },
                            "cwd": "/tmp/custom-wolfram",
                            "timeout": 15000,
                            "trust": False,
                        },
                        "custom-server": {"command": "node", "args": ["custom.js"]},
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        wolfram = settings["mcpServers"]["gpd-wolfram"]
        assert wolfram["command"] == "gpd-mcp-wolfram"
        assert wolfram["args"] == []
        assert wolfram["env"]["GPD_WOLFRAM_MCP_ENDPOINT"] == "https://custom.invalid/api/mcp"
        assert wolfram["env"]["EXTRA_FLAG"] == "1"
        assert wolfram["cwd"] == "/tmp/custom-wolfram"
        assert wolfram["timeout"] == 15000
        assert wolfram["trust"] is False
        assert "super-secret-token" not in json.dumps(wolfram)
        assert settings["mcpServers"]["custom-server"] == {"command": "node", "args": ["custom.js"]}

    def test_install_omits_managed_wolfram_when_project_override_disables_it(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "integrations.json").write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")
        monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert "gpd-wolfram" not in settings.get("mcpServers", {})

    def test_install_adds_policy_path_shell_sentinel_and_policy_file(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["policyPaths"] == [str((target / "policies").resolve())]
        assert "tools" not in settings or "allowed" not in settings.get("tools", {})

        policy_path = target / "policies" / "gpd-auto-edit.toml"
        assert policy_path.exists()
        policy = policy_path.read_text(encoding="utf-8")
        assert 'toolName = "run_shell_command"' in policy
        assert 'modes = ["autoEdit"]' in policy
        assert "allow_redirection = true" in policy
        assert expected_gemini_bridge(target) in policy
        assert '"git init"' in policy

    def test_install_surfaces_shell_prefix_allowlist_in_model_facing_content(
        self,
        adapter: GeminiAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".gemini"
        target.mkdir()

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        command = (target / "commands" / "gpd" / "new-project.toml").read_text(encoding="utf-8")
        expected_bridge = expected_gemini_bridge(target)

        assert "enforced shell-prefix allowlist" in command
        assert f"`{expected_bridge}`" in command
        assert "`git init`" in command
        assert "`mkdir -p GPD`" in command
        assert "`printf '%s\\n' \"$PROJECT_CONTRACT_JSON\"`" in command

    def test_install_preserves_existing_policy_paths_and_mcp_trust_choice(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        existing_policy_path = "/tmp/custom-policies"
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "policyPaths": [existing_policy_path],
                    "tools": {"allowed": ["write_file"]},
                    "mcpServers": {
                        "gpd-state": {
                            "command": "python3",
                            "args": ["-m", "old.state_server"],
                            "trust": False,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["policyPaths"] == [existing_policy_path, str((target / "policies").resolve())]
        assert settings["tools"]["allowed"] == ["write_file"]
        assert settings["mcpServers"]["gpd-state"]["trust"] is False

    def test_install_writes_manifest(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)
        assert (target / "gpd-file-manifest.json").exists()

    def test_install_returns_counts(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        assert result["runtime"] == "gemini"
        assert result["commands"] > 0
        assert result["agents"] > 0

    def test_install_gpd_content_placeholder_replaced(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        for md_file in (target / "get-physics-done").rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content

    def test_install_rewrites_gpd_cli_calls_to_runtime_cli_bridge(
        self,
        adapter: GeminiAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        expected_bridge = expected_gemini_bridge(target)
        command = (target / "commands" / "gpd" / "new-project.toml").read_text(encoding="utf-8")
        workflow = (target / "get-physics-done" / "workflows" / "new-project.md").read_text(encoding="utf-8")
        state_schema = (target / "get-physics-done" / "templates" / "state-json-schema.md").read_text(encoding="utf-8")

        assert f"When shell steps call the GPD CLI, use {expected_bridge}" in command
        assert "Run the init command as its own shell call in Gemini auto-edit mode." in workflow
        assert "INIT=$(gpd --raw init new-project)" not in workflow
        assert f'INIT=$({expected_bridge} --raw init new-project)' not in workflow
        assert f"{expected_bridge} --raw init new-project" in workflow
        assert f"{expected_bridge} commit " in workflow
        assert ' gpd commit "' not in workflow
        assert f"{expected_bridge} --raw validate project-contract {_GEMINI_APPROVED_CONTRACT_PATH}" in command
        assert f"{expected_bridge} state set-project-contract {_GEMINI_APPROVED_CONTRACT_PATH}" in command
        assert "PROJECT_CONTRACT_JSON" not in workflow
        assert "PROJECT_CONTRACT_JSON" not in state_schema
        assert "PRE_CHECK=$(" not in workflow
        assert f"{expected_bridge} --raw validate project-contract {_GEMINI_APPROVED_CONTRACT_PATH}" in workflow
        assert f"{expected_bridge} state set-project-contract {_GEMINI_APPROVED_CONTRACT_PATH}" in workflow
        assert f"{expected_bridge} --raw validate project-contract {_GEMINI_APPROVED_CONTRACT_PATH}" in state_schema
        assert f"{expected_bridge} state set-project-contract {_GEMINI_APPROVED_CONTRACT_PATH}" in state_schema

    def test_install_rewrites_set_profile_shell_block_for_gemini(
        self,
        adapter: GeminiAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        content = (target / "commands" / "gpd" / "set-profile.toml").read_text(encoding="utf-8")

        assert "Run these as separate shell calls in Gemini auto-edit mode." in content
        assert "Do not combine them into one multi-line shell block." in content
        assert "INIT=$(" not in content
        assert "if [ $? -ne 0 ]" not in content
        assert expected_gemini_bridge(target) + " config ensure-section" in content
        assert expected_gemini_bridge(target) + " --raw init progress --include state,config --no-project-reentry" in content


    def test_install_agents_replace_runtime_placeholders(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """Regression: _copy_agents_gemini must pass runtime='gemini' to replace_placeholders."""
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        verifier = (target / "agents" / "gpd-verifier.md").read_text(encoding="utf-8")
        assert "{GPD_CONFIG_DIR}" not in verifier
        assert "{GPD_RUNTIME_FLAG}" not in verifier
        assert "--gemini" in verifier

    def test_install_sanitizes_shell_placeholders_in_agents(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
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
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        checker = (target / "agents" / "gpd-shell-vars.md").read_text(encoding="utf-8")
        assert "${PHASE_ARG}" not in checker
        assert "$ARGUMENTS" not in checker
        assert "$phase_dir" not in checker
        assert "$file" not in checker
        assert "$artifact_path" not in checker
        assert "<PHASE_ARG>" in checker
        assert "<ARGUMENTS>" in checker
        assert "<phase_dir>" in checker
        assert "<file>" in checker
        assert "<artifact_path>" in checker
        assert "Math stays $T$." in checker

    def test_install_does_not_call_finalize_internally(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """install() must not call finalize_install internally.

        The CLI calls adapter.finalize_install(result, force_statusline=...)
        after install().  If install() already called finalize_install (without
        forwarding force_statusline), the CLI's call would see settingsWritten=True
        and return immediately, discarding the user's --force-statusline flag.
        """
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        # install() must NOT have written settings or set the settingsWritten flag
        assert result.get("settingsWritten") is not True
        assert not (target / "settings.json").exists()
        assert adapter.missing_install_artifacts(target) == ("settings.json",)

    def test_install_returns_before_finalize_but_runtime_completeness_stays_strict(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """Install-time verification must not hide missing finalize artifacts afterwards."""
        target = tmp_path / ".gemini"
        target.mkdir()

        adapter.install(gpd_root, target)

        missing = adapter.missing_install_artifacts(target)
        assert missing == ("settings.json",)
        assert adapter.missing_install_verification_artifacts(target) == ()

    def test_install_fails_closed_for_malformed_settings_json(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        settings_path = target / "settings.json"
        settings_path.write_text('{"hooks": [\n', encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert settings_path.read_text(encoding="utf-8") == before

    def test_install_fails_closed_for_structurally_invalid_settings_json(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        settings_path = target / "settings.json"
        settings_path.write_text(json.dumps({"mcpServers": []}), encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert settings_path.read_text(encoding="utf-8") == before

    def test_install_fails_closed_for_structurally_invalid_mcp_server_entry(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        settings_path = target / "settings.json"
        settings_path.write_text(json.dumps({"mcpServers": {"custom-server": []}}), encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert settings_path.read_text(encoding="utf-8") == before

    def test_reinstall_fails_closed_for_malformed_managed_config_manifest(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finalize_install(result)

        manifest_path = target / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["managed_config"] = ["broken"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        before = manifest_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="managed_config"):
            adapter.install(gpd_root, target)

        assert manifest_path.read_text(encoding="utf-8") == before

    def test_force_statusline_forwarded_through_finalize(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """force_statusline=True must override a pre-existing non-GPD statusline.

        Regression: previously install() called finalize_install internally
        without forwarding force_statusline, so the CLI's subsequent call
        with force_statusline=True was silently discarded.
        """
        target = tmp_path / ".gemini"
        target.mkdir()

        # Pre-populate settings with a non-GPD statusline
        (target / "settings.json").write_text(
            json.dumps({"statusLine": {"type": "command", "command": "other-tool --status"}}),
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)

        # Without force_statusline the existing statusline is preserved
        adapter.finalize_install(result, force_statusline=False)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["statusLine"]["command"] == "other-tool --status"

        # Reset settingsWritten so finalize_install runs again
        result.pop("settingsWritten", None)

        # With force_statusline the GPD statusline overwrites the existing one
        adapter.finalize_install(result, force_statusline=True)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert "statusline.py" in settings["statusLine"]["command"]

    def test_finalize_install_fails_closed_for_malformed_settings_json(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        settings_path = target / "settings.json"
        settings_path.write_text('{"hooks": [\n', encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.finalize_install(result)

        assert settings_path.read_text(encoding="utf-8") == before

    def test_finalize_install_fails_closed_for_structurally_invalid_settings_json(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        settings_path = target / "settings.json"
        settings_path.write_text(json.dumps({"policyPaths": {}}), encoding="utf-8")
        before = settings_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.finalize_install(result)

        assert settings_path.read_text(encoding="utf-8") == before

    def test_install_agents_at_includes_receive_runtime(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        """Regression: expand_at_includes in _copy_agents_gemini must receive runtime='gemini'.

        Agents with @ includes pointing at specs that contain {GPD_CONFIG_DIR}
        must have those placeholders replaced during include expansion.
        """
        # Create an agent that @-includes a spec with runtime placeholders
        agents_src = gpd_root / "agents"
        specs_dir = gpd_root / "specs" / "references"
        (specs_dir / "runtime-ref.md").write_text(
            "---\ndescription: ref\n---\nConfig: {GPD_CONFIG_DIR}\nFlag: {GPD_RUNTIME_FLAG}\n",
            encoding="utf-8",
        )
        (agents_src / "gpd-includer.md").write_text(
            "---\nname: gpd-includer\ndescription: test\n---\n"
            "@{GPD_INSTALL_DIR}/references/runtime-ref.md\n",
            encoding="utf-8",
        )

        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        includer = (target / "agents" / "gpd-includer.md").read_text(encoding="utf-8")
        assert "{GPD_CONFIG_DIR}" not in includer
        assert "{GPD_RUNTIME_FLAG}" not in includer
        assert "--gemini" in includer

    def test_install_agents_inline_gpd_agents_dir_includes(
        self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        agents_src = gpd_root / "agents"
        (agents_src / "gpd-shared.md").write_text(
            "---\nname: gpd-shared\ndescription: shared\nsurface: internal\nrole_family: coordination\n---\n"
            "Shared agent body.\n",
            encoding="utf-8",
        )
        (agents_src / "gpd-main.md").write_text(
            "---\nname: gpd-main\ndescription: main\nsurface: public\nrole_family: worker\n---\n"
            "@{GPD_AGENTS_DIR}/gpd-shared.md\n",
            encoding="utf-8",
        )

        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        content = (target / "agents" / "gpd-main.md").read_text(encoding="utf-8")
        assert "Shared agent body." in content
        assert "<!-- [included: gpd-shared.md] -->" in content
        assert "@ include not resolved:" not in content.lower()


class TestRuntimePermissions:
    def test_runtime_permissions_status_marks_yolo_launcher_as_relaunch_required(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.sync_runtime_permissions(target, autonomy="yolo")

        status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert status["config_aligned"] is True
        assert status["requires_relaunch"] is True
        assert "gemini-gpd-yolo" in str(status["next_step"])

    def test_sync_runtime_permissions_yolo_creates_launcher_wrapper(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        result = adapter.sync_runtime_permissions(target, autonomy="yolo")
        wrapper = target / "get-physics-done" / "bin" / "gemini-gpd-yolo"

        assert wrapper.exists()
        assert '--approval-mode=yolo "$@"' in wrapper.read_text(encoding="utf-8")
        assert result["sync_applied"] is True
        assert result["launch_command"] == str(wrapper)
        assert result["requires_relaunch"] is True

    def test_sync_runtime_permissions_non_yolo_removes_launcher_wrapper(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.sync_runtime_permissions(target, autonomy="yolo")

        result = adapter.sync_runtime_permissions(target, autonomy="balanced")
        wrapper = target / "get-physics-done" / "bin" / "gemini-gpd-yolo"

        assert not wrapper.exists()
        assert result["sync_applied"] is True


class TestUninstall:
    def test_uninstall_removes_gpd_dirs(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.uninstall(target)

        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()
        assert not (target / "gpd-file-manifest.json").exists()

    def test_uninstall_cleans_settings(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        # Write settings with statusline and hooks via finish_install
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        adapter.uninstall(target)

        assert not (target / "settings.json").exists()

    def test_uninstall_preserves_preexisting_experimental_agents(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps({"experimental": {"enableAgents": True}, "theme": "solarized"}) + "\n",
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        adapter.uninstall(target)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["experimental"]["enableAgents"] is True
        assert settings["theme"] == "solarized"

    def test_uninstall_removes_gpd_mcp_servers(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)
        adapter.finish_install(
            result["settingsPath"],
            result["settings"],
            result["statuslineCommand"],
            True,
        )

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        settings["mcpServers"]["custom-server"] = {"command": "node", "args": ["custom.js"]}
        settings["mcpServers"]["gpd-wolfram"] = {
            "command": "gpd-mcp-wolfram",
            "args": [],
            "env": {"GPD_WOLFRAM_MCP_ENDPOINT": "https://example.invalid/api/mcp"},
        }
        (target / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert "mcpServers" in cleaned
        assert cleaned["mcpServers"] == {"custom-server": {"command": "node", "args": ["custom.js"]}}

    def test_uninstall_removes_gpd_policy_path_and_policy_file(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
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
        settings["policyPaths"].append("/tmp/custom-policies")
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
        assert cleaned["policyPaths"] == ["/tmp/custom-policies"]
        assert "tools" not in cleaned
        assert not (target / "bin" / "gpd").exists()
        assert not (target / "policies" / "gpd-auto-edit.toml").exists()

    def test_uninstall_preserves_non_gpd_sessionstart_statusline_hook(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
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
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
        session_start = cleaned.get("hooks", {}).get("SessionStart", [])
        commands = [
            hook["command"]
            for entry in session_start
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and isinstance(hook.get("command"), str)
        ]
        assert "python3 /tmp/third-party-statusline.py" in commands

    def test_uninstall_preserves_non_gpd_sessionstart_check_update_hook(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
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
            {"hooks": [{"type": "command", "command": "python3 /tmp/third-party/check_update.py"}]}
        )
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
        session_start = cleaned.get("hooks", {}).get("SessionStart", [])
        commands = [
            hook["command"]
            for entry in session_start
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict) and isinstance(hook.get("command"), str)
        ]
        assert "python3 /tmp/third-party/check_update.py" in commands

    def test_uninstall_on_empty_dir(self, adapter: GeminiAdapter, tmp_path: Path) -> None:
        target = tmp_path / "empty"
        target.mkdir()
        result = adapter.uninstall(target)
        assert result["removed"] == []


class TestRewriteWindowsPathEscape:
    """Regression: Windows paths with backslashes must not be interpreted as
    escape sequences by ``re.sub``.  See discussion #12."""

    def test_rewrite_gpd_cli_invocations_preserves_prose_and_quotes(self) -> None:
        bridge_command = "/runtime/gpd-cli"
        content = (
            'Prose mentions gpd and "gpd status" without changing.\n'
            "Use `gpd status` for a quick check.\n"
            "```bash\n"
            'echo "gpd status"\n'
            "echo 'gpd commit'\n"
            "gpd status\n"
            "gpd commit\n"
            "  printf 'done'\n"
            "```\n"
        )

        result = _rewrite_gpd_cli_invocations(content, bridge_command)

        assert 'Prose mentions gpd and "gpd status" without changing.' in result
        assert "`gpd status`" in result
        assert 'echo "gpd status"' in result
        assert "echo 'gpd commit'" in result
        assert f"{bridge_command} status" in result
        assert f"{bridge_command} commit" in result

    @pytest.mark.parametrize(
        "bridge_command",
        [
            r"'C:\Users\OuterSpaceOrg\GPD\venv\Scripts\python.exe' -m gpd.runtime_cli",
            r"'C:\Users\me\GPD\venv\Scripts\python.exe' -m gpd.runtime_cli",
        ],
    )
    def test_rewrite_gpd_cli_invocations_windows_path(self, bridge_command: str) -> None:
        content = "```bash\ngpd status\n```\n"
        result = _rewrite_gpd_cli_invocations(content, bridge_command)
        assert bridge_command in result
        assert "```bash\n" in result


class TestPolicyTomlWindowsPath:
    """Regression: policy TOML must be valid even when bridge_command contains
    Windows backslash paths.  See discussion #12."""

    def test_render_policy_toml_with_windows_path(self) -> None:
        import tomllib

        bridge = r"'C:\Users\OuterSpaceOrg\GPD\venv\Scripts\python.exe' -m gpd.runtime_cli --runtime gemini"
        toml_text = _render_gemini_policy_toml(bridge)
        parsed = tomllib.loads(toml_text)
        prefixes = parsed["rule"][0]["commandPrefix"]
        assert any("python" in p for p in prefixes)
        assert any("git init" in p for p in prefixes)
