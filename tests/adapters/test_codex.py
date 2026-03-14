"""Tests for the Codex CLI runtime adapter."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from gpd.adapters.codex import CodexAdapter, _convert_codex_tool_name, _convert_to_codex_skill
from gpd.registry import load_agents_from_dir


@pytest.fixture()
def adapter() -> CodexAdapter:
    return CodexAdapter()


class TestProperties:
    def test_runtime_name(self, adapter: CodexAdapter) -> None:
        assert adapter.runtime_name == "codex"

    def test_display_name(self, adapter: CodexAdapter) -> None:
        assert adapter.display_name == "Codex"

    def test_config_dir_name(self, adapter: CodexAdapter) -> None:
        assert adapter.config_dir_name == ".codex"

    def test_help_command(self, adapter: CodexAdapter) -> None:
        assert adapter.help_command == "$gpd-help"


class TestConvertCodexToolName:
    def test_known_mappings(self) -> None:
        assert _convert_codex_tool_name("Bash") == "shell"
        assert _convert_codex_tool_name("Read") == "read_file"
        assert _convert_codex_tool_name("Write") == "write_file"
        assert _convert_codex_tool_name("Edit") == "apply_patch"
        assert _convert_codex_tool_name("Grep") == "grep"

    def test_task_excluded(self) -> None:
        assert _convert_codex_tool_name("Task") is None

    def test_mcp_passthrough(self) -> None:
        assert _convert_codex_tool_name("mcp__physics_server") == "mcp__physics_server"

    def test_unknown_passthrough(self) -> None:
        assert _convert_codex_tool_name("CustomTool") == "CustomTool"


class TestConvertToCodexSkill:
    def test_no_frontmatter_wraps(self) -> None:
        result = _convert_to_codex_skill("Just body text", "gpd-help")
        assert result.startswith("---\n")
        assert "name: gpd-help" in result
        assert "Just body text" in result

    def test_frontmatter_name_converted(self) -> None:
        content = "---\nname: gpd:help\ndescription: Show help\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-help")
        assert "name: gpd-help" in result
        assert "gpd:help" not in result

    def test_color_stripped(self) -> None:
        content = "---\nname: test\ncolor: cyan\ndescription: D\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "color:" not in result

    def test_allowed_tools_converted(self) -> None:
        content = "---\nname: test\ndescription: D\nallowed-tools:\n  - Read\n  - Bash\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "allowed-tools:" in result
        assert "read_file" in result
        assert "shell" in result

    def test_task_excluded_from_tools(self) -> None:
        content = "---\nname: test\ndescription: D\nallowed-tools:\n  - Read\n  - Task\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "Task" not in result.split("---", 2)[1]

    def test_slash_command_conversion(self) -> None:
        content = "---\nname: test\ndescription: D\n---\nUse /gpd:execute-phase to run."
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "$gpd-execute-phase" in result

    def test_path_conversion(self) -> None:
        """Path conversion is handled by replace_placeholders in the install pipeline.
        _convert_to_codex_skill only handles /gpd: -> $gpd- and frontmatter conversion."""
        content = "---\nname: test\ndescription: D\n---\nSee /gpd:execute-phase"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "$gpd-execute-phase" in result

    def test_description_preserved(self) -> None:
        content = "---\nname: test\ndescription: My description\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "description: My description" in result

    def test_description_with_triple_dash_is_preserved(self) -> None:
        content = "---\nname: test\ndescription: before --- after\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "description: before --- after" in result
        assert result.rstrip().endswith("Body")

    def test_missing_name_added(self) -> None:
        content = "---\ndescription: D\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "name: gpd-test" in result

    def test_missing_description_added(self) -> None:
        content = "---\nname: test\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "description: GPD skill - gpd-test" in result

    def test_duplicate_tools_deduplicated(self) -> None:
        """Tools appearing in both tools: and allowed-tools: are deduplicated."""
        content = (
            "---\n"
            "name: test\n"
            "description: D\n"
            "tools: Read, Bash\n"
            "allowed-tools:\n"
            "  - Read\n"
            "  - Write\n"
            "---\n"
            "Body"
        )
        result = _convert_to_codex_skill(content, "gpd-test")
        # Extract allowed-tools entries from the frontmatter
        fm = result.split("---")[1]
        tool_entries = [line.strip()[2:] for line in fm.splitlines() if line.strip().startswith("- ")]
        assert tool_entries == ["read_file", "shell", "write_file"]

    def test_duplicate_tools_in_allowed_tools_only(self) -> None:
        """Duplicate entries within allowed-tools: alone are deduplicated."""
        content = (
            "---\n"
            "name: test\n"
            "description: D\n"
            "allowed-tools:\n"
            "  - Read\n"
            "  - Bash\n"
            "  - Read\n"
            "---\n"
            "Body"
        )
        result = _convert_to_codex_skill(content, "gpd-test")
        fm = result.split("---")[1]
        tool_entries = [line.strip()[2:] for line in fm.splitlines() if line.strip().startswith("- ")]
        assert tool_entries == ["read_file", "shell"]


class TestInstall:
    def test_local_install_uses_target_skills_dir_by_default(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        global_skills = tmp_path / "global-skills"
        preserved_skill = global_skills / "gpd-keep"
        preserved_skill.mkdir(parents=True)
        (preserved_skill / "SKILL.md").write_text("keep", encoding="utf-8")
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(global_skills))

        result = adapter.install(gpd_root, target, is_global=False)

        local_skills = target / "skills"
        assert result["skills_dir"] == str(local_skills)
        assert any(d.name.startswith("gpd-") for d in local_skills.iterdir() if d.is_dir())
        assert (global_skills / "gpd-keep" / "SKILL.md").exists()

    def test_install_creates_skills(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        gpd_skills = [d for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(gpd_skills) > 0
        for skill_dir in gpd_skills:
            assert (skill_dir / "SKILL.md").exists()

    def test_install_only_exposes_public_agents_as_skills(
        self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()

        adapter.install(gpd_root, target, skills_dir=skills)

        installed_skill_names = {d.name for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-")}
        agents = load_agents_from_dir(gpd_root / "agents")
        public_agents = {agent.name for agent in agents.values() if agent.surface == "public"}
        internal_agents = {agent.name for agent in agents.values() if agent.surface == "internal"}

        assert public_agents <= installed_skill_names
        assert installed_skill_names.isdisjoint(internal_agents)

    def test_install_creates_gpd_content(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        gpd_dest = target / "get-physics-done"
        assert gpd_dest.is_dir()
        for subdir in ("references", "templates", "workflows"):
            assert (gpd_dest / subdir).is_dir()

    def test_install_creates_agents(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        agent_files = list(agents_dir.glob("gpd-*.md"))
        assert len(agent_files) >= 2

    def test_install_preserves_shell_placeholders_for_codex_agents(
        self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path
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
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        checker = (target / "agents" / "gpd-shell-vars.md").read_text(encoding="utf-8")
        assert "Use ${PHASE_ARG} and $ARGUMENTS in prose." in checker
        assert "$artifact_path" in checker
        assert 'echo "$phase_dir" "$file"' in checker
        assert "Math stays $T$." in checker

    def test_install_writes_version(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        assert (target / "get-physics-done" / "VERSION").exists()

    def test_install_configures_toml(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        config_toml = target / "config.toml"
        assert config_toml.exists()
        content = config_toml.read_text(encoding="utf-8")
        escaped_exe = (sys.executable or "python3").replace("\\", "\\\\")
        expected_notify = (
            f'notify = ["{escaped_exe}", '
            f'"{(target / "hooks" / "notify.py").as_posix()}"]'
        )
        assert "# GPD update notification" in content
        assert expected_notify in content
        assert "[features]" in content
        assert "multi_agent = true" in content

    def test_install_writes_codex_mcp_startup_timeout(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()

        adapter.install(gpd_root, target, skills_dir=skills)

        parsed = tomllib.loads((target / "config.toml").read_text(encoding="utf-8"))
        assert parsed["mcp_servers"]["gpd-state"]["startup_timeout_sec"] == 30

    def test_install_notify_not_inside_existing_section(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        """Notify must be at TOML root level, not inside an existing section."""
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()

        # Pre-populate config.toml with a section that would swallow the notify
        (target / "config.toml").write_text(
            '[notice.model_migrations]\n"gpt-5.3-codex" = "gpt-5.4"\n',
            encoding="utf-8",
        )

        adapter.install(gpd_root, target, skills_dir=skills)

        content = (target / "config.toml").read_text(encoding="utf-8")
        # Verify notify appears BEFORE the section, not inside it
        notify_pos = content.index("notify =")
        section_pos = content.index("[notice.model_migrations]")
        assert notify_pos < section_pos, (
            f"notify (pos {notify_pos}) must appear before [notice.model_migrations] (pos {section_pos}) "
            f"to stay at TOML root level. Full content:\n{content}"
        )

    def test_install_with_explicit_target_uses_absolute_notify_path(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "custom-codex"
        target.mkdir()

        adapter.install(gpd_root, target, is_global=False, explicit_target=True)

        content = (target / "config.toml").read_text(encoding="utf-8")
        assert f'"{(target / "hooks" / "notify.py").as_posix()}"' in content
        assert '".codex/hooks/notify.py"' not in content

    def test_reinstall_rewrites_stale_managed_notify_interpreter(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        (target / "config.toml").write_text(
            '# GPD update notification\nnotify = ["python3", ".codex/hooks/notify.py"]\n',
            encoding="utf-8",
        )
        monkeypatch.setattr("gpd.adapters.install_utils.sys.executable", "/custom/venv/bin/python")

        adapter.install(gpd_root, target, is_global=False)

        content = (target / "config.toml").read_text(encoding="utf-8")
        assert 'notify = ["/custom/venv/bin/python", ".codex/hooks/notify.py"]' in content
        assert 'notify = ["python3", ".codex/hooks/notify.py"]' not in content

    def test_install_writes_manifest(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        assert (target / "gpd-file-manifest.json").exists()

    def test_install_returns_counts(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        result = adapter.install(gpd_root, target, skills_dir=skills)

        assert result["runtime"] == "codex"
        assert result["skills"] > 0
        assert result["agents"] > 0

    def test_install_nested_commands_flattened(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        # commands/sub/deep.md should become gpd-sub-deep/ skill
        assert (skills / "gpd-sub-deep" / "SKILL.md").exists()

    def test_nested_command_include_expands_in_recursive_codex_install(
        self,
        adapter: CodexAdapter,
        tmp_path: Path,
    ) -> None:
        source_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        gpd_root = tmp_path / "gpd"
        shutil.copytree(source_root, gpd_root)

        nested_command = gpd_root / "commands" / "nested" / "include.md"
        nested_command.parent.mkdir(parents=True, exist_ok=True)
        nested_command.write_text(
            """---
name: gpd:nested-include
description: Nested command include expansion regression
---

<execution_context>
@{GPD_INSTALL_DIR}/workflows/update.md
</execution_context>
""",
            encoding="utf-8",
        )

        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        content = (skills / "gpd-nested-include" / "SKILL.md").read_text(encoding="utf-8")
        assert "<!-- [included: update.md] -->" in content
        assert "Check for a newer GPD release" in content
        assert re.search(r"^\s*@.*?/workflows/update\.md\s*$", content, flags=re.MULTILINE) is None

    def test_update_skill_expands_workflow_include(
        self,
        adapter: CodexAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        content = (skills / "gpd-update" / "SKILL.md").read_text(encoding="utf-8")
        assert "<!-- [included: update.md] -->" in content
        assert "Check for a newer GPD release" in content
        assert re.search(r"^\s*@.*?/workflows/update\.md\s*$", content, flags=re.MULTILINE) is None
        assert "$gpd-reapply-patches" in content

    def test_complete_milestone_skill_expands_bullet_list_includes(
        self,
        adapter: CodexAdapter,
        tmp_path: Path,
    ) -> None:
        gpd_root = Path(__file__).resolve().parents[2] / "src" / "gpd"
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        content = (skills / "gpd-complete-milestone" / "SKILL.md").read_text(encoding="utf-8")
        assert "<!-- [included: complete-milestone.md] -->" in content
        assert "<!-- [included: milestone-archive.md] -->" in content
        assert "Mark a completed research stage" in content
        assert "# Milestone Archive Template" in content
        assert re.search(r"^\s*-\s*@.*?/workflows/complete-milestone\.md.*$", content, flags=re.MULTILINE) is None
        assert re.search(r"^\s*-\s*@.*?/templates/milestone-archive\.md.*$", content, flags=re.MULTILINE) is None


class TestUninstall:
    def test_global_uninstall_uses_manifest_skills_dir_when_env_drifts(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        original_shared_skills = tmp_path / "shared-skills-a"
        monkeypatch.setenv("CODEX_CONFIG_DIR", str(target))
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(original_shared_skills))

        adapter.install(gpd_root, target, is_global=True)

        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        assert manifest["codex_skills_dir"] == str(original_shared_skills)

        drifted_shared_skills = tmp_path / "shared-skills-b"
        preserved_skill = drifted_shared_skills / "gpd-foreign"
        preserved_skill.mkdir(parents=True)
        (preserved_skill / "SKILL.md").write_text("keep", encoding="utf-8")
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(drifted_shared_skills))

        adapter.uninstall(target)

        assert not any(
            entry.is_dir() and entry.name.startswith("gpd-")
            for entry in original_shared_skills.iterdir()
        )
        assert (preserved_skill / "SKILL.md").exists()

    def test_local_uninstall_uses_target_skills_dir_by_default(
        self,
        adapter: CodexAdapter,
        gpd_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        global_skills = tmp_path / "global-skills"
        preserved_skill = global_skills / "gpd-keep"
        preserved_skill.mkdir(parents=True)
        (preserved_skill / "SKILL.md").write_text("keep", encoding="utf-8")
        monkeypatch.setenv("CODEX_SKILLS_DIR", str(global_skills))

        adapter.install(gpd_root, target, is_global=False)
        adapter.uninstall(target)

        local_skills = target / "skills"
        assert not any(d.name.startswith("gpd-") for d in local_skills.iterdir() if d.is_dir())
        assert (global_skills / "gpd-keep" / "SKILL.md").exists()

    def test_uninstall_removes_skills(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        result = adapter.uninstall(target, skills_dir=skills)

        gpd_skills = [d for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(gpd_skills) == 0
        assert any("skills" in item for item in result["removed"])

    def test_uninstall_removes_agents(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        # Add non-GPD agent to make sure it survives
        (target / "agents" / "custom.md").write_text("keep", encoding="utf-8")

        adapter.uninstall(target, skills_dir=skills)

        agents_dir = target / "agents"
        assert not any(f.name.startswith("gpd-") for f in agents_dir.iterdir())
        assert (agents_dir / "custom.md").exists()

    def test_uninstall_cleans_toml(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)
        adapter.uninstall(target, skills_dir=skills)

        config_toml = target / "config.toml"
        if config_toml.exists():
            content = config_toml.read_text(encoding="utf-8")
            assert "gpd-" not in content
            assert "notify.py" not in content
            assert "multi_agent" not in content

    def test_uninstall_on_empty_dir(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        target = tmp_path / "empty"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        result = adapter.uninstall(target, skills_dir=skills)
        assert result["removed"] == []

    def test_uninstall_preserves_non_gpd_toml_lines(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        """Uninstall must not destroy user TOML content that happens to contain 'gpd-'."""
        target = tmp_path / ".codex"
        target.mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            'model = "gpt-4"\n'
            '# My notes about gpd-style naming\n'
            'custom = "my-gpd-tool"\n'
            f'notify = ["{sys.executable or "python3"}", "/path/notify.py"]\n',
            encoding="utf-8",
        )
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        content = config_toml.read_text(encoding="utf-8")
        assert 'model = "gpt-4"' in content
        assert "gpd-style naming" in content
        assert 'custom = "my-gpd-tool"' in content
        assert f'notify = ["{sys.executable or "python3"}", "/path/notify.py"]' in content

    def test_uninstall_removes_gpd_comment_with_notify(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        """The '# GPD update notification' comment should be cleaned alongside the notify line."""
        target = tmp_path / ".codex"
        target.mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            'model = "gpt-4"\n'
            "\n"
            "# GPD update notification\n"
            f'notify = ["{sys.executable or "python3"}", "/path/notify.py"]\n',
            encoding="utf-8",
        )
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        content = config_toml.read_text(encoding="utf-8")
        assert "GPD update notification" not in content
        assert "notify.py" not in content


class TestNotifyConfiguration:
    def test_wraps_existing_notify_and_restores_it_on_uninstall(
        self,
        adapter: CodexAdapter,
        tmp_path: Path,
    ) -> None:
        from gpd.adapters.codex import _configure_config_toml

        target = tmp_path / ".codex"
        target.mkdir()
        (target / "hooks").mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            'model = "gpt-5"\n'
            'notify = ["toolctl", "/path/to/my-tool"]\n',
            encoding="utf-8",
        )

        _configure_config_toml(target, is_global=True)

        content = config_toml.read_text(encoding="utf-8")
        assert '# GPD original notify: ["toolctl", "/path/to/my-tool"]' in content
        escaped_exe = (sys.executable or "python3").replace("\\", "\\\\")
        assert f'notify = ["{escaped_exe}", "-c",' in content
        assert "gpd-codex-notify-wrapper-v1" in content
        assert "/path/to/my-tool" in content
        assert "notify.py" in content

        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        cleaned = config_toml.read_text(encoding="utf-8")
        assert 'notify = ["toolctl", "/path/to/my-tool"]' in cleaned
        assert "notify.py" not in cleaned
        assert "GPD original notify" not in cleaned

    def test_wraps_custom_notify_py_and_restores_it_on_uninstall(
        self,
        adapter: CodexAdapter,
        tmp_path: Path,
    ) -> None:
        from gpd.adapters.codex import _configure_config_toml

        target = tmp_path / ".codex"
        target.mkdir()
        (target / "hooks").mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            'notify = ["python", "/Users/me/custom/notify.py"]\n',
            encoding="utf-8",
        )

        _configure_config_toml(target, is_global=False)

        content = config_toml.read_text(encoding="utf-8")
        assert '# GPD original notify: ["python", "/Users/me/custom/notify.py"]' in content
        assert 'notify = ["python", "/Users/me/custom/notify.py"]' not in content
        assert "gpd-codex-notify-wrapper-v1" in content

        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        cleaned = config_toml.read_text(encoding="utf-8")
        assert 'notify = ["python", "/Users/me/custom/notify.py"]' in cleaned
        assert "gpd-codex-notify-wrapper-v1" not in cleaned
        assert "GPD original notify" not in cleaned

    def test_mcp_toml_escapes_windows_paths(self, tmp_path: Path) -> None:
        from gpd.adapters.codex import _write_mcp_servers_codex_toml

        target = tmp_path / ".codex"
        target.mkdir()

        count = _write_mcp_servers_codex_toml(
            target,
            {
                "gpd-test": {
                    "command": r"C:\Python311\python.exe",
                    "args": [r"C:\Program Files\GPD\server.py"],
                    "env": {"PYTHONPATH": r"C:\Users\tester\venv"},
                }
            },
        )

        content = (target / "config.toml").read_text(encoding="utf-8")
        assert count == 1
        assert r'command = "C:\\Python311\\python.exe"' in content
        assert r'args = ["C:\\Program Files\\GPD\\server.py"]' in content
        assert r'PYTHONPATH = "C:\\Users\\tester\\venv"' in content

    def test_mcp_toml_preserves_user_overrides_and_custom_fields(self, tmp_path: Path) -> None:
        from gpd.adapters.codex import _write_mcp_servers_codex_toml

        target = tmp_path / ".codex"
        target.mkdir()
        (target / "config.toml").write_text(
            '[mcp_servers.gpd-state]\n'
            'command = "python3"\n'
            'args = ["-m", "old.server"]\n'
            'startup_timeout_sec = 45\n'
            'cwd = "/tmp/custom-gpd"\n'
            '\n'
            '[mcp_servers.gpd-state.env]\n'
            'LOG_LEVEL = "INFO"\n'
            'EXTRA_FLAG = "1"\n',
            encoding="utf-8",
        )

        count = _write_mcp_servers_codex_toml(
            target,
            {
                "gpd-state": {
                    "command": "/custom/venv/bin/python",
                    "args": ["-m", "gpd.mcp.servers.state_server"],
                    "env": {"LOG_LEVEL": "WARNING"},
                }
            },
        )

        parsed = tomllib.loads((target / "config.toml").read_text(encoding="utf-8"))
        server = parsed["mcp_servers"]["gpd-state"]
        assert count == 1
        assert server["command"] == "/custom/venv/bin/python"
        assert server["args"] == ["-m", "gpd.mcp.servers.state_server"]
        assert server["startup_timeout_sec"] == 45
        assert server["cwd"] == "/tmp/custom-gpd"
        assert server["env"] == {"LOG_LEVEL": "INFO", "EXTRA_FLAG": "1"}

    def test_wraps_existing_false_multi_agent_and_restores_it_on_uninstall(
        self,
        adapter: CodexAdapter,
        tmp_path: Path,
    ) -> None:
        from gpd.adapters.codex import _configure_config_toml

        target = tmp_path / ".codex"
        target.mkdir()
        (target / "hooks").mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            '[features]\n'
            'multi_agent = false\n',
            encoding="utf-8",
        )

        _configure_config_toml(target, is_global=True)

        content = config_toml.read_text(encoding="utf-8")
        assert "# GPD original multi_agent: multi_agent = false" in content
        assert "multi_agent = true" in content

        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        cleaned = config_toml.read_text(encoding="utf-8")
        assert "GPD original multi_agent" not in cleaned
        assert "multi_agent = false" in cleaned
        assert "multi_agent = true" not in cleaned
