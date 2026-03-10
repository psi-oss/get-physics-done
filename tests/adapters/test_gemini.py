"""Tests for the Gemini CLI runtime adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters.gemini import (
    GeminiAdapter,
    _convert_frontmatter_to_gemini,
    _convert_gemini_tool_name,
    _convert_to_gemini_toml,
)


@pytest.fixture()
def adapter() -> GeminiAdapter:
    return GeminiAdapter()


class TestProperties:
    def test_runtime_name(self, adapter: GeminiAdapter) -> None:
        assert adapter.runtime_name == "gemini"

    def test_display_name(self, adapter: GeminiAdapter) -> None:
        assert adapter.display_name == "Gemini"

    def test_config_dir_name(self, adapter: GeminiAdapter) -> None:
        assert adapter.config_dir_name == ".gemini"

    def test_help_command(self, adapter: GeminiAdapter) -> None:
        assert adapter.help_command == "/gpd:help"


class TestTranslateToolName:
    def test_canonical_to_gemini(self, adapter: GeminiAdapter) -> None:
        assert adapter.translate_tool_name("file_read") == "read_file"
        assert adapter.translate_tool_name("shell") == "run_shell_command"
        assert adapter.translate_tool_name("search_files") == "search_file_content"
        assert adapter.translate_tool_name("web_search") == "google_web_search"

    def test_legacy_alias(self, adapter: GeminiAdapter) -> None:
        assert adapter.translate_tool_name("Read") == "read_file"
        assert adapter.translate_tool_name("Bash") == "run_shell_command"


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


class TestConvertToGeminiToml:
    def test_no_frontmatter(self) -> None:
        result = _convert_to_gemini_toml("Just a prompt body")
        assert "prompt" in result
        assert "Just a prompt body" in result

    def test_extracts_description(self) -> None:
        content = "---\nname: test\ndescription: My description\n---\nPrompt body"
        result = _convert_to_gemini_toml(content)
        assert 'description = "My description"' in result
        assert "Prompt body" in result

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


class TestGenerateCommand:
    def test_creates_toml_file(self, adapter: GeminiAdapter, tmp_path: Path) -> None:
        result = adapter.generate_command(
            {"name": "help", "content": "---\ndescription: Help\n---\nHelp body"},
            tmp_path,
        )
        assert result == tmp_path / "commands" / "help.toml"
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "prompt" in content

    def test_creates_commands_dir(self, adapter: GeminiAdapter, tmp_path: Path) -> None:
        adapter.generate_command({"name": "test", "content": "body"}, tmp_path)
        assert (tmp_path / "commands").is_dir()


class TestGenerateAgent:
    def test_creates_md_with_converted_frontmatter(self, adapter: GeminiAdapter, tmp_path: Path) -> None:
        content = "---\nname: gpd-verifier\nallowed-tools:\n  - Read\n  - Bash\ncolor: green\n---\nPrompt"
        result = adapter.generate_agent({"name": "gpd-verifier", "content": content}, tmp_path)
        assert result == tmp_path / "agents" / "gpd-verifier.md"
        text = result.read_text(encoding="utf-8")
        assert "color:" not in text
        assert "tools:" in text
        assert "read_file" in text


class TestGenerateHook:
    def test_format_matches_claude_code(self, adapter: GeminiAdapter) -> None:
        result = adapter.generate_hook("test", {"event": "SessionStart", "command": "echo hi"})
        assert result == {"hooks": {"SessionStart": [{"command": "echo hi"}]}}


class TestInstall:
    def test_install_creates_toml_commands(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        adapter.install(gpd_root, target)

        commands_dir = target / "commands" / "gpd"
        assert commands_dir.is_dir()
        toml_files = list(commands_dir.rglob("*.toml"))
        assert len(toml_files) > 0

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
            assert "color:" not in content
            assert "allowed-tools:" not in content

    def test_install_enables_experimental_agents(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        # install() returns settings dict (not yet written to disk)
        settings = result["settings"]
        assert settings.get("experimental", {}).get("enableAgents") is True

    def test_install_configures_update_hook(self, adapter: GeminiAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        settings = result["settings"]
        hooks = settings.get("hooks", {})
        session_start = hooks.get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert any("check_update" in c for c in cmds)

    def test_install_preserves_jsonc_settings_and_uses_current_interpreter(
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
        assert settings["statusLine"]["command"] == "/custom/venv/bin/python .gemini/hooks/statusline.py"
        session_start = settings.get("hooks", {}).get("SessionStart", [])
        cmds = [h.get("command", "") for entry in session_start for h in (entry.get("hooks") or [])]
        assert "/custom/venv/bin/python .gemini/hooks/check_update.py" in cmds

    def test_install_rewrites_legacy_arxiv_mcp_server(
        self,
        adapter: GeminiAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "arxiv": {"command": "python", "args": ["-m", "legacy_server"]},
                        "custom": {"command": "keep"},
                    }
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = adapter.install(gpd_root, target)

        mcp_servers = result["settings"]["mcpServers"]
        assert "gpd-arxiv" in mcp_servers
        assert "arxiv" not in mcp_servers
        assert mcp_servers["custom"]["command"] == "keep"

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

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert "statusLine" not in settings
        assert settings.get("experimental", {}).get("enableAgents") is not True

    def test_uninstall_on_empty_dir(self, adapter: GeminiAdapter, tmp_path: Path) -> None:
        target = tmp_path / "empty"
        target.mkdir()
        result = adapter.uninstall(target)
        assert result["removed"] == []
