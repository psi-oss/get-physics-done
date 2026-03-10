"""Tests for the Codex CLI runtime adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from gpd.adapters.codex import CodexAdapter, _convert_codex_tool_name, _convert_to_codex_skill


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


class TestTranslateToolName:
    def test_canonical_to_codex(self, adapter: CodexAdapter) -> None:
        assert adapter.translate_tool_name("file_read") == "read_file"
        assert adapter.translate_tool_name("file_edit") == "apply_patch"
        assert adapter.translate_tool_name("shell") == "shell"

    def test_runtime_native_alias(self, adapter: CodexAdapter) -> None:
        assert adapter.translate_tool_name("Read") == "read_file"
        assert adapter.translate_tool_name("Edit") == "apply_patch"


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

    def test_missing_name_added(self) -> None:
        content = "---\ndescription: D\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "name: gpd-test" in result

    def test_missing_description_added(self) -> None:
        content = "---\nname: test\n---\nBody"
        result = _convert_to_codex_skill(content, "gpd-test")
        assert "description: GPD skill - gpd-test" in result


class TestGenerateCommand:
    def test_creates_skill_dir(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        result = adapter.generate_command({"name": "gpd-help", "content": "---\nname: help\n---\nBody"}, tmp_path)
        assert result == tmp_path / "gpd-help" / "SKILL.md"
        assert result.exists()

    def test_skill_has_codex_frontmatter(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        adapter.generate_command(
            {"name": "gpd-help", "content": "---\nname: gpd:help\ndescription: Help\ncolor: cyan\n---\nBody"},
            tmp_path,
        )
        content = (tmp_path / "gpd-help" / "SKILL.md").read_text(encoding="utf-8")
        assert "name: gpd-help" in content
        assert "color:" not in content


class TestGenerateAgent:
    def test_creates_skill_dir(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        result = adapter.generate_agent(
            {"name": "gpd-verifier", "content": "---\nname: gpd-verifier\n---\nPrompt"},
            tmp_path,
        )
        assert result == tmp_path / "gpd-verifier" / "SKILL.md"
        assert result.exists()


class TestGenerateHook:
    def test_returns_notify_array(self, adapter: CodexAdapter) -> None:
        result = adapter.generate_hook("notify", {"command": "check_update.py"})
        assert result == {"notify": [sys.executable or "python3", "check_update.py"]}


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
        expected_interpreter = (sys.executable or "python3").replace("\\", "\\\\")
        expected_notify = (
            f'notify = ["{expected_interpreter}", '
            f'"{(target / "hooks" / "codex_notify.py").as_posix()}"]'
        )
        assert "# GPD update notification" in content
        assert expected_notify in content
        assert "[features]" in content
        assert "multi_agent = true" in content

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
        assert f'"{(target / "hooks" / "codex_notify.py").as_posix()}"' in content
        assert '".codex/hooks/codex_notify.py"' not in content

    def test_install_writes_manifest(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.install(gpd_root, target, skills_dir=skills)

        assert (target / "gpd-file-manifest.json").exists()

    def test_install_writes_mcp_startup_timeout(self, adapter: CodexAdapter, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()

        adapter.install(gpd_root, target, skills_dir=skills)

        content = (target / "config.toml").read_text(encoding="utf-8")
        assert "[mcp_servers.gpd-skills]" in content
        assert "startup_timeout_sec = 30" in content

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
            assert "codex_notify" not in content
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
            f'notify = ["{sys.executable or "python3"}", "/path/codex_notify.py"]\n',
            encoding="utf-8",
        )
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        content = config_toml.read_text(encoding="utf-8")
        assert 'model = "gpt-4"' in content
        assert "gpd-style naming" in content
        assert 'custom = "my-gpd-tool"' in content
        assert "codex_notify" not in content

    def test_uninstall_removes_gpd_comment_with_notify(self, adapter: CodexAdapter, tmp_path: Path) -> None:
        """The '# GPD update notification' comment should be cleaned alongside the notify line."""
        target = tmp_path / ".codex"
        target.mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            'model = "gpt-4"\n'
            "\n"
            "# GPD update notification\n"
            f'notify = ["{sys.executable or "python3"}", "/path/codex_notify.py"]\n',
            encoding="utf-8",
        )
        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        content = config_toml.read_text(encoding="utf-8")
        assert "GPD update notification" not in content
        assert "codex_notify" not in content


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
        assert 'notify = ["sh", "-c",' in content
        assert "/path/to/my-tool" in content
        assert "codex_notify.py" in content

        skills = tmp_path / "skills"
        skills.mkdir()
        adapter.uninstall(target, skills_dir=skills)

        cleaned = config_toml.read_text(encoding="utf-8")
        assert 'notify = ["toolctl", "/path/to/my-tool"]' in cleaned
        assert "codex_notify" not in cleaned
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

    def test_mcp_toml_preserves_existing_startup_timeout_override(self, tmp_path: Path) -> None:
        from gpd.adapters.codex import _write_mcp_servers_codex_toml

        target = tmp_path / ".codex"
        target.mkdir()
        (target / "config.toml").write_text(
            '[mcp_servers.gpd-skills]\n'
            'command = "python"\n'
            'args = ["-m", "gpd.mcp.servers.skills_server"]\n'
            "startup_timeout_sec = 45\n"
            "\n"
            "[mcp_servers.gpd-skills.env]\n"
            'LOG_LEVEL = "INFO"\n',
            encoding="utf-8",
        )

        _write_mcp_servers_codex_toml(
            target,
            {
                "gpd-skills": {
                    "command": "python3",
                    "args": ["-m", "gpd.mcp.servers.skills_server"],
                    "startup_timeout_sec": 30,
                    "env": {"LOG_LEVEL": "WARNING"},
                }
            },
        )

        content = (target / "config.toml").read_text(encoding="utf-8")
        assert 'command = "python3"' in content
        assert "startup_timeout_sec = 45" in content
        assert "startup_timeout_sec = 30" not in content
        assert 'LOG_LEVEL = "INFO"' in content
        assert 'LOG_LEVEL = "WARNING"' not in content

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

    def test_notify_stays_top_level_when_config_already_has_tables(self, tmp_path: Path) -> None:
        from gpd.adapters.codex import _configure_config_toml

        target = tmp_path / ".codex"
        target.mkdir()
        (target / "hooks").mkdir()
        config_toml = target / "config.toml"
        config_toml.write_text(
            'model = "gpt-5.4"\n'
            '[projects."/tmp/example"]\n'
            'trust_level = "trusted"\n'
            '\n'
            "[notice.model_migrations]\n"
            '"gpt-5.3-codex" = "gpt-5.4"\n',
            encoding="utf-8",
        )

        _configure_config_toml(target, is_global=True)

        content = config_toml.read_text(encoding="utf-8")
        notify_line = f'notify = ["{sys.executable or "python3"}", "{(target / "hooks" / "codex_notify.py").as_posix()}"]'
        assert content.index(notify_line) < content.index('[projects."/tmp/example"]')
        assert "notice.model_migrations.notify" not in content
