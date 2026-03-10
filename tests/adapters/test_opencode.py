"""Tests for the OpenCode runtime adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters.opencode import (
    OpenCodeAdapter,
    configure_opencode_permissions,
    convert_claude_to_opencode_frontmatter,
    convert_tool_name,
    copy_agents_as_agent_files,
    copy_flattened_commands,
)


@pytest.fixture()
def adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter()


class TestProperties:
    def test_runtime_name(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.runtime_name == "opencode"

    def test_display_name(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.display_name == "OpenCode"

    def test_config_dir_name(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.config_dir_name == ".opencode"

    def test_help_command(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.help_command == "/gpd-help"


class TestTranslateToolName:
    def test_canonical_to_opencode(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.translate_tool_name("file_read") == "read_file"
        assert adapter.translate_tool_name("file_edit") == "edit_file"
        assert adapter.translate_tool_name("ask_user") == "question"
        assert adapter.translate_tool_name("slash_command") == "skill"

    def test_legacy_alias(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.translate_tool_name("AskUserQuestion") == "question"
        assert adapter.translate_tool_name("SlashCommand") == "skill"


class TestConvertToolName:
    def test_special_mappings(self) -> None:
        assert convert_tool_name("AskUserQuestion") == "question"
        assert convert_tool_name("SlashCommand") == "skill"
        assert convert_tool_name("TodoWrite") == "todowrite"
        assert convert_tool_name("WebFetch") == "webfetch"
        assert convert_tool_name("WebSearch") == "websearch"

    def test_mcp_passthrough(self) -> None:
        assert convert_tool_name("mcp__physics") == "mcp__physics"

    def test_unknown_passthrough(self) -> None:
        assert convert_tool_name("CustomTool") == "CustomTool"


class TestConvertFrontmatter:
    def test_no_frontmatter_passthrough(self) -> None:
        content = "Just body text"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "question" not in result  # no AskUserQuestion to convert
        assert "/gpd-" not in result  # no /gpd: to convert

    def test_name_stripped(self) -> None:
        content = "---\nname: gpd:help\ndescription: Help\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "name:" not in result
        assert "description: Help" in result

    def test_color_name_to_hex(self) -> None:
        content = "---\ncolor: cyan\ndescription: D\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert '"#00FFFF"' in result

    def test_color_hex_preserved(self) -> None:
        content = "---\ncolor: #FF0000\ndescription: D\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "#FF0000" in result

    def test_color_invalid_hex_stripped(self) -> None:
        content = "---\ncolor: #GGGGGG\ndescription: D\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "color:" not in result

    def test_color_unknown_name_stripped(self) -> None:
        content = "---\ncolor: chartreuse\ndescription: D\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "color:" not in result

    def test_allowed_tools_to_tools_object(self) -> None:
        content = "---\ndescription: D\nallowed-tools:\n  - Read\n  - Bash\n  - AskUserQuestion\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "tools:" in result
        assert "read_file: true" in result
        assert "shell: true" in result
        assert "question: true" in result
        assert "allowed-tools:" not in result

    def test_slash_command_conversion(self) -> None:
        content = "---\ndescription: D\n---\nRun /gpd:execute-phase now"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "/gpd-execute-phase" in result
        assert "/gpd:" not in result

    def test_claude_path_conversion(self) -> None:
        content = "---\ndescription: D\n---\nSee ~/.claude/agents/gpd-verifier.md"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "~/.config/opencode/agents/gpd-verifier.md" in result

    def test_tool_name_conversion_in_body(self) -> None:
        content = "---\ndescription: D\n---\nUse AskUserQuestion to ask."
        result = convert_claude_to_opencode_frontmatter(content)
        assert "question" in result

    def test_inline_tools_field(self) -> None:
        content = "---\ndescription: D\ntools: Read, Write\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "tools:" in result


class TestCopyFlattenedCommands:
    def test_flattens_nested_dirs(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "command"
        dest.mkdir()
        count = copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/")

        assert count >= 2
        assert (dest / "gpd-help.md").exists()
        assert (dest / "gpd-sub-deep.md").exists()

    def test_placeholder_replacement(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "command"
        dest.mkdir()
        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/")

        content = (dest / "gpd-help.md").read_text(encoding="utf-8")
        assert "{GPD_INSTALL_DIR}" not in content
        assert "~/.claude/" not in content

    def test_frontmatter_converted(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "command"
        dest.mkdir()
        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/")

        content = (dest / "gpd-help.md").read_text(encoding="utf-8")
        # name: should be stripped by OpenCode frontmatter conversion
        assert "name:" not in content

    def test_cleans_old_files(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "command"
        dest.mkdir()
        (dest / "gpd-old-command.md").write_text("stale", encoding="utf-8")
        (dest / "custom-command.md").write_text("keep", encoding="utf-8")

        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/")

        assert not (dest / "gpd-old-command.md").exists()
        assert (dest / "custom-command.md").exists()

    def test_nonexistent_src_returns_zero(self, tmp_path: Path) -> None:
        dest = tmp_path / "command"
        dest.mkdir()
        assert copy_flattened_commands(tmp_path / "nope", dest, "gpd", "/") == 0


class TestCopyAgentsAsAgentFiles:
    def test_copies_agents_with_conversion(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "agents"
        count = copy_agents_as_agent_files(gpd_root / "agents", dest, "/prefix/")

        assert count >= 2
        assert (dest / "gpd-verifier.md").exists()
        assert (dest / "gpd-executor.md").exists()

    def test_frontmatter_converted(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "agents"
        copy_agents_as_agent_files(gpd_root / "agents", dest, "/prefix/")

        for agent_file in dest.glob("gpd-*.md"):
            content = agent_file.read_text(encoding="utf-8")
            assert "allowed-tools:" not in content

    def test_removes_stale_agents(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "agents"
        dest.mkdir(parents=True)
        (dest / "gpd-stale.md").write_text("stale", encoding="utf-8")

        copy_agents_as_agent_files(gpd_root / "agents", dest, "/prefix/")

        assert not (dest / "gpd-stale.md").exists()

    def test_nonexistent_src_returns_zero(self, tmp_path: Path) -> None:
        dest = tmp_path / "agents"
        assert copy_agents_as_agent_files(tmp_path / "nope", dest, "/") == 0


class TestConfigureOpenCodePermissions:
    def test_creates_config_with_permissions(self, tmp_path: Path) -> None:
        modified = configure_opencode_permissions(tmp_path)

        assert modified is True
        config = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
        perm = config["permission"]
        assert any("get-physics-done" in k for k in perm.get("read", {}))
        assert any("get-physics-done" in k for k in perm.get("external_directory", {}))

    def test_preserves_existing_config(self, tmp_path: Path) -> None:
        (tmp_path / "opencode.json").write_text(
            json.dumps({"model": "gpt-4", "permission": {"read": {"*.txt": "allow"}}}),
            encoding="utf-8",
        )

        configure_opencode_permissions(tmp_path)

        config = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
        assert config["model"] == "gpt-4"
        assert config["permission"]["read"]["*.txt"] == "allow"

    def test_idempotent(self, tmp_path: Path) -> None:
        configure_opencode_permissions(tmp_path)
        modified = configure_opencode_permissions(tmp_path)
        assert modified is False


class TestGenerateCommand:
    def test_creates_flattened_md(self, adapter: OpenCodeAdapter, tmp_path: Path) -> None:
        result = adapter.generate_command(
            {"name": "gpd-help", "content": "---\nname: gpd:help\ndescription: Help\n---\nBody"},
            tmp_path,
        )
        assert result == tmp_path / "command" / "gpd-help.md"
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        # name: stripped by frontmatter conversion
        assert "name:" not in content


class TestGenerateAgent:
    def test_creates_agent_md(self, adapter: OpenCodeAdapter, tmp_path: Path) -> None:
        content = "---\nname: gpd-verifier\nallowed-tools:\n  - Read\ncolor: green\n---\nPrompt"
        result = adapter.generate_agent({"name": "gpd-verifier", "content": content}, tmp_path)
        assert result == tmp_path / "agents" / "gpd-verifier.md"
        text = result.read_text(encoding="utf-8")
        assert "name:" not in text
        assert "tools:" in text


class TestInstall:
    def test_local_install_uses_relative_gpd_paths(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()

        adapter.install(gpd_root, target, is_global=False)

        content = (target / "command" / "gpd-help.md").read_text(encoding="utf-8")
        assert "./.opencode/get-physics-done/ref" in content
        assert "./.opencode/agents" in content
        assert f"{target.as_posix()}/get-physics-done" not in content

    def test_install_creates_flattened_commands(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        command_dir = target / "command"
        assert command_dir.is_dir()
        gpd_cmds = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")]
        assert len(gpd_cmds) > 0

    def test_install_creates_gpd_content(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        gpd_dest = target / "get-physics-done"
        assert gpd_dest.is_dir()
        for subdir in ("references", "templates", "workflows"):
            assert (gpd_dest / subdir).is_dir()

    def test_install_creates_agents(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        assert len(list(agents_dir.glob("gpd-*.md"))) >= 2

    def test_install_copies_hooks(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert (target / "hooks" / "statusline.py").exists()

    def test_install_writes_version(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert (target / "get-physics-done" / "VERSION").exists()

    def test_install_configures_permissions(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert (target / "opencode.json").exists()

    def test_install_writes_manifest(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert (target / "gpd-file-manifest.json").exists()

    def test_install_returns_counts(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        assert result["runtime"] == "opencode"
        assert result["commands"] > 0
        assert result["agents"] > 0


class TestUninstall:
    def test_uninstall_cleans_local_opencode_json(
        self,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        adapter = OpenCodeAdapter()
        monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(tmp_path / "global-opencode"))
        target = tmp_path / ".opencode"
        target.mkdir()

        adapter.install(gpd_root, target, is_global=False)

        config_path = target / "opencode.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["permission"]["read"]["/tmp/custom/*"] = "allow"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(config_path.read_text(encoding="utf-8"))
        read_permissions = cleaned.get("permission", {}).get("read", {})
        external_permissions = cleaned.get("permission", {}).get("external_directory", {})
        assert "/tmp/custom/*" in read_permissions
        assert not any("get-physics-done" in key for key in read_permissions)
        assert not any("get-physics-done" in key for key in external_permissions)

    def test_uninstall_removes_commands(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.uninstall(target)

        command_dir = target / "command"
        if command_dir.exists():
            gpd_cmds = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")]
            assert len(gpd_cmds) == 0

    def test_uninstall_removes_gpd_dir(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.uninstall(target)

        assert not (target / "get-physics-done").exists()

    def test_uninstall_on_empty_dir(self, adapter: OpenCodeAdapter, tmp_path: Path) -> None:
        target = tmp_path / "empty"
        target.mkdir()
        result = adapter.uninstall(target)
        assert result["removed"] == []
