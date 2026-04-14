"""Tests for the GitHub Copilot CLI runtime adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters.copilot_cli import (
    CopilotCliAdapter,
    convert_to_copilot_frontmatter,
    convert_tool_name,
    copy_agents_as_agent_files,
    copy_flattened_commands,
)
from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_cli_bridge_command


@pytest.fixture()
def adapter() -> CopilotCliAdapter:
    return CopilotCliAdapter()


def expected_copilot_bridge(target: Path, *, is_global: bool = False, explicit_target: bool = False) -> str:
    return build_runtime_cli_bridge_command(
        "copilot-cli",
        target_dir=target,
        config_dir_name=".copilot",
        is_global=is_global,
        explicit_target=explicit_target,
    )


class TestProperties:
    def test_runtime_name(self, adapter: CopilotCliAdapter) -> None:
        assert adapter.runtime_name == "copilot-cli"

    def test_display_name(self, adapter: CopilotCliAdapter) -> None:
        assert adapter.display_name == "GitHub Copilot CLI"

    def test_config_dir_name(self, adapter: CopilotCliAdapter) -> None:
        assert adapter.config_dir_name == ".copilot"

    def test_help_command(self, adapter: CopilotCliAdapter) -> None:
        assert adapter.help_command == "/gpd-help"


class TestConvertToolName:
    def test_file_mappings(self) -> None:
        assert convert_tool_name("file_read") == "read_file"
        assert convert_tool_name("file_write") == "write_file"
        assert convert_tool_name("file_edit") == "edit_file"

    def test_search_mappings(self) -> None:
        assert convert_tool_name("search_files") == "grep"
        assert convert_tool_name("find_files") == "glob"

    def test_identity_mappings(self) -> None:
        assert convert_tool_name("shell") == "shell"
        assert convert_tool_name("agent") == "agent"
        assert convert_tool_name("task") == "task"

    def test_slash_command_mapping(self) -> None:
        assert convert_tool_name("slash_command") == "skill"

    def test_mcp_passthrough(self) -> None:
        assert convert_tool_name("mcp__physics") == "mcp__physics"

    def test_unknown_passthrough(self) -> None:
        assert convert_tool_name("CustomTool") == "CustomTool"


class TestConvertFrontmatter:
    def test_no_frontmatter_passthrough(self) -> None:
        content = "Just body text"
        result = convert_to_copilot_frontmatter(content)
        assert result == content

    def test_name_stripped(self) -> None:
        content = "---\nname: gpd:help\ndescription: Help\n---\nBody"
        result = convert_to_copilot_frontmatter(content)
        assert "name:" not in result
        assert "description: Help" in result

    def test_color_stripped(self) -> None:
        content = "---\ncolor: cyan\ndescription: D\n---\nBody"
        result = convert_to_copilot_frontmatter(content)
        assert "color:" not in result
        assert "description: D" in result

    def test_allowed_tools_to_tools_object(self) -> None:
        content = "---\ndescription: D\nallowed-tools:\n  - Read\n  - Bash\n---\nBody"
        result = convert_to_copilot_frontmatter(content)
        assert "tools:" in result
        assert "read_file: true" in result
        assert "shell: true" in result
        assert "allowed-tools:" not in result

    def test_slash_command_conversion_is_boundary_aware(self) -> None:
        content = (
            "---\ndescription: D\n---\n"
            "Run /gpd:execute-phase now.\n"
            "See https://example.test//gpd:help and /tmp//gpd:help.txt.\n"
            "Use `/gpd:tour` when you mean the runtime command.\n"
        )
        result = convert_to_copilot_frontmatter(content)
        assert "/gpd-execute-phase" in result
        assert "`/gpd-tour`" in result
        assert "https://example.test//gpd:help" in result
        assert "/tmp//gpd:help.txt" in result

    def test_claude_path_conversion(self) -> None:
        content = "---\ndescription: D\n---\nSee ~/.claude/agents/gpd-verifier.md"
        result = convert_to_copilot_frontmatter(content)
        assert "~/.copilot/agents/gpd-verifier.md" in result

    def test_claude_path_conversion_uses_resolved_path_prefix(self) -> None:
        content = "---\ndescription: D\n---\nSee ~/.claude/agents/gpd-verifier.md"
        result = convert_to_copilot_frontmatter(content, "./.copilot/")
        assert "./.copilot/agents/gpd-verifier.md" in result
        assert "~/.copilot/agents/gpd-verifier.md" not in result

    def test_inline_tools_field(self) -> None:
        content = "---\ndescription: D\ntools: Read, Write\n---\nBody"
        result = convert_to_copilot_frontmatter(content)
        assert "tools:" in result

    def test_description_with_triple_dash_is_preserved(self) -> None:
        content = "---\ndescription: before --- after\nallowed-tools:\n  - Read\n---\nBody"
        result = convert_to_copilot_frontmatter(content)
        assert "description: before --- after" in result
        assert "read_file: true" in result
        assert result.rstrip().endswith("Body")


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
        # name: should be stripped by Copilot CLI frontmatter conversion
        assert "name:" not in content

    def test_cleans_old_files(self, gpd_root: Path, tmp_path: Path) -> None:
        dest = tmp_path / "command"
        dest.mkdir()
        (dest / "gpd-old-command.md").write_text("stale", encoding="utf-8")
        (dest / "custom-command.md").write_text("keep", encoding="utf-8")
        (tmp_path / MANIFEST_NAME).write_text(
            json.dumps({"copilot_generated_command_files": ["gpd-old-command.md"]}),
            encoding="utf-8",
        )

        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/", workflow_target_dir=tmp_path)

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


class TestInstall:
    def test_install_creates_flattened_commands(self, adapter: CopilotCliAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        command_dir = target / "command"
        assert command_dir.is_dir()
        gpd_cmds = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")]
        assert len(gpd_cmds) > 0

    def test_install_creates_gpd_content(self, adapter: CopilotCliAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        gpd_dest = target / "get-physics-done"
        assert gpd_dest.is_dir()
        for subdir in ("references", "templates", "workflows"):
            assert (gpd_dest / subdir).is_dir()

    def test_install_creates_agents(self, adapter: CopilotCliAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        assert len(list(agents_dir.glob("gpd-*.md"))) >= 2

    def test_install_creates_copilot_json(self, adapter: CopilotCliAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        config_path = target / "copilot.json"
        assert config_path.exists()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert isinstance(config, dict)

    def test_install_completeness_requires_copilot_json(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert adapter.missing_install_artifacts(target) == ()

        (target / "copilot.json").unlink()

        assert adapter.missing_install_artifacts(target) == ("copilot.json",)

    def test_install_completeness_requires_manifest_backed_command_surface(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        command_dir = target / "command"
        command_dir.rename(tmp_path / "command-missing")

        missing = adapter.missing_install_artifacts(target)

        assert adapter.has_complete_install(target) is False
        assert "command/gpd-*.md" in missing
        assert any(item.startswith("command/") for item in missing)

    def test_install_fails_closed_for_malformed_copilot_json(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        config_path = target / "copilot.json"
        config_path.write_text('{"mcp": [\n', encoding="utf-8")
        before = config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert config_path.read_text(encoding="utf-8") == before

    def test_install_fails_closed_for_structurally_invalid_copilot_mcp_config(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        config_path = target / "copilot.json"
        config_path.write_text(json.dumps({"mcp": []}), encoding="utf-8")
        before = config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert config_path.read_text(encoding="utf-8") == before

    def test_install_skips_unused_hooks(self, adapter: CopilotCliAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert not (target / "hooks").exists()

    def test_install_preserves_existing_copilot_json_config(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        (target / "copilot.json").write_text(
            json.dumps({"model": "gpt-4", "custom": True}),
            encoding="utf-8",
        )

        adapter.install(gpd_root, target)

        config = json.loads((target / "copilot.json").read_text(encoding="utf-8"))
        assert config["model"] == "gpt-4"
        assert config["custom"] is True


class TestUninstall:
    def test_uninstall_removes_gpd_artifacts(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()
        adapter.install(gpd_root, target)

        result = adapter.uninstall(target)

        assert result["runtime"] == "copilot-cli"
        assert not (target / "get-physics-done").exists()
        assert not (target / MANIFEST_NAME).exists()

    def test_uninstall_preserves_user_owned_gpd_command_files(
        self,
        adapter: CopilotCliAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".copilot"
        target.mkdir()

        adapter.install(gpd_root, target)
        (target / "command" / "gpd-user-keep.md").write_text("keep", encoding="utf-8")

        adapter.uninstall(target)

        assert (target / "command" / "gpd-user-keep.md").exists()
