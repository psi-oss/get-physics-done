"""Tests for the base RuntimeAdapter ABC and shared behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.adapters import get_adapter


class TestResolveTargetDir:
    """Test resolve_target_dir for all adapters."""

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_local_uses_cwd(self, runtime: str, tmp_path: Path) -> None:
        adapter = get_adapter(runtime)
        result = adapter.resolve_target_dir(is_global=False, cwd=tmp_path)
        assert result == tmp_path / adapter.config_dir_name

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_global_uses_global_config(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        result = adapter.resolve_target_dir(is_global=True)
        assert result == adapter.global_config_dir


class TestUninstallBase:
    """Test the base uninstall method (used by Claude Code adapter)."""

    def test_removes_commands_gpd(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        (target / "commands" / "gpd").mkdir(parents=True)
        (target / "commands" / "gpd" / "help.md").write_text("help", encoding="utf-8")

        result = adapter.uninstall(target)
        assert not (target / "commands" / "gpd").exists()
        assert "commands/gpd/" in result["removed"]

    def test_removes_get_physics_done(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        (target / "get-physics-done").mkdir(parents=True)
        (target / "get-physics-done" / "file.md").write_text("x", encoding="utf-8")

        result = adapter.uninstall(target)
        assert not (target / "get-physics-done").exists()
        assert "get-physics-done/" in result["removed"]

    def test_removes_only_gpd_agents(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        agents = target / "agents"
        agents.mkdir(parents=True)
        (agents / "gpd-verifier.md").write_text("v", encoding="utf-8")
        (agents / "gpd-executor.md").write_text("e", encoding="utf-8")
        (agents / "custom-agent.md").write_text("c", encoding="utf-8")

        adapter.uninstall(target)

        assert not (agents / "gpd-verifier.md").exists()
        assert not (agents / "gpd-executor.md").exists()
        assert (agents / "custom-agent.md").exists()

    def test_removes_gpd_hooks(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        hooks = target / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "statusline.py").write_text("s", encoding="utf-8")
        (hooks / "check_update.py").write_text("u", encoding="utf-8")
        (hooks / "user-hook.py").write_text("keep", encoding="utf-8")

        adapter.uninstall(target)

        assert not (hooks / "statusline.py").exists()
        assert not (hooks / "check_update.py").exists()
        assert (hooks / "user-hook.py").exists()

    def test_removes_manifest(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir(parents=True)
        (target / "gpd-file-manifest.json").write_text("{}", encoding="utf-8")

        adapter.uninstall(target)
        assert not (target / "gpd-file-manifest.json").exists()

    def test_removes_patches_dir(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        patches = target / "gpd-local-patches"
        patches.mkdir(parents=True)
        (patches / "backup.md").write_text("b", encoding="utf-8")

        adapter.uninstall(target)
        assert not patches.exists()

    def test_empty_dir_returns_empty_removed(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / "empty"
        target.mkdir()
        result = adapter.uninstall(target)
        assert result["removed"] == []

    def test_uninstall_cleans_jsonc_settings(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir(parents=True)
        (target / "settings.json").write_text(
            '{\n'
            '  // user comment\n'
            '  "statusLine": {"type": "command", "command": "python .claude/hooks/statusline.py"},\n'
            '  "hooks": {\n'
            '    "SessionStart": [\n'
            '      {"hooks": [{"type": "command", "command": "python .claude/hooks/check_update.py"}]}\n'
            "    ]\n"
            "  },\n"
            '  "theme": "solarized",\n'
            "}\n",
            encoding="utf-8",
        )

        adapter.uninstall(target)

        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
        assert settings["theme"] == "solarized"
        assert "statusLine" not in settings
        assert settings.get("hooks") in ({}, None)


class TestAdapterConformance:
    """Verify all adapters implement the runtime-facing interface."""

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_has_required_properties(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert isinstance(adapter.runtime_name, str)
        assert isinstance(adapter.display_name, str)
        assert isinstance(adapter.config_dir_name, str)
        assert isinstance(adapter.help_command, str)
        assert isinstance(adapter.global_config_dir, Path)

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_has_required_methods(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert callable(adapter.finalize_install)
        assert callable(adapter.format_command)
        assert callable(adapter.install)
        assert callable(adapter.uninstall)

    @pytest.mark.parametrize(
        ("runtime", "expected"),
        [
            ("claude-code", "/gpd:help"),
            ("gemini", "/gpd:help"),
            ("codex", "$gpd-help"),
            ("opencode", "/gpd-help"),
        ],
    )
    def test_help_command_uses_runtime_formatter(self, runtime: str, expected: str) -> None:
        adapter = get_adapter(runtime)
        assert adapter.help_command == expected

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_config_dir_name_starts_with_dot(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert adapter.config_dir_name.startswith(".")

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_runtime_name_matches_registry(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert adapter.runtime_name == runtime
