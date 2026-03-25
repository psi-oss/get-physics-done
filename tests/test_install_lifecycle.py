"""Install → uninstall → reinstall lifecycle tests for each runtime adapter.

Exercises the full lifecycle for claude-code, gemini, codex, and opencode:
1. Install to a temp directory
2. Verify expected files exist
3. Uninstall
4. Verify cleanup
5. Reinstall
6. Verify files exist again

Also tests manifest read/write correctness across cycles.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.adapters import get_adapter, iter_runtime_descriptors
from gpd.adapters.install_utils import MANIFEST_NAME, build_runtime_cli_bridge_command, file_hash
from gpd.cli import app

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_ALL_RUNTIMES = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)
runner = CliRunner()


def _install_kwargs_for_runtime(tmp_path: Path, runtime: str, *, is_global: bool, explicit_target: bool = False) -> dict[str, object]:
    adapter = get_adapter(runtime)
    install_kwargs: dict[str, object] = {"is_global": is_global}
    if explicit_target:
        install_kwargs["explicit_target"] = True
    if "skills/" in adapter.runtime_descriptor.manifest_file_prefixes:
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        install_kwargs["skills_dir"] = skills_dir
    return install_kwargs


def _install_and_finalize(adapter, gpd_root: Path, target: Path, **install_kwargs: object) -> dict[str, object]:
    result = adapter.install(gpd_root, target, **install_kwargs)
    adapter.finalize_install(result)
    return result


def _expected_bridge_for_install(
    adapter,
    target: Path,
    *,
    is_global: bool,
    explicit_target: bool = False,
) -> str:
    return build_runtime_cli_bridge_command(
        adapter.runtime_name,
        target_dir=target,
        config_dir_name=adapter.config_dir_name,
        is_global=is_global,
        explicit_target=explicit_target,
    )

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gpd_root() -> Path:
    """Return the GPD package data root (contains commands/, agents/, specs/, hooks/)."""
    root = Path(__file__).resolve().parent.parent / "src" / "gpd"
    assert (root / "commands").is_dir(), f"GPD commands dir not found at {root / 'commands'}"
    assert (root / "agents").is_dir(), f"GPD agents dir not found at {root / 'agents'}"
    assert (root / "specs").is_dir(), f"GPD specs dir not found at {root / 'specs'}"
    assert (root / "hooks").is_dir(), f"GPD hooks dir not found at {root / 'hooks'}"
    return root


# ---------------------------------------------------------------------------
# Claude Code lifecycle
# ---------------------------------------------------------------------------


class TestClaudeCodeLifecycle:
    """Full install → uninstall → reinstall for Claude Code adapter."""

    runtime_name = "claude-code"

    def test_install_creates_expected_structure(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        result = _install_and_finalize(adapter, gpd_root, target, is_global=True)

        # Commands installed
        commands_dir = target / "commands" / "gpd"
        assert commands_dir.is_dir()
        md_files = list(commands_dir.rglob("*.md"))
        assert len(md_files) > 0, "No command .md files installed"
        assert "context_mode:" in md_files[0].read_text(encoding="utf-8")

        # Agents installed
        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        agent_files = [f for f in agents_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(agent_files) > 0, "No GPD agent files installed"

        # get-physics-done content installed
        gpd_dir = target / "get-physics-done"
        assert gpd_dir.is_dir()
        assert (gpd_dir / "VERSION").exists()

        # Hooks installed
        hooks_dir = target / "hooks"
        assert hooks_dir.is_dir()

        # Manifest written
        manifest_path = target / MANIFEST_NAME
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "version" in manifest
        assert "files" in manifest
        assert len(manifest["files"]) > 0

        # Result dict has expected keys
        assert result["runtime"] == "claude-code"
        assert result["commands"] > 0
        assert result["agents"] > 0

    def test_uninstall_removes_gpd_artifacts(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)
        result = adapter.uninstall(target)

        # GPD commands removed
        assert not (target / "commands" / "gpd").exists()

        # GPD agents removed
        agents_dir = target / "agents"
        gpd_agents = [f for f in agents_dir.iterdir() if f.name.startswith("gpd-")] if agents_dir.exists() else []
        assert len(gpd_agents) == 0

        # get-physics-done removed
        assert not (target / "get-physics-done").exists()

        # Manifest removed
        assert not (target / MANIFEST_NAME).exists()

        # Result reports removals
        assert len(result["removed"]) > 0

    def test_reinstall_after_uninstall(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        # Install → uninstall → reinstall
        _install_and_finalize(adapter, gpd_root, target, is_global=True)
        adapter.uninstall(target)
        result = _install_and_finalize(adapter, gpd_root, target, is_global=True)

        # Verify reinstall succeeded
        assert (target / "commands" / "gpd").is_dir()
        agents_dir = target / "agents"
        agent_files = [f for f in agents_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(agent_files) > 0
        assert (target / "get-physics-done" / "VERSION").exists()
        assert (target / MANIFEST_NAME).exists()
        assert result["commands"] > 0

    def test_manifest_hashes_match_files(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        for rel_path, expected_hash in manifest["files"].items():
            full_path = target / rel_path
            assert full_path.exists(), f"Manifest lists {rel_path} but file missing"
            actual_hash = file_hash(full_path)
            assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}"

    def test_slides_command_installed(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        slides_md = target / "commands" / "gpd" / "slides.md"
        assert slides_md.exists()
        content = slides_md.read_text(encoding="utf-8")
        assert "context_mode: projectless" in content
        assert "/get-physics-done/workflows/slides.md" in content

    def test_inline_gpd_commands_are_rewritten_to_the_bridge(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        bridge_command = _expected_bridge_for_install(adapter, target, is_global=True)
        content = (target / "commands" / "gpd" / "suggest-next.md").read_text(encoding="utf-8")
        assert bridge_command in content
        assert "Uses `gpd --raw suggest`" not in content
        assert "`gpd --raw suggest`" not in content


# ---------------------------------------------------------------------------
# Gemini lifecycle
# ---------------------------------------------------------------------------


class TestGeminiLifecycle:
    """Full install → uninstall → reinstall for Gemini adapter."""

    runtime_name = "gemini"

    def test_install_creates_expected_structure(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        result = _install_and_finalize(adapter, gpd_root, target, is_global=True)

        # Commands as TOML (Gemini-specific)
        commands_dir = target / "commands" / "gpd"
        assert commands_dir.is_dir()
        toml_files = list(commands_dir.rglob("*.toml"))
        assert len(toml_files) > 0, "No command .toml files installed"
        assert "context_mode =" in toml_files[0].read_text(encoding="utf-8")

        # Agents installed
        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        agent_files = [f for f in agents_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(agent_files) > 0

        # get-physics-done content
        gpd_dir = target / "get-physics-done"
        assert gpd_dir.is_dir()
        assert (gpd_dir / "VERSION").exists()

        # Hooks and manifest
        assert (target / "hooks").is_dir()
        assert (target / MANIFEST_NAME).exists()

        # Result dict
        assert result["runtime"] == "gemini"
        assert result["commands"] > 0

    def test_gemini_agents_have_tools_not_allowed_tools(self, tmp_path: Path, gpd_root: Path) -> None:
        """Gemini agents should use `tools:` not `allowed-tools:` in frontmatter."""
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        agents_dir = target / "agents"
        for agent_file in agents_dir.iterdir():
            if agent_file.name.startswith("gpd-") and agent_file.suffix == ".md":
                content = agent_file.read_text(encoding="utf-8")
                assert "allowed-tools:" not in content, (
                    f"{agent_file.name} still has 'allowed-tools:' — should be 'tools:'"
                )

    def test_gemini_command_prompts_do_not_keep_shell_captures(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        bridge_command = _expected_bridge_for_install(adapter, target, is_global=True)
        content = (target / "commands" / "gpd" / "write-paper.toml").read_text(encoding="utf-8")
        assert bridge_command in content
        assert "$(gpd" not in content
        assert "CONV_CHECK=$(gpd" not in content
        assert "QUALITY=$(gpd" not in content

    def test_uninstall_removes_gpd_artifacts(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        settings_path = target / "settings.json"
        assert settings_path.exists()
        installed_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert "statusLine" in installed_settings
        assert any(
            isinstance(entry, dict) and entry.get("hooks")
            for entry in installed_settings.get("hooks", {}).get("SessionStart", [])
        )
        assert installed_settings.get("experimental", {}).get("enableAgents") is True

        adapter.uninstall(target)

        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()
        assert not (target / MANIFEST_NAME).exists()

        # Verify settings.json cleaned up
        if settings_path.exists():
            cleaned = json.loads(settings_path.read_text(encoding="utf-8"))
            assert "statusLine" not in cleaned
            assert "experimental" not in cleaned or not cleaned.get("experimental", {}).get("enableAgents")

    def test_reinstall_after_uninstall(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)
        adapter.uninstall(target)
        result = _install_and_finalize(adapter, gpd_root, target, is_global=True)

        assert (target / "commands" / "gpd").is_dir()
        assert (target / "get-physics-done" / "VERSION").exists()
        assert (target / MANIFEST_NAME).exists()
        assert result["commands"] > 0

    def test_manifest_hashes_match_files(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        for rel_path, expected_hash in manifest["files"].items():
            full_path = target / rel_path
            assert full_path.exists(), f"Manifest lists {rel_path} but file missing"
            assert file_hash(full_path) == expected_hash, f"Hash mismatch for {rel_path}"

    def test_slides_command_installed(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        slides_toml = target / "commands" / "gpd" / "slides.toml"
        assert slides_toml.exists()
        content = slides_toml.read_text(encoding="utf-8")
        assert 'context_mode = "projectless"' in content
        assert "PRESENTATION-BRIEF.md" in content


# ---------------------------------------------------------------------------
# Codex lifecycle
# ---------------------------------------------------------------------------


class TestCodexLifecycle:
    """Full install → uninstall → reinstall for Codex adapter."""

    runtime_name = "codex"

    def test_install_creates_expected_structure(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        result = _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        # Discoverable Codex skills installed (commands only).
        gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(gpd_skills) > 0, "No GPD skill directories installed"
        for skill_dir in gpd_skills:
            assert (skill_dir / "SKILL.md").exists(), f"Missing SKILL.md in {skill_dir.name}"
        help_skill = skills_dir / "gpd-help" / "SKILL.md"
        assert help_skill.exists()
        assert "context_mode:" in help_skill.read_text(encoding="utf-8")
        assert not (skills_dir / "gpd-planner").exists()

        # The full GPD agent catalog still installs as agent .md files.
        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        assert (agents_dir / "gpd-planner.toml").exists()

        # get-physics-done content
        assert (target / "get-physics-done").is_dir()
        assert (target / "get-physics-done" / "VERSION").exists()

        # config.toml with notify hook
        assert (target / "config.toml").exists()
        toml_content = (target / "config.toml").read_text(encoding="utf-8")
        assert "notify" in toml_content
        assert "multi_agent = true" in toml_content
        assert "[agents.gpd-planner]" in toml_content

        # Manifest
        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert manifest["codex_generated_skill_dirs"]
        assert all(name.startswith("gpd-") for name in manifest["codex_generated_skill_dirs"])

        # Result dict
        assert result["runtime"] == "codex"
        assert result["agentRoles"] > 0

    def test_codex_skills_have_hyphen_names(self, tmp_path: Path, gpd_root: Path) -> None:
        """Codex skill names should be hyphen-case (a-z0-9-)."""
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir() and skill_dir.name.startswith("gpd-"):
                # Skill directory name should only contain [a-z0-9-]
                assert all(c.isalnum() or c == "-" for c in skill_dir.name), (
                    f"Skill name {skill_dir.name} has invalid characters"
                )

    def test_uninstall_removes_gpd_artifacts(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)
        result = adapter.uninstall(target, skills_dir=skills_dir)

        # Discoverable Codex skills removed
        gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")] if skills_dir.exists() else []
        assert len(gpd_skills) == 0, f"Skills not removed: {[d.name for d in gpd_skills]}"

        # get-physics-done removed
        assert not (target / "get-physics-done").exists()

        # Manifest removed
        assert not (target / MANIFEST_NAME).exists()

        # GPD agents removed
        agents_dir = target / "agents"
        gpd_agents = [f for f in agents_dir.iterdir() if f.name.startswith("gpd-")] if agents_dir.exists() else []
        assert len(gpd_agents) == 0

        # Result has counts
        assert result["skills"] > 0

    def test_uninstall_preserves_user_owned_gpd_skill_dir(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)
        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        tracked_skill_names = set(manifest["codex_generated_skill_dirs"])

        preserved_skill = skills_dir / "gpd-user-keep"
        preserved_skill.mkdir()
        (preserved_skill / "SKILL.md").write_text("keep", encoding="utf-8")

        adapter.uninstall(target, skills_dir=skills_dir)

        assert (preserved_skill / "SKILL.md").exists()
        assert "gpd-user-keep" not in tracked_skill_names
        assert not any((skills_dir / name).exists() for name in tracked_skill_names)

    def test_reinstall_after_uninstall(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)
        adapter.uninstall(target, skills_dir=skills_dir)
        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(gpd_skills) > 0
        assert (target / "get-physics-done" / "VERSION").exists()
        assert (target / MANIFEST_NAME).exists()

    def test_manifest_includes_skills(self, tmp_path: Path, gpd_root: Path) -> None:
        """Codex manifest should include discoverable skill SKILL.md hashes."""
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        skill_entries = [k for k in manifest["files"] if k.startswith("skills/")]
        assert len(skill_entries) > 0, "Manifest missing skill entries"

    def test_slides_skill_installed(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        slides_skill = skills_dir / "gpd-slides" / "SKILL.md"
        assert slides_skill.exists()
        content = slides_skill.read_text(encoding="utf-8")
        assert "context_mode: projectless" in content
        assert "<!-- [included: slides.md] -->" in content

    def test_inline_gpd_commands_are_rewritten_to_the_bridge(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        bridge_command = _expected_bridge_for_install(adapter, target, is_global=True)
        content = (skills_dir / "gpd-suggest-next" / "SKILL.md").read_text(encoding="utf-8")
        assert bridge_command in content
        assert "Uses `gpd --raw suggest`" not in content
        assert "`gpd --raw suggest`" not in content


# ---------------------------------------------------------------------------
# OpenCode lifecycle
# ---------------------------------------------------------------------------


class TestOpenCodeLifecycle:
    """Full install → uninstall → reinstall for OpenCode adapter."""

    runtime_name = "opencode"

    def test_install_creates_expected_structure(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        result = _install_and_finalize(adapter, gpd_root, target)

        # Flat command structure (command/gpd-*.md)
        command_dir = target / "command"
        assert command_dir.is_dir()
        gpd_commands = [f for f in command_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(gpd_commands) > 0, "No GPD command files installed"

        # Agents installed
        agents_dir = target / "agents"
        assert agents_dir.is_dir()

        # get-physics-done content
        assert (target / "get-physics-done").is_dir()
        assert (target / "get-physics-done" / "VERSION").exists()

        # opencode.json permissions
        assert (target / "opencode.json").exists()
        oc_config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
        assert "permission" in oc_config

        # Manifest
        assert (target / MANIFEST_NAME).exists()

        assert result["runtime"] == "opencode"

    def test_slides_command_installed(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        slides_md = target / "command" / "gpd-slides.md"
        assert slides_md.exists()
        content = slides_md.read_text(encoding="utf-8")
        assert "PRESENTATION-BRIEF.md" in content

    def test_opencode_commands_are_flat(self, tmp_path: Path, gpd_root: Path) -> None:
        """OpenCode uses flat command structure: command/gpd-help.md not commands/gpd/help.md."""
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        # Should NOT have nested commands/gpd/ structure
        assert not (target / "commands" / "gpd").exists()
        # Should have flat command/ structure
        command_dir = target / "command"
        assert command_dir.is_dir()
        gpd_commands = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")]
        assert len(gpd_commands) > 0

    def test_opencode_frontmatter_converted(self, tmp_path: Path, gpd_root: Path) -> None:
        """OpenCode commands should have frontmatter converted (no allowed-tools:, no name:)."""
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        command_dir = target / "command"
        for cmd_file in command_dir.iterdir():
            if cmd_file.name.startswith("gpd-") and cmd_file.suffix == ".md":
                content = cmd_file.read_text(encoding="utf-8")
                # allowed-tools should be converted to tools
                assert "allowed-tools:" not in content, f"{cmd_file.name} still has 'allowed-tools:'"

    def test_inline_gpd_commands_are_rewritten_to_the_bridge(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        bridge_command = adapter.runtime_cli_bridge_command(target)
        content = (target / "command" / "gpd-suggest-next.md").read_text(encoding="utf-8")
        assert bridge_command in content
        assert "Uses `gpd --raw suggest`" not in content
        assert "`gpd --raw suggest`" not in content

    def test_uninstall_removes_gpd_artifacts(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        # Patch global_config_dir to avoid touching real XDG dirs

        _install_and_finalize(adapter, gpd_root, target)

        # For uninstall, we need to make the opencode.json accessible within the target
        from gpd.adapters.opencode import uninstall_opencode

        uninstall_opencode(target, config_dir=target)

        # Flat commands removed
        command_dir = target / "command"
        gpd_commands = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")] if command_dir.exists() else []
        assert len(gpd_commands) == 0

        # get-physics-done removed
        assert not (target / "get-physics-done").exists()

        # Manifest removed
        assert not (target / MANIFEST_NAME).exists()

        # Permissions cleaned from opencode.json
        if (target / "opencode.json").exists():
            oc_config = json.loads((target / "opencode.json").read_text(encoding="utf-8"))
            perm = oc_config.get("permission", {})
            for perm_type in ("read", "external_directory"):
                perm_dict = perm.get(perm_type, {})
                gpd_keys = [k for k in perm_dict if "get-physics-done" in k]
                assert len(gpd_keys) == 0, f"GPD permissions not cleaned from {perm_type}"

    def test_reinstall_after_uninstall(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        from gpd.adapters.opencode import uninstall_opencode

        uninstall_opencode(target, config_dir=target)

        result = _install_and_finalize(adapter, gpd_root, target)

        command_dir = target / "command"
        gpd_commands = [f for f in command_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(gpd_commands) > 0
        assert (target / "get-physics-done" / "VERSION").exists()
        assert (target / MANIFEST_NAME).exists()
        assert result["commands"] > 0

    def test_manifest_uses_flat_command_paths(self, tmp_path: Path, gpd_root: Path) -> None:
        """OpenCode manifest should reference command/gpd-*.md (flat) not commands/gpd/ (nested)."""
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        command_entries = [k for k in manifest["files"] if k.startswith("command/")]
        assert len(command_entries) > 0, "Manifest missing command/ entries"
        nested_entries = [k for k in manifest["files"] if k.startswith("commands/")]
        assert len(nested_entries) == 0, "OpenCode manifest should not have nested commands/ entries"


# ---------------------------------------------------------------------------
# Cross-runtime manifest tests
# ---------------------------------------------------------------------------


class TestManifestConsistency:
    """Verify manifest read/write is correct across install cycles."""

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    def test_manifest_version_matches_package(self, runtime: str, tmp_path: Path, gpd_root: Path) -> None:
        from gpd.version import version_for_gpd_root

        adapter = get_adapter(runtime)
        target = tmp_path / adapter.config_dir_name
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, **_install_kwargs_for_runtime(tmp_path, runtime, is_global=True))

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert manifest["version"] == version_for_gpd_root(gpd_root)

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    def test_manifest_has_timestamp(self, runtime: str, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter(runtime)
        target = tmp_path / adapter.config_dir_name
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, **_install_kwargs_for_runtime(tmp_path, runtime, is_global=True))

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert "timestamp" in manifest
        assert len(manifest["timestamp"]) > 10  # ISO 8601 format

    def test_reinstall_overwrites_manifest(self, tmp_path: Path, gpd_root: Path) -> None:
        """Second install should produce a fresh manifest (not append)."""
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)
        manifest1 = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))

        # Reinstall without uninstall
        _install_and_finalize(adapter, gpd_root, target, is_global=True)
        manifest2 = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))

        # Timestamps should differ (or at least manifest is valid)
        assert manifest2["version"] == manifest1["version"]
        assert len(manifest2["files"]) > 0

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    @pytest.mark.parametrize("is_global, expected_scope", [(False, "local"), (True, "global")])
    def test_manifest_records_install_scope(
        self,
        runtime: str,
        is_global: bool,
        expected_scope: str,
        tmp_path: Path,
        gpd_root: Path,
    ) -> None:
        adapter = get_adapter(runtime)
        target = tmp_path / adapter.config_dir_name
        target.mkdir(parents=True, exist_ok=True)

        _install_and_finalize(adapter, gpd_root, target, **_install_kwargs_for_runtime(tmp_path, runtime, is_global=is_global))

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert manifest["runtime"] == runtime
        assert manifest["install_scope"] == expected_scope

    @pytest.mark.parametrize(("runtime", "is_global"), [(runtime, is_global) for runtime in _ALL_RUNTIMES for is_global in (False, True)])
    def test_manifest_records_explicit_target_metadata(
        self,
        runtime: str,
        is_global: bool,
        tmp_path: Path,
        gpd_root: Path,
    ) -> None:
        adapter = get_adapter(runtime)
        target = tmp_path / "custom-targets" / adapter.config_dir_name
        target.mkdir(parents=True, exist_ok=True)

        _install_and_finalize(adapter,
            gpd_root,
            target,
            **_install_kwargs_for_runtime(tmp_path, runtime, is_global=is_global, explicit_target=True),
        )

        manifest = json.loads((target / MANIFEST_NAME).read_text(encoding="utf-8"))
        assert manifest["install_target_dir"] == str(target)
        assert manifest["explicit_target"] is True

    @pytest.mark.parametrize("manifest_runtime", ["Claude Code", "claude"])
    def test_uninstall_accepts_display_name_and_alias_manifest_runtime(
        self,
        manifest_runtime: str,
        tmp_path: Path,
        gpd_root: Path,
    ) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / adapter.config_dir_name
        target.mkdir(parents=True, exist_ok=True)

        _install_and_finalize(
            adapter,
            gpd_root,
            target,
            **_install_kwargs_for_runtime(tmp_path, "claude-code", is_global=False),
        )

        manifest_path = target / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["runtime"] = manifest_runtime
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = adapter.uninstall(target)

        assert result["removed"]
        assert not manifest_path.exists()

    def test_target_dir_matching_global_dir_infers_global_scope(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        runtime = "claude-code"
        adapter = get_adapter(runtime)
        fake_home = tmp_path / "_fake_home"
        fake_home.mkdir()

        with patch("pathlib.Path.home", return_value=fake_home):
            target_dir = adapter.resolve_target_dir(True, tmp_path)
            result = runner.invoke(
                app,
                ["--raw", "install", runtime, "--target-dir", str(target_dir)],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        manifest = json.loads((target_dir / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        assert manifest["install_scope"] == "global"


@pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
def test_clean_local_uninstall_removes_gpd_owned_runtime_artifacts(tmp_path: Path, gpd_root: Path, runtime: str) -> None:
    adapter = get_adapter(runtime)
    target = tmp_path / adapter.config_dir_name
    target.mkdir(parents=True, exist_ok=True)

    install_kwargs = _install_kwargs_for_runtime(tmp_path, runtime, is_global=False)
    _install_and_finalize(adapter, gpd_root, target, **install_kwargs)

    if runtime == "codex":
        adapter.uninstall(target, skills_dir=install_kwargs["skills_dir"])
        skills_dir = Path(str(install_kwargs["skills_dir"]))
        assert not skills_dir.exists()
        assert not skills_dir.parent.exists()
        assert not (target / "config.toml").exists()
    else:
        adapter.uninstall(target)

    assert not (target / "hooks" / "install_metadata.py").exists()
    assert not (target / "cache" / "gpd-update-check.json").exists()
    assert not (target / "cache" / "gpd-update-check.json.inflight").exists()
    assert not (target / "commands").exists()
    assert not (target / "command").exists()
    assert not (target / "agents").exists()
    assert not (target / "hooks").exists()
    assert not (target / "cache").exists()
    assert not (target / "get-physics-done").exists()

    if runtime == "claude-code":
        assert not (target / "settings.json").exists()
        assert not (tmp_path / ".mcp.json").exists()
    elif runtime == "gemini":
        assert not (target / "settings.json").exists()
    elif runtime == "opencode":
        assert not (target / "opencode.json").exists()

    assert not target.exists()


def test_explicit_lifecycle_suites_cover_all_catalog_runtimes() -> None:
    lifecycle_classes = (
        TestClaudeCodeLifecycle,
        TestGeminiLifecycle,
        TestCodexLifecycle,
        TestOpenCodeLifecycle,
    )

    covered = {test_class.runtime_name for test_class in lifecycle_classes}
    assert covered == set(_ALL_RUNTIMES)


# ---------------------------------------------------------------------------
# Path replacement in installed content
# ---------------------------------------------------------------------------


class TestPathReplacementInInstalledContent:
    """Verify that {GPD_INSTALL_DIR} and ~/.claude/ are replaced in installed files."""

    def test_claude_code_path_replacement(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        # Check a few installed files for unreplaced placeholders
        for md_file in (target / "commands" / "gpd").rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content, (
                f"{md_file.relative_to(target)} has unreplaced {{GPD_INSTALL_DIR}}"
            )

    def test_gemini_no_unreplaced_placeholders(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        for toml_file in (target / "commands" / "gpd").rglob("*.toml"):
            content = toml_file.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content, (
                f"{toml_file.relative_to(target)} has unreplaced {{GPD_INSTALL_DIR}}"
            )

    def test_opencode_no_claude_paths(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target)

        command_dir = target / "command"
        if command_dir.exists():
            for md_file in command_dir.iterdir():
                if md_file.suffix == ".md":
                    content = md_file.read_text(encoding="utf-8")
                    assert "{GPD_INSTALL_DIR}" not in content, f"{md_file.name} has unreplaced {{GPD_INSTALL_DIR}}"


def test_reinstall_replaces_manifest_tracked_gpd_hook(tmp_path: Path, gpd_root: Path) -> None:
    adapter = get_adapter("claude-code")
    target = tmp_path / ".claude"
    target.mkdir()

    _install_and_finalize(adapter, gpd_root, target, is_global=True)

    managed_hook = target / "hooks" / "statusline.py"
    original = managed_hook.read_text(encoding="utf-8")
    managed_hook.write_text("# locally modified managed hook\n", encoding="utf-8")

    _install_and_finalize(adapter, gpd_root, target, is_global=True)

    assert managed_hook.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# Idempotency: install twice produces identical results
# ---------------------------------------------------------------------------


class TestInstallIdempotent:
    """Installing twice (without uninstall) should be safe and produce the same result."""

    def test_claude_code_install_twice(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        result1 = _install_and_finalize(adapter, gpd_root, target, is_global=True)
        result2 = _install_and_finalize(adapter, gpd_root, target, is_global=True)

        assert result1["commands"] == result2["commands"]
        assert result1["agents"] == result2["agents"]
        assert (target / "commands" / "gpd").is_dir()
        assert (target / "get-physics-done" / "VERSION").exists()
        assert (target / MANIFEST_NAME).exists()

    def test_gemini_install_twice(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        result1 = _install_and_finalize(adapter, gpd_root, target, is_global=True)
        result2 = _install_and_finalize(adapter, gpd_root, target, is_global=True)

        assert result1["commands"] == result2["commands"]
        assert result1["agents"] == result2["agents"]
        assert (target / "commands" / "gpd").is_dir()

    def test_codex_install_twice(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        result1 = _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)
        result2 = _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)

        assert result1["commands"] == result2["commands"]
        assert result1["agents"] == result2["agents"]
        gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(gpd_skills) > 0

    def test_opencode_install_twice(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("opencode")
        target = tmp_path / ".opencode"
        target.mkdir()

        result1 = _install_and_finalize(adapter, gpd_root, target)
        result2 = _install_and_finalize(adapter, gpd_root, target)

        assert result1["commands"] == result2["commands"]
        assert result1["agents"] == result2["agents"]
        command_dir = target / "command"
        gpd_commands = [f for f in command_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(gpd_commands) > 0


class TestUpgradePrunesRemovedFiles:
    """Reinstall should remove files that were managed by an older version but are no longer shipped."""

    @pytest.mark.parametrize("runtime", _ALL_RUNTIMES)
    def test_reinstall_removes_manifest_tracked_stale_file(self, runtime: str, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter(runtime)
        target = tmp_path / adapter.config_dir_name
        target.mkdir(parents=True, exist_ok=True)
        install_kwargs = _install_kwargs_for_runtime(tmp_path, runtime, is_global=True)

        _install_and_finalize(adapter, gpd_root, target, **install_kwargs)

        stale_file = target / "get-physics-done" / "STALE-ROOT.md"
        stale_file.write_text("stale\n", encoding="utf-8")

        manifest_path = target / MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["get-physics-done/STALE-ROOT.md"] = file_hash(stale_file)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        _install_and_finalize(adapter, gpd_root, target, **install_kwargs)

        assert not stale_file.exists()


# ---------------------------------------------------------------------------
# Uninstall when not installed: should be safe (no crash)
# ---------------------------------------------------------------------------


class TestUninstallWhenNotInstalled:
    """Uninstalling from a directory with no GPD artifacts should not crash."""

    def test_claude_code_uninstall_empty(self, tmp_path: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        result = adapter.uninstall(target)
        assert result["removed"] == []

    def test_gemini_uninstall_empty(self, tmp_path: Path) -> None:
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        result = adapter.uninstall(target)
        assert result["removed"] == []

    def test_codex_uninstall_empty(self, tmp_path: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        result = adapter.uninstall(target, skills_dir=skills_dir)
        assert result["removed"] == []

    def test_opencode_uninstall_empty(self, tmp_path: Path) -> None:
        from gpd.adapters.opencode import uninstall_opencode

        target = tmp_path / ".opencode"
        target.mkdir()

        result = uninstall_opencode(target, config_dir=target)
        assert result["commands"] == 0
        assert result["agents"] == 0
        assert result["hooks"] == 0
        assert result["dirs"] == 0

    def test_uninstall_nonexistent_subdirs(self, tmp_path: Path) -> None:
        """Uninstall when target exists but has no commands/, agents/, etc."""
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()
        # Just put a random file in target
        (target / "other.txt").write_text("not gpd", encoding="utf-8")

        result = adapter.uninstall(target)
        assert result["removed"] == []
        assert (target / "other.txt").exists()  # Non-GPD content preserved


# ---------------------------------------------------------------------------
# Install then immediately uninstall: clean state
# ---------------------------------------------------------------------------


class TestInstallThenUninstallClean:
    """Install then immediate uninstall should leave a clean directory."""

    def test_claude_code_clean_after_cycle(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("claude-code")
        target = tmp_path / ".claude"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)
        adapter.uninstall(target)

        # GPD artifacts gone
        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()
        assert not (target / MANIFEST_NAME).exists()
        assert not (target / "gpd-local-patches").exists()
        # Agents dir may exist but no gpd-* files
        agents = target / "agents"
        if agents.exists():
            gpd_agents = [f for f in agents.iterdir() if f.name.startswith("gpd-")]
            assert len(gpd_agents) == 0

    def test_codex_clean_after_cycle(self, tmp_path: Path, gpd_root: Path) -> None:
        adapter = get_adapter("codex")
        target = tmp_path / ".codex"
        target.mkdir()
        skills_dir = tmp_path / ".agents" / "skills"
        skills_dir.mkdir(parents=True)

        _install_and_finalize(adapter, gpd_root, target, is_global=True, skills_dir=skills_dir)
        adapter.uninstall(target, skills_dir=skills_dir)

        assert not (target / "get-physics-done").exists()
        assert not (target / MANIFEST_NAME).exists()
        gpd_skills = [d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")] if skills_dir.exists() else []
        assert len(gpd_skills) == 0


# ---------------------------------------------------------------------------
# Uninstall with corrupted config files
# ---------------------------------------------------------------------------


class TestUninstallCorruptedConfigs:
    """Uninstall should not crash when config files are corrupted."""

    def test_opencode_corrupted_settings_json(self, tmp_path: Path, gpd_root: Path) -> None:
        """Corrupted settings.json should not prevent OpenCode uninstall."""
        from gpd.adapters.opencode import uninstall_opencode

        target = tmp_path / ".opencode"
        target.mkdir()

        adapter = get_adapter("opencode")
        _install_and_finalize(adapter, gpd_root, target)

        # Corrupt settings.json
        (target / "settings.json").write_text("{{{not valid json!!!", encoding="utf-8")

        # Uninstall should still succeed
        uninstall_opencode(target, config_dir=target)
        assert not (target / "get-physics-done").exists()
        # Commands should be cleaned
        command_dir = target / "command"
        gpd_cmds = [f for f in command_dir.iterdir() if f.name.startswith("gpd-")] if command_dir.exists() else []
        assert len(gpd_cmds) == 0

    def test_opencode_corrupted_opencode_json(self, tmp_path: Path, gpd_root: Path) -> None:
        """Corrupted opencode.json should not prevent OpenCode uninstall."""
        from gpd.adapters.opencode import uninstall_opencode

        target = tmp_path / ".opencode"
        target.mkdir()

        adapter = get_adapter("opencode")
        _install_and_finalize(adapter, gpd_root, target)

        # Corrupt opencode.json
        (target / "opencode.json").write_text("NOT JSON AT ALL", encoding="utf-8")

        # Uninstall should still succeed
        uninstall_opencode(target, config_dir=target)
        assert not (target / "get-physics-done").exists()

    def test_gemini_corrupted_settings_json(self, tmp_path: Path, gpd_root: Path) -> None:
        """Corrupted settings.json should not prevent Gemini uninstall."""
        adapter = get_adapter("gemini")
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_and_finalize(adapter, gpd_root, target, is_global=True)

        # Corrupt settings.json (Gemini uses read_settings which handles this)
        (target / "settings.json").write_text("{{{broken", encoding="utf-8")

        # Should not crash
        adapter.uninstall(target)
        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()
