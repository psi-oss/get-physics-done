"""Tests for the OpenCode runtime adapter."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_cli_bridge_command, hook_python_interpreter
from gpd.adapters.opencode import (
    OpenCodeAdapter,
    configure_opencode_permissions,
    convert_claude_to_opencode_frontmatter,
    convert_tool_name,
    copy_agents_as_agent_files,
    copy_flattened_commands,
)
from tests.adapters.review_contract_test_utils import (
    assert_review_contract_prompt_surface,
    compile_review_contract_fixture_for_runtime,
)


@pytest.fixture()
def adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter()


def expected_opencode_bridge(target: Path, *, is_global: bool = False, explicit_target: bool = False) -> str:
    return build_runtime_cli_bridge_command(
        "opencode",
        target_dir=target,
        config_dir_name=".opencode",
        is_global=is_global,
        explicit_target=explicit_target,
    )


def _assert_no_manifestless_gpd_artifacts(target: Path) -> None:
    assert not (target / MANIFEST_NAME).exists()
    assert not (target / "get-physics-done").exists()
    assert not (target / "command").exists()
    assert not (target / "agents").exists()
    assert not (target / "hooks").exists()


class TestProperties:
    def test_runtime_name(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.runtime_name == "opencode"

    def test_display_name(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.display_name == "OpenCode"

    def test_config_dir_name(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.config_dir_name == ".opencode"

    def test_help_command(self, adapter: OpenCodeAdapter) -> None:
        assert adapter.help_command == "/gpd-help"


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

    def test_slash_command_conversion_is_boundary_aware(self) -> None:
        content = (
            "---\ndescription: D\n---\n"
            "Run /gpd:execute-phase now.\n"
            "See https://example.test//gpd:help and /tmp//gpd:help.txt.\n"
            "Use `/gpd:tour` when you mean the runtime command.\n"
        )
        result = convert_claude_to_opencode_frontmatter(content)
        assert "/gpd-execute-phase" in result
        assert "`/gpd-tour`" in result
        assert "https://example.test//gpd:help" in result
        assert "/tmp//gpd:help.txt" in result

    def test_bare_gpd_command_conversion_is_boundary_aware(self) -> None:
        content = (
            "---\ndescription: D\n---\n"
            "Use gpd:start for routing.\n"
            "See https://example.test/gpd:help for docs.\n"
            "Do not rewrite mygpd:command inside a word.\n"
        )
        result = convert_claude_to_opencode_frontmatter(content)
        assert "gpd-start" in result
        assert "https://example.test/gpd:help" in result
        assert "mygpd:command" in result

    def test_foreign_runtime_claude_path_is_preserved(self) -> None:
        content = "---\ndescription: D\n---\nSee ~/.claude/agents/gpd-verifier.md"
        result = convert_claude_to_opencode_frontmatter(content, "./.opencode/")
        assert "~/.claude/agents/gpd-verifier.md" in result
        assert "./.opencode/agents/gpd-verifier.md" not in result

    def test_claude_tool_name_in_body_is_left_unchanged(self) -> None:
        content = "---\ndescription: D\n---\nUse AskUserQuestion to ask."
        result = convert_claude_to_opencode_frontmatter(content)
        assert result == content

    def test_inline_tools_field(self) -> None:
        content = "---\ndescription: D\ntools: Read, Write\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "tools:" in result

    def test_description_with_triple_dash_is_preserved(self) -> None:
        content = "---\ndescription: before --- after\nallowed-tools:\n  - Read\n---\nBody"
        result = convert_claude_to_opencode_frontmatter(content)
        assert "description: before --- after" in result
        assert "read_file: true" in result
        assert result.rstrip().endswith("Body")

    def test_review_contract_is_prepended_to_prompt_body(self) -> None:
        content = compile_review_contract_fixture_for_runtime("opencode")

        result = convert_claude_to_opencode_frontmatter(content)

        assert_review_contract_prompt_surface(result)


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
        assert "~/.claude/agents path" in content

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
        (tmp_path / MANIFEST_NAME).write_text(
            json.dumps({"opencode_generated_command_files": ["gpd-old-command.md"]}),
            encoding="utf-8",
        )

        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/", workflow_target_dir=tmp_path)

        assert not (dest / "gpd-old-command.md").exists()
        assert (dest / "custom-command.md").exists()

    def test_preserves_user_owned_gpd_files_when_reinstalling(self, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        dest = target / "command"
        dest.mkdir(parents=True)
        (dest / "gpd-old-command.md").write_text("stale", encoding="utf-8")
        (dest / "gpd-user-keep.md").write_text("keep", encoding="utf-8")
        (target / MANIFEST_NAME).write_text(
            json.dumps({"opencode_generated_command_files": ["gpd-old-command.md"]}),
            encoding="utf-8",
        )

        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/", workflow_target_dir=target)

        assert not (dest / "gpd-old-command.md").exists()
        assert (dest / "gpd-user-keep.md").exists()

    def test_cleans_old_files_from_manifest_files_fallback(self, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        dest = target / "command"
        dest.mkdir(parents=True)
        (dest / "gpd-old-command.md").write_text("stale", encoding="utf-8")
        (dest / "gpd-user-keep.md").write_text("keep", encoding="utf-8")
        (target / MANIFEST_NAME).write_text(
            json.dumps({"files": {"command/gpd-old-command.md": "old-hash"}}),
            encoding="utf-8",
        )

        copy_flattened_commands(gpd_root / "commands", dest, "gpd", "/prefix/", workflow_target_dir=target)

        assert not (dest / "gpd-old-command.md").exists()
        assert (dest / "gpd-user-keep.md").exists()

    def test_write_manifest_scans_flat_commands_by_default(self, tmp_path: Path) -> None:
        from gpd.adapters.opencode import write_manifest

        target = tmp_path / ".opencode"
        command_dir = target / "command"
        command_dir.mkdir(parents=True)
        (command_dir / "gpd-help.md").write_text("help", encoding="utf-8")
        (command_dir / "user.md").write_text("keep", encoding="utf-8")

        manifest = write_manifest(target, "1.2.3")

        assert manifest["runtime"] == "opencode"
        assert "command/gpd-help.md" in manifest["files"]
        assert "command/user.md" not in manifest["files"]
        assert manifest["opencode_generated_command_files"] == ["gpd-help.md"]

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

    def test_sanitizes_shell_placeholders_for_opencode_agents(self, gpd_root: Path, tmp_path: Path) -> None:
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
        dest = tmp_path / "agents"
        copy_agents_as_agent_files(gpd_root / "agents", dest, "/prefix/")

        checker = (dest / "gpd-shell-vars.md").read_text(encoding="utf-8")
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

    def test_preserves_global_string_permission_via_star_rule(self, tmp_path: Path) -> None:
        (tmp_path / "opencode.json").write_text(json.dumps({"permission": "ask"}), encoding="utf-8")

        configure_opencode_permissions(tmp_path)

        config = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
        assert config["permission"]["*"] == "ask"
        assert any("get-physics-done" in key for key in config["permission"]["external_directory"])


class TestUninstallOwnership:
    def test_uninstall_preserves_user_owned_gpd_command_files(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()

        adapter.install(gpd_root, target)
        (target / "command" / "gpd-user-keep.md").write_text("keep", encoding="utf-8")

        from gpd.adapters.opencode import uninstall_opencode

        uninstall_opencode(target, config_dir=target, allow_empty_config_removal=True)

        assert (target / "command" / "gpd-user-keep.md").exists()

    def test_uninstall_falls_back_to_manifest_files_when_generated_command_metadata_is_missing(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        dest = target / "command"
        dest.mkdir(parents=True)

        adapter.install(gpd_root, target)
        (dest / "gpd-user-keep.md").write_text("keep", encoding="utf-8")

        manifest_path = target / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("opencode_generated_command_files", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        from gpd.adapters.opencode import uninstall_opencode

        uninstall_opencode(target, config_dir=target, allow_empty_config_removal=True)

        assert not (dest / "gpd-help.md").exists()
        assert not (dest / "gpd-start.md").exists()
        assert (dest / "gpd-user-keep.md").exists()
        assert not (target / MANIFEST_NAME).exists()

    def test_adapter_uninstall_removes_flat_gpd_commands_when_owned_manifest_loses_command_tracking(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        command_dir = target / "command"
        target.mkdir()

        adapter.install(gpd_root, target)
        (command_dir / "gpd-obsolete.md").write_text("stale", encoding="utf-8")
        (command_dir / "custom-command.md").write_text("keep", encoding="utf-8")

        manifest_path = target / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("opencode_generated_command_files", None)
        manifest["files"] = {
            rel_path: digest for rel_path, digest in manifest["files"].items() if not rel_path.startswith("command/")
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        adapter.uninstall(target)

        assert command_dir.exists()
        assert not list(command_dir.glob("gpd-*.md"))
        assert (command_dir / "custom-command.md").exists()
        assert not manifest_path.exists()


class TestInstall:
    def test_help_command_does_not_describe_opencode_commands_as_slash_commands(
        self,
        adapter: OpenCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".opencode"
        target.mkdir()

        adapter.install(gpd_root, target)

        content = (target / "command" / "gpd-help.md").read_text(encoding="utf-8")
        assert "slash-command" not in content
        assert "Show available GPD commands and usage guide" in content
        assert "gpd:" in content

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
        assert "~/.claude/agents" in content
        assert "./.opencode/agents" not in content
        assert f"{target.as_posix()}/get-physics-done" not in content

    def test_install_completeness_requires_opencode_json(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert adapter.missing_install_artifacts(target) == ()

        (target / "opencode.json").unlink()

        assert adapter.missing_install_artifacts(target) == ("opencode.json",)

    def test_install_completeness_requires_manifest_backed_command_surface(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        command_dir = target / "command"
        command_dir.rename(tmp_path / "command-missing")

        missing = adapter.missing_install_artifacts(target)

        assert adapter.has_complete_install(target) is False
        assert "command/gpd-*.md" in missing
        assert any(item.startswith("command/") for item in missing)

    def test_install_completeness_falls_back_to_manifest_files_when_generated_command_metadata_is_missing(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        manifest_path = target / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("opencode_generated_command_files", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        assert adapter.missing_install_artifacts(target) == ()
        assert adapter.has_complete_install(target) is True

        tracked_command = next(
            rel_path.removeprefix("command/") for rel_path in manifest["files"] if rel_path.startswith("command/gpd-")
        )
        (target / "command" / tracked_command).unlink()

        missing = adapter.missing_install_artifacts(target)

        assert adapter.has_complete_install(target) is False
        assert f"command/{tracked_command}" in missing
        assert "command/gpd-*.md" in missing

    def test_install_fails_closed_for_malformed_opencode_json(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        config_path = target / "opencode.json"
        config_path.write_text('{"permission": [\n', encoding="utf-8")
        before = config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert config_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

    def test_install_fails_closed_for_structurally_invalid_opencode_json(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        config_path = target / "opencode.json"
        config_path.write_text(json.dumps({"permission": []}), encoding="utf-8")
        before = config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert config_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

    def test_install_fails_closed_for_structurally_invalid_opencode_mcp_config(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        config_path = target / "opencode.json"
        config_path.write_text(json.dumps({"mcp": []}), encoding="utf-8")
        before = config_path.read_text(encoding="utf-8")

        with pytest.raises(RuntimeError, match="malformed"):
            adapter.install(gpd_root, target)

        assert config_path.read_text(encoding="utf-8") == before
        _assert_no_manifestless_gpd_artifacts(target)

    def test_install_fails_when_no_command_files_are_generated(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()

        def _copy_no_commands(*args: object, **kwargs: object) -> int:
            return 0

        monkeypatch.setattr("gpd.adapters.opencode.copy_flattened_commands", _copy_no_commands)

        with pytest.raises(RuntimeError, match=r"command/gpd-\*\.md"):
            adapter.install(gpd_root, target)

        assert not (target / MANIFEST_NAME).exists()

    def test_install_creates_flattened_commands(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        command_dir = target / "command"
        assert command_dir.is_dir()
        gpd_cmds = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")]
        assert len(gpd_cmds) > 0

    def test_update_command_inlines_workflow(self, adapter: OpenCodeAdapter, tmp_path: Path) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        content = (target / "command" / "gpd-update.md").read_text(encoding="utf-8")
        assert "Check for a newer GPD release" in content
        assert "<!-- [included: update.md] -->" in content
        assert re.search(r"^\s*@.*?/workflows/update\.md\s*$", content, flags=re.MULTILINE) is None
        assert "gpd-reapply-patches" in content

    def test_complete_milestone_command_inlines_bullet_list_includes(
        self,
        adapter: OpenCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        content = (target / "command" / "gpd-complete-milestone.md").read_text(encoding="utf-8")
        assert "<!-- [included: complete-milestone.md] -->" in content
        assert "<!-- [included: milestone-archive.md] -->" in content
        assert "Mark a completed research stage" in content
        assert "# Milestone Archive Template" in content
        assert re.search(r"^\s*-\s*@.*?/workflows/complete-milestone\.md.*$", content, flags=re.MULTILINE) is None
        assert re.search(r"^\s*-\s*@.*?/templates/milestone-archive\.md.*$", content, flags=re.MULTILINE) is None

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

    def test_install_agents_inline_gpd_agents_dir_includes(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
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

        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        content = (target / "agents" / "gpd-main.md").read_text(encoding="utf-8")
        assert "Shared agent body." in content
        assert "<!-- [included: gpd-shared.md] -->" in content
        assert "@ include not resolved:" not in content.lower()

    def test_install_skips_unused_hooks(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        assert not (target / "hooks").exists()

    def test_install_manifest_does_not_own_preexisting_hooks(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        hooks = target / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "install_metadata.py").write_text("# user hook\n", encoding="utf-8")

        adapter.install(gpd_root, target)

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert not any(path.startswith("hooks/") for path in manifest["files"])
        assert (hooks / "install_metadata.py").read_text(encoding="utf-8") == "# user hook\n"

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

    def test_install_manifest_tracks_flat_commands_through_shared_writer(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        tracked_commands = manifest["opencode_generated_command_files"]

        assert "gpd-help.md" in tracked_commands
        assert all(f"command/{name}" in manifest["files"] for name in tracked_commands)
        assert not any(path.startswith("commands/gpd/") for path in manifest["files"])

    def test_install_returns_counts(self, adapter: OpenCodeAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        result = adapter.install(gpd_root, target)

        assert result["runtime"] == "opencode"
        assert result["commands"] > 0
        assert result["agents"] > 0
        assert result["hooks"] == 0

    def test_install_rewrites_gpd_cli_calls_to_runtime_cli_bridge(
        self,
        adapter: OpenCodeAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target, is_global=False)

        expected_bridge = expected_opencode_bridge(target, is_global=False)
        command = (target / "command" / "gpd-settings.md").read_text(encoding="utf-8")
        workflow = (target / "get-physics-done" / "workflows" / "settings.md").read_text(encoding="utf-8")
        execute_phase = (target / "get-physics-done" / "workflows" / "execute-phase.md").read_text(encoding="utf-8")
        agent = (target / "agents" / "gpd-planner.md").read_text(encoding="utf-8")

        assert expected_bridge + " config ensure-section" in command
        assert f"INIT=$({expected_bridge} --raw init progress --include state,config --no-project-reentry)" in command
        assert expected_bridge + " config ensure-section" in workflow
        assert f"INIT=$({expected_bridge} --raw init progress --include state,config --no-project-reentry)" in workflow
        assert 'echo "ERROR: gpd initialization failed: $INIT"' in workflow
        assert f'if ! {expected_bridge} verify plan "$plan"; then' in execute_phase
        assert f'INIT=$({expected_bridge} --raw init plan-phase "<PHASE>")' in agent
        assert "```bash\ngpd config ensure-section\n" not in workflow
        assert "INIT=$(gpd --raw init progress --include state,config --no-project-reentry)" not in workflow
        assert 'if ! gpd verify plan "$plan"; then' not in execute_phase
        assert 'INIT=$(gpd --raw init plan-phase "<PHASE>")' not in agent

    def test_install_preserves_existing_mcp_overrides(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        target = tmp_path / ".opencode"
        target.mkdir()
        (target / "opencode.json").write_text(
            json.dumps(
                {
                    "mcp": {
                        "gpd-state": {
                            "type": "local",
                            "command": ["python3", "-m", "old.state_server"],
                            "enabled": False,
                            "timeout": 12000,
                            "environment": {"LOG_LEVEL": "INFO", "EXTRA_FLAG": "1"},
                        },
                        "custom-server": {
                            "type": "local",
                            "command": ["node", "custom.js"],
                        },
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        adapter.install(gpd_root, target)

        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        expected = build_mcp_servers_dict(python_path=hook_python_interpreter())["gpd-state"]
        server = config["mcp"]["gpd-state"]
        assert server["type"] == "local"
        assert server["command"] == [expected["command"], *expected["args"]]
        assert server["enabled"] is False
        assert server["timeout"] == 12000
        assert server["environment"]["LOG_LEVEL"] == "INFO"
        assert server["environment"]["EXTRA_FLAG"] == "1"
        assert config["mcp"]["custom-server"] == {"type": "local", "command": ["node", "custom.js"]}

    def test_install_projects_managed_wolfram_mcp_without_secrets(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")
        monkeypatch.setenv("GPD_WOLFRAM_MCP_ENDPOINT", "https://example.invalid/api/mcp")

        adapter.install(gpd_root, target)

        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        wolfram = config["mcp"]["gpd-wolfram"]
        assert wolfram["type"] == "local"
        assert wolfram["command"] == [hook_python_interpreter(), "-m", "gpd.mcp.integrations.wolfram_bridge"]
        assert wolfram["enabled"] is True
        assert wolfram["environment"] == {"GPD_WOLFRAM_MCP_ENDPOINT": "https://example.invalid/api/mcp"}
        assert "super-secret-token" not in json.dumps(wolfram)
        assert "GPD_WOLFRAM_MCP_API_KEY" not in json.dumps(wolfram)

    def test_install_preserves_existing_managed_wolfram_overrides(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")
        monkeypatch.setenv("GPD_WOLFRAM_MCP_ENDPOINT", "https://example.invalid/api/mcp")
        (target / "opencode.json").write_text(
            json.dumps(
                {
                    "mcp": {
                        "gpd-wolfram": {
                            "type": "local",
                            "command": ["legacy-wolfram-bridge", "--legacy"],
                            "enabled": False,
                            "timeout": 12000,
                            "environment": {
                                "GPD_WOLFRAM_MCP_ENDPOINT": "https://custom.invalid/api/mcp",
                                "EXTRA_FLAG": "1",
                            },
                        },
                        "custom-server": {
                            "type": "local",
                            "command": ["node", "custom.js"],
                        },
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        adapter.install(gpd_root, target)

        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        wolfram = config["mcp"]["gpd-wolfram"]
        assert wolfram["type"] == "local"
        assert wolfram["command"] == [hook_python_interpreter(), "-m", "gpd.mcp.integrations.wolfram_bridge"]
        assert wolfram["enabled"] is False
        assert wolfram["timeout"] == 12000
        assert wolfram["environment"]["GPD_WOLFRAM_MCP_ENDPOINT"] == "https://custom.invalid/api/mcp"
        assert wolfram["environment"]["EXTRA_FLAG"] == "1"

    def test_install_omits_managed_wolfram_when_project_override_disables_it(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "integrations.json").write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")
        monkeypatch.setenv("GPD_WOLFRAM_MCP_API_KEY", "super-secret-token")

        adapter.install(gpd_root, target)

        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        assert "gpd-wolfram" not in config.get("mcp", {})
        assert "super-secret-token" not in json.dumps(config)

    def test_install_fails_closed_for_malformed_project_integrations_before_copying_artifacts(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        (tmp_path / "GPD").mkdir()
        (tmp_path / "GPD" / "integrations.json").write_text('{"wolfram":', encoding="utf-8")

        with pytest.raises(RuntimeError, match="Malformed integrations config"):
            adapter.install(gpd_root, target)

        _assert_no_manifestless_gpd_artifacts(target)


class TestRuntimePermissions:
    def test_runtime_permissions_status_marks_yolo_as_relaunch_required(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.sync_runtime_permissions(target, autonomy="yolo")

        status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert status["config_aligned"] is True
        assert status["requires_relaunch"] is True
        assert "Restart OpenCode" in str(status["next_step"])

    def test_sync_runtime_permissions_yolo_sets_global_allow(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        result = adapter.sync_runtime_permissions(target, autonomy="yolo")

        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))

        assert config["permission"] == "allow"
        assert manifest["gpd_runtime_permissions"]["mode"] == "yolo"
        assert result["sync_applied"] is True
        assert result["requires_relaunch"] is True

    def test_sync_runtime_permissions_restores_non_yolo_permissions(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        adapter.sync_runtime_permissions(target, autonomy="yolo")
        result = adapter.sync_runtime_permissions(target, autonomy="balanced")

        config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))

        assert isinstance(config["permission"], dict)
        assert config["permission"] != "allow"
        assert any("get-physics-done" in key for key in config["permission"]["external_directory"])
        assert "gpd_runtime_permissions" not in manifest
        assert result["sync_applied"] is True

    def test_malformed_opencode_json_fails_closed_for_status_and_sync(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)

        config_path = target / "opencode.json"
        config_path.write_text('{"permission": [\n', encoding="utf-8")
        before = config_path.read_text(encoding="utf-8")

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
        assert config_path.read_text(encoding="utf-8") == before


class TestUninstall:
    def test_uninstall_restores_scalar_permission_shape_after_install(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        config_path = target / "opencode.json"
        config_path.write_text(json.dumps({"permission": "ask"}) + "\n", encoding="utf-8")

        adapter.install(gpd_root, target, is_global=False)

        installed = json.loads(config_path.read_text(encoding="utf-8"))
        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert installed["permission"]["*"] == "ask"
        assert manifest["opencode_managed_config"]["permission_restore"] == {
            "kind": "scalar",
            "value": "ask",
        }

        adapter.uninstall(target)

        cleaned = json.loads(config_path.read_text(encoding="utf-8"))
        assert cleaned["permission"] == "ask"

    def test_uninstall_keeps_permission_object_when_user_added_rules_after_scalar_install(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        config_path = target / "opencode.json"
        config_path.write_text(json.dumps({"permission": "ask"}) + "\n", encoding="utf-8")

        adapter.install(gpd_root, target, is_global=False)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["permission"]["read"]["/tmp/custom/*"] = "allow"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(config_path.read_text(encoding="utf-8"))
        assert cleaned["permission"]["*"] == "ask"
        assert cleaned["permission"]["read"] == {"/tmp/custom/*": "allow"}
        assert "external_directory" not in cleaned["permission"]

    def test_uninstall_removes_only_exact_managed_permission_keys(
        self,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        adapter = OpenCodeAdapter()
        target = tmp_path / ".opencode"
        target.mkdir()

        adapter.install(gpd_root, target, is_global=False)

        config_path = target / "opencode.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        managed_key = f"{target.as_posix()}/get-physics-done/*"
        preserved_read_key = f"{target.as_posix()}/custom-get-physics-done-archive/*"
        preserved_external_key = f"{target.as_posix()}/nested/get-physics-done-backup/*"
        config["permission"]["read"][preserved_read_key] = "allow"
        config["permission"]["external_directory"][preserved_external_key] = "allow"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        adapter.uninstall(target)

        cleaned = json.loads(config_path.read_text(encoding="utf-8"))
        read_permissions = cleaned.get("permission", {}).get("read", {})
        external_permissions = cleaned.get("permission", {}).get("external_directory", {})
        assert managed_key not in read_permissions
        assert managed_key not in external_permissions
        assert read_permissions[preserved_read_key] == "allow"
        assert external_permissions[preserved_external_key] == "allow"

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
        config["mcp"]["gpd-wolfram"] = {
            "type": "local",
            "command": ["gpd-mcp-wolfram"],
            "environment": {"GPD_WOLFRAM_MCP_ENDPOINT": "https://example.invalid/api/mcp"},
        }
        config["mcp"]["custom-server"] = {"type": "local", "command": ["node", "custom.js"]}
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        result = adapter.uninstall(target)

        cleaned = json.loads(config_path.read_text(encoding="utf-8"))
        read_permissions = cleaned.get("permission", {}).get("read", {})
        external_permissions = cleaned.get("permission", {}).get("external_directory", {})
        mcp_servers = cleaned.get("mcp", {})
        assert "/tmp/custom/*" in read_permissions
        assert not any("get-physics-done" in key for key in read_permissions)
        assert not any("get-physics-done" in key for key in external_permissions)
        assert "gpd-wolfram" not in mcp_servers
        assert mcp_servers == {"custom-server": {"type": "local", "command": ["node", "custom.js"]}}
        assert any("GPD MCP servers" in item for item in result["removed"])

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

    def test_uninstall_preserves_manifestless_hook_residue_with_empty_flat_command_dir(
        self,
        adapter: OpenCodeAdapter,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        (target / "command").mkdir(parents=True)
        (target / "agents").mkdir(parents=True)
        hooks = target / "hooks"
        hooks.mkdir(parents=True)
        bundled_hooks = Path(__file__).resolve().parents[2] / "src" / "gpd" / "hooks"
        (hooks / "install_metadata.py").write_text(
            (bundled_hooks / "install_metadata.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = adapter.uninstall(target)

        assert "1 GPD hooks" not in result["removed"]
        assert (hooks / "install_metadata.py").exists()
        assert not (target / "command").exists()
        assert not (target / "agents").exists()

    def test_uninstall_restores_permissions_after_gpd_managed_yolo(
        self,
        adapter: OpenCodeAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".opencode"
        target.mkdir()
        adapter.install(gpd_root, target)
        adapter.sync_runtime_permissions(target, autonomy="yolo")

        adapter.uninstall(target)

        config_path = target / "opencode.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            permission = config.get("permission", {})
            assert permission != "allow"
            assert not any("get-physics-done" in key for key in permission.get("external_directory", {}))
