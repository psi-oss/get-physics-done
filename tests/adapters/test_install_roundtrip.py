"""Integration tests: install → read back → verify for all 4 runtimes.

Tests that installed content matches source expectations for each adapter.
Exercises both the write path (install) and the read path (loading/parsing
installed content) to catch serialization/deserialization mismatches.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from gpd.adapters import iter_adapters
from gpd.adapters.claude_code import ClaudeCodeAdapter
from gpd.adapters.codex import CodexAdapter
from gpd.adapters.gemini import GeminiAdapter
from gpd.adapters.install_utils import (
    build_runtime_cli_bridge_command,
    convert_tool_references_in_body,
    expand_at_includes,
    translate_frontmatter_tool_names,
)
from gpd.adapters.opencode import OpenCodeAdapter
from gpd.adapters.runtime_catalog import resolve_global_config_dir
from gpd.adapters.tool_names import build_canonical_alias_map
from gpd.registry import get_command, load_agents_from_dir

REPO_GPD_ROOT = Path(__file__).resolve().parents[2] / "src" / "gpd"
RUNTIME_ALIAS_MAP = build_canonical_alias_map(adapter.tool_name_map for adapter in iter_adapters())


def _review_contract_section(content: str) -> str:
    match = re.search(r"## Review Contract\n\n.*?\n```\n", content, flags=re.DOTALL)
    assert match is not None
    return match.group(0)


def expected_opencode_bridge(target: Path, *, is_global: bool = False, explicit_target: bool = False) -> str:
    return build_runtime_cli_bridge_command(
        "opencode",
        target_dir=target,
        config_dir_name=".opencode",
        is_global=is_global,
        explicit_target=explicit_target,
    )


def _install_real_repo_for_runtime(tmp_path: Path, runtime: str) -> Path:
    if runtime == "claude-code":
        target = tmp_path / ".claude"
        target.mkdir()
        ClaudeCodeAdapter().install(REPO_GPD_ROOT, target)
        return target

    if runtime == "codex":
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        CodexAdapter().install(REPO_GPD_ROOT, target, skills_dir=skills)
        return target

    if runtime == "gemini":
        target = tmp_path / ".gemini"
        target.mkdir()
        _install_gemini_for_tests(REPO_GPD_ROOT, target)
        return target

    if runtime == "opencode":
        target = tmp_path / ".opencode"
        target.mkdir()
        OpenCodeAdapter().install(REPO_GPD_ROOT, target)
        return target

    raise AssertionError(f"Unsupported runtime {runtime}")


def _install_gemini_for_tests(gpd_root: Path, target: Path) -> GeminiAdapter:
    """Install Gemini artifacts and persist the deferred Gemini settings."""
    adapter = GeminiAdapter()
    result = adapter.install(gpd_root, target)
    adapter.finalize_install(result)
    return adapter


def _canonicalize_runtime_markdown(content: str, *, runtime: str) -> str:
    content = re.sub(
        r"@(?:\./)?[^\s`>)]*get-physics-done/([^\s`>)]+)",
        r"@{GPD_INSTALL_DIR}/\1",
        content,
    )
    content = re.sub(
        r"@(?:\./)?[^\s`>)]*agents/([^\s`>)]+)",
        r"@{GPD_AGENTS_DIR}/\1",
        content,
    )
    content = re.sub(
        (
            r"(?:'[^']+'|\"[^\"]+\"|[^ \n`]+)\s+-m gpd\.runtime_cli\s+--runtime\s+[a-z-]+\s+"
            r"--config-dir\s+(?:'[^']+'|\"[^\"]+\"|[^ \n`]+)\s+--install-scope\s+(?:local|global)"
            r"(?:\s+--explicit-target)?"
        ),
        "gpd",
        content,
    )
    content = expand_at_includes(
        content,
        REPO_GPD_ROOT / "specs",
        "/normalized/",
        runtime=runtime,
    )
    content = translate_frontmatter_tool_names(content, lambda name: RUNTIME_ALIAS_MAP.get(name, name))
    content = convert_tool_references_in_body(content, RUNTIME_ALIAS_MAP)
    content = content.replace("$gpd-", "/gpd:")
    content = content.replace("/gpd-", "/gpd:")
    return content


def _read_compare_experiment_command(tmp_path: Path, target: Path, runtime: str) -> str:
    if runtime == "claude-code":
        return (target / "commands" / "gpd" / "compare-experiment.md").read_text(encoding="utf-8")

    if runtime == "codex":
        return (tmp_path / "skills" / "gpd-compare-experiment" / "SKILL.md").read_text(encoding="utf-8")

    if runtime == "gemini":
        parsed = tomllib.loads((target / "commands" / "gpd" / "compare-experiment.toml").read_text(encoding="utf-8"))
        prompt = parsed.get("prompt")
        assert isinstance(prompt, str)
        return prompt

    if runtime == "opencode":
        return (target / "command" / "gpd-compare-experiment.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_command_prompt(tmp_path: Path, target: Path, runtime: str, command_name: str) -> str:
    if runtime == "claude-code":
        return (target / "commands" / "gpd" / f"{command_name}.md").read_text(encoding="utf-8")

    if runtime == "codex":
        return (tmp_path / "skills" / f"gpd-{command_name}" / "SKILL.md").read_text(encoding="utf-8")

    if runtime == "gemini":
        parsed = tomllib.loads((target / "commands" / "gpd" / f"{command_name}.toml").read_text(encoding="utf-8"))
        prompt = parsed.get("prompt")
        assert isinstance(prompt, str)
        return prompt

    if runtime == "opencode":
        return (target / "command" / f"gpd-{command_name}.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_update_surface(tmp_path: Path, target: Path, runtime: str) -> str:
    if runtime == "claude-code":
        return (target / "commands" / "gpd" / "update.md").read_text(encoding="utf-8")

    if runtime == "codex":
        return (tmp_path / "skills" / "gpd-update" / "SKILL.md").read_text(encoding="utf-8")

    if runtime == "gemini":
        parsed = tomllib.loads((target / "commands" / "gpd" / "update.toml").read_text(encoding="utf-8"))
        prompt = parsed.get("prompt")
        assert isinstance(prompt, str)
        return prompt

    if runtime == "opencode":
        return (target / "command" / "gpd-update.md").read_text(encoding="utf-8")

    raise AssertionError(f"Unsupported runtime {runtime}")


def _read_runtime_agent_prompt(target: Path, runtime: str, agent_name: str) -> str:
    if runtime in {"claude-code", "codex", "gemini", "opencode"}:
        return (target / "agents" / f"{agent_name}.md").read_text(encoding="utf-8")
    raise AssertionError(f"Unsupported runtime {runtime}")


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
def test_update_surface_materializes_workflow_paths_in_compiled_artifacts(
    tmp_path: Path,
    runtime: str,
) -> None:
    target = _install_real_repo_for_runtime(tmp_path, runtime)
    adapter = next(adapter for adapter in iter_adapters() if adapter.runtime_name == runtime)
    canonical_global_dir = resolve_global_config_dir(adapter.runtime_descriptor)
    content = _read_runtime_update_surface(tmp_path, target, runtime)

    if runtime == "claude-code":
        assert f"@{target.as_posix()}/get-physics-done/workflows/update.md" in content
        assert "{GPD_CONFIG_DIR}" not in content
    else:
        assert f'GPD_CONFIG_DIR="{target.as_posix()}"' in content
        assert f'GPD_GLOBAL_CONFIG_DIR="{canonical_global_dir.as_posix()}"' in content
        assert "TARGET_DIR_ARG=$(" in content

# ---------------------------------------------------------------------------
# Claude Code: install → read back → compare
# ---------------------------------------------------------------------------


class TestClaudeCodeRoundtrip:
    """Install into .claude/, then verify installed files match source semantics."""

    @pytest.fixture()
    def installed(self, gpd_root: Path, tmp_path: Path) -> Path:
        target = tmp_path / ".claude"
        target.mkdir()
        ClaudeCodeAdapter().install(gpd_root, target)
        return target

    def test_commands_roundtrip(self, installed: Path, gpd_root: Path) -> None:
        """Installed commands/gpd/ files correspond 1:1 with source commands/."""
        src_mds = sorted(f.name for f in (gpd_root / "commands").rglob("*.md"))
        dest_mds = sorted(f.name for f in (installed / "commands" / "gpd").rglob("*.md"))
        assert dest_mds == src_mds

    def test_command_placeholders_resolved(self, installed: Path) -> None:
        """All {GPD_INSTALL_DIR} and ~/.claude/ placeholders are replaced."""
        for md in (installed / "commands" / "gpd").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content

    def test_agents_roundtrip(self, installed: Path, gpd_root: Path) -> None:
        """Installed agents match source agent filenames."""
        src_agents = sorted(f.name for f in (gpd_root / "agents").glob("*.md"))
        dest_agents = sorted(f.name for f in (installed / "agents").glob("gpd-*.md"))
        assert dest_agents == src_agents

    def test_agent_frontmatter_preserved(self, installed: Path) -> None:
        """Claude Code agents keep frontmatter intact (tools, description)."""
        for md in (installed / "agents").glob("gpd-*.md"):
            content = md.read_text(encoding="utf-8")
            assert content.startswith("---"), f"{md.name} missing frontmatter"
            # Frontmatter should have description and either tools: or allowed-tools:
            end = content.find("---", 3)
            frontmatter = content[3:end]
            assert "description:" in frontmatter, f"{md.name} missing description"

    def test_gpd_content_subdirs(self, installed: Path) -> None:
        """get-physics-done/ has all expected subdirectories with files."""
        gpd = installed / "get-physics-done"
        for subdir in ("references", "templates", "workflows"):
            d = gpd / subdir
            assert d.is_dir(), f"Missing {subdir}/"
            files = list(d.rglob("*"))
            assert len(files) > 0, f"{subdir}/ is empty"

    def test_gpd_content_placeholders_resolved(self, installed: Path) -> None:
        """get-physics-done/ .md files have placeholders replaced."""
        for md in (installed / "get-physics-done").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}" not in content

    def test_shared_content_tool_references_are_translated(self, installed: Path) -> None:
        """Shared markdown content should use Claude-native tool names."""
        workflow = (installed / "get-physics-done" / "workflows" / "wor.md").read_text(encoding="utf-8")
        reference = (installed / "get-physics-done" / "references" / "ref.md").read_text(encoding="utf-8")

        assert "AskUserQuestion([" in workflow
        assert "ask_user(" not in workflow
        assert "Task(" in workflow
        assert "task(" not in workflow
        assert "WebSearch" in reference
        assert "web_search" not in reference

    def test_hooks_copied(self, installed: Path, gpd_root: Path) -> None:
        """Hook scripts are copied faithfully."""
        for hook in (gpd_root / "hooks").iterdir():
            if hook.is_file() and not hook.name.startswith("__"):
                dest = installed / "hooks" / hook.name
                assert dest.exists(), f"Missing hook: {hook.name}"
                assert dest.read_bytes() == hook.read_bytes()

    def test_version_file(self, installed: Path) -> None:
        """VERSION file exists and is non-empty."""
        version = installed / "get-physics-done" / "VERSION"
        assert version.exists()
        assert len(version.read_text(encoding="utf-8").strip()) > 0

    def test_manifest_tracks_all_files(self, installed: Path) -> None:
        """File manifest lists entries for commands, agents, and content."""
        manifest = json.loads((installed / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        files = manifest["files"]
        assert any(k.startswith("commands/gpd/") for k in files)
        assert any(k.startswith("agents/") for k in files)
        assert any(k.startswith("get-physics-done/") for k in files)
        assert "version" in manifest


# ---------------------------------------------------------------------------
# Gemini: install → read back → compare
# ---------------------------------------------------------------------------


class TestGeminiRoundtrip:
    """Install into .gemini/, verify TOML commands and converted agents."""

    @pytest.fixture()
    def installed(self, gpd_root: Path, tmp_path: Path) -> Path:
        target = tmp_path / ".gemini"
        target.mkdir()
        _install_gemini_for_tests(gpd_root, target)
        return target

    def test_commands_are_toml(self, installed: Path) -> None:
        """Gemini commands are .toml files (not .md)."""
        toml_files = list((installed / "commands" / "gpd").rglob("*.toml"))
        assert len(toml_files) > 0
        md_files = list((installed / "commands" / "gpd").rglob("*.md"))
        assert len(md_files) == 0, "Should not have .md files in Gemini commands"

    def test_toml_has_prompt_field(self, installed: Path) -> None:
        """Each TOML command has a prompt field."""
        for toml_file in (installed / "commands" / "gpd").rglob("*.toml"):
            content = toml_file.read_text(encoding="utf-8")
            assert "prompt" in content, f"{toml_file.name} missing prompt field"

    def test_toml_preserves_non_runtime_metadata_as_comments(self, gpd_root: Path, tmp_path: Path) -> None:
        """Gemini TOML commands keep canonical non-runtime metadata as comments."""
        (gpd_root / "commands" / "progress.md").write_text(
            "---\n"
            "name: gpd:progress\n"
            'description: Check research progress\n'
            'argument-hint: "[--brief] [--full] [--reconcile]"\n'
            "context_mode: project-required\n"
            "project_reentry_capable: true\n"
            "requires:\n"
            '  files: ["GPD/ROADMAP.md"]\n'
            "allowed-tools:\n"
            "  - file_read\n"
            "  - shell\n"
            "---\n"
            "Progress body.\n",
            encoding="utf-8",
        )
        target = tmp_path / ".gemini"
        target.mkdir()
        _install_gemini_for_tests(gpd_root, target)

        content = (target / "commands" / "gpd" / "progress.toml").read_text(encoding="utf-8")
        parsed = tomllib.loads(content)

        assert "# Source frontmatter preserved for parity:" in content
        assert '# name: gpd:progress' in content
        assert '# argument-hint: "[--brief] [--full] [--reconcile]"' in content
        assert "# project_reentry_capable: true" in content
        assert "# requires:" in content
        assert '#   files: ["GPD/ROADMAP.md"]' in content
        assert "# allowed-tools:" not in content
        assert parsed["context_mode"] == "project-required"

    def test_toml_command_count_matches_source(self, installed: Path, gpd_root: Path) -> None:
        """Number of TOML commands matches source .md count."""
        src_count = sum(1 for _ in (gpd_root / "commands").rglob("*.md"))
        dest_count = sum(1 for _ in (installed / "commands" / "gpd").rglob("*.toml"))
        assert dest_count == src_count

    def test_agents_use_tools_array(self, installed: Path) -> None:
        """Gemini agents convert allowed-tools to tools: YAML array."""
        for md in (installed / "agents").glob("gpd-*.md"):
            content = md.read_text(encoding="utf-8")
            # Should not have allowed-tools (Claude format)
            assert "allowed-tools:" not in content, f"{md.name} still has allowed-tools"
            # Should not have color field (causes Gemini validation error)
            end = content.find("---", 3)
            if end > 0:
                fm = content[3:end]
                assert "color:" not in fm, f"{md.name} still has color field"

    def test_agents_tool_names_converted(self, installed: Path) -> None:
        """Gemini agents use Gemini tool names (read_file, not Read)."""
        verifier = installed / "agents" / "gpd-verifier.md"
        if not verifier.exists():
            pytest.skip("gpd-verifier.md not found in installed agents")
        agent_content = verifier.read_text(encoding="utf-8")
        if "tools:" not in agent_content:
            pytest.skip("gpd-verifier.md has no tools: field")
        end = agent_content.find("---", 3)
        assert end > 0, "gpd-verifier.md has malformed frontmatter"
        fm = agent_content[3:end]
        tools_idx = fm.find("tools:")
        assert tools_idx >= 0, "tools: not found in frontmatter"
        tools_section = fm[tools_idx:]
        assert "read_file" in tools_section or "Read" not in tools_section

    def test_gpd_content_installed(self, installed: Path) -> None:
        """get-physics-done/ content is present."""
        gpd = installed / "get-physics-done"
        assert gpd.is_dir()
        for subdir in ("references", "templates", "workflows"):
            assert (gpd / subdir).is_dir()

    def test_shared_content_tool_references_are_translated(self, installed: Path) -> None:
        """Shared markdown content should use Gemini runtime tool names."""
        workflow = (installed / "get-physics-done" / "workflows" / "wor.md").read_text(encoding="utf-8")
        reference = (installed / "get-physics-done" / "references" / "ref.md").read_text(encoding="utf-8")

        assert "ask_user([" in workflow
        assert "AskUserQuestion" not in workflow
        assert "task(" in workflow
        assert "Task(" not in workflow
        assert "google_web_search" in reference
        assert "WebSearch" not in reference

    def test_runtime_cli_bridge_is_pinned_in_shell_heavy_surfaces(self, tmp_path: Path) -> None:
        """Gemini install rewrites the shell-heavy surfaces to the runtime bridge."""
        installed = _install_real_repo_for_runtime(tmp_path, "gemini")
        bridge_marker = "-m gpd.runtime_cli --runtime gemini"
        command = _read_runtime_command_prompt(tmp_path, installed, "gemini", "set-profile")
        workflow = (installed / "get-physics-done" / "workflows" / "set-profile.md").read_text(encoding="utf-8")
        execute_phase = (installed / "get-physics-done" / "workflows" / "execute-phase.md").read_text(encoding="utf-8")
        agent = (installed / "agents" / "gpd-planner.md").read_text(encoding="utf-8")

        assert bridge_marker in command
        assert bridge_marker in workflow
        assert bridge_marker in execute_phase
        assert bridge_marker in agent
        assert "config ensure-section" in command
        assert "config ensure-section" in workflow
        assert "init progress --include state,config" in command
        assert 'if !' in execute_phase and "verify plan \"$plan\"" in execute_phase
        assert 'INIT=$(' in agent and "init plan-phase \"<PHASE>\"" in agent
        assert "gpd config ensure-section" not in command
        assert 'INIT=$(gpd init progress --include state,config)' not in command
        assert 'if ! gpd verify plan "$plan"; then' not in execute_phase
        assert 'INIT=$(gpd init plan-phase "<PHASE>")' not in agent

    def test_settings_json_has_experimental(self, installed: Path) -> None:
        """settings.json enables experimental.enableAgents."""
        settings_path = installed / "settings.json"
        assert settings_path.exists(), "settings.json not written to disk"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        experimental = settings.get("experimental", {})
        assert experimental.get("enableAgents") is True

    def test_manifest_present(self, installed: Path) -> None:
        """File manifest exists and has version."""
        manifest_path = installed / "gpd-file-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "version" in manifest
        assert "files" in manifest


# ---------------------------------------------------------------------------
# Codex: install → read back → compare
# ---------------------------------------------------------------------------


class TestCodexRoundtrip:
    """Install into .codex/ + skills/, verify command skills plus agent roles."""

    @pytest.fixture()
    def installed(self, gpd_root: Path, tmp_path: Path) -> tuple[Path, Path]:
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        CodexAdapter().install(gpd_root, target, skills_dir=skills)
        return target, skills

    def test_commands_become_skill_dirs(self, installed: tuple[Path, Path]) -> None:
        """Each command becomes a gpd-<name>/SKILL.md directory."""
        _, skills = installed
        skill_dirs = [d for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-")]
        assert len(skill_dirs) > 0
        for skill_dir in skill_dirs:
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.exists(), f"{skill_dir.name}/ missing SKILL.md"

    def test_skill_md_has_frontmatter(self, installed: tuple[Path, Path]) -> None:
        """SKILL.md files have YAML frontmatter with name and description."""
        _, skills = installed
        for skill_dir in skills.iterdir():
            if not skill_dir.is_dir() or not skill_dir.name.startswith("gpd-"):
                continue
            skill_md = skill_dir / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            assert content.startswith("---"), f"{skill_dir.name}/SKILL.md missing frontmatter"
            end = content.find("---", 3)
            fm = content[3:end]
            assert "name:" in fm, f"{skill_dir.name} missing name field"
            assert "description:" in fm, f"{skill_dir.name} missing description field"

    def test_skill_names_are_hyphen_case(self, installed: tuple[Path, Path]) -> None:
        """Codex skill names must be hyphen-case (a-z0-9-)."""
        _, skills = installed
        import re

        for skill_dir in skills.iterdir():
            if skill_dir.is_dir() and skill_dir.name.startswith("gpd-"):
                assert re.match(r"^[a-z0-9-]+$", skill_dir.name), f"Skill name not hyphen-case: {skill_dir.name}"

    def test_command_count_matches_source(self, installed: tuple[Path, Path], gpd_root: Path) -> None:
        """Number of skills matches source command count."""
        _, skills = installed
        src_count = sum(1 for _ in (gpd_root / "commands").rglob("*.md"))
        skill_count = sum(1 for d in skills.iterdir() if d.is_dir() and d.name.startswith("gpd-"))
        assert skill_count == src_count

    def test_agents_not_installed_as_skills(self, installed: tuple[Path, Path], gpd_root: Path) -> None:
        """Codex agents are registered as roles, not duplicated as discoverable skills."""
        _, skills = installed
        agents = load_agents_from_dir(gpd_root / "agents")
        for agent_name in sorted(agents):
            assert not (skills / agent_name).exists(), f"Agent should not be a Codex skill: {agent_name}"

    def test_agents_installed_as_md_files(self, installed: tuple[Path, Path], gpd_root: Path) -> None:
        """Agents are also installed as .md files under .codex/agents/."""
        target, _ = installed
        agents_dir = target / "agents"
        assert agents_dir.is_dir()
        src_agents = sorted(f.name for f in (gpd_root / "agents").glob("*.md"))
        dest_agents = sorted(f.name for f in agents_dir.glob("*.md"))
        assert dest_agents == src_agents

    def test_agent_role_configs_installed(self, installed: tuple[Path, Path], gpd_root: Path) -> None:
        """Each installed Codex agent also gets a role config TOML."""
        target, _ = installed
        agents_dir = target / "agents"
        src_agent_names = sorted(f.stem for f in (gpd_root / "agents").glob("*.md"))
        dest_role_names = sorted(f.stem for f in agents_dir.glob("gpd-*.toml"))
        assert dest_role_names == src_agent_names

    def test_gpd_content_installed(self, installed: tuple[Path, Path]) -> None:
        """get-physics-done/ has expected content."""
        target, _ = installed
        gpd = target / "get-physics-done"
        assert gpd.is_dir()
        for subdir in ("references", "templates", "workflows"):
            assert (gpd / subdir).is_dir()

    def test_shared_content_tool_references_are_translated(self, installed: tuple[Path, Path]) -> None:
        """Shared markdown content should use Codex runtime tool names."""
        target, _ = installed
        workflow = (target / "get-physics-done" / "workflows" / "wor.md").read_text(encoding="utf-8")
        reference = (target / "get-physics-done" / "references" / "ref.md").read_text(encoding="utf-8")

        assert "<codex_questioning>" in workflow
        assert "ask_user([" in workflow
        assert "AskUserQuestion" not in workflow
        assert "task(" in workflow
        assert "Task(" not in workflow
        assert "web_search" in reference
        assert "WebSearch" not in reference

    def test_runtime_cli_bridge_is_pinned_in_shell_heavy_surfaces(self, tmp_path: Path) -> None:
        """Codex install rewrites the shell-heavy surfaces to the runtime bridge."""
        target = _install_real_repo_for_runtime(tmp_path, "codex")
        bridge_marker = "-m gpd.runtime_cli --runtime codex"
        command = _read_runtime_command_prompt(tmp_path, target, "codex", "set-profile")
        workflow = (target / "get-physics-done" / "workflows" / "set-profile.md").read_text(encoding="utf-8")
        execute_phase = (target / "get-physics-done" / "workflows" / "execute-phase.md").read_text(encoding="utf-8")
        agent = (target / "agents" / "gpd-planner.md").read_text(encoding="utf-8")

        assert bridge_marker in command
        assert bridge_marker in workflow
        assert bridge_marker in execute_phase
        assert bridge_marker in agent
        assert "config ensure-section" in command
        assert "config ensure-section" in workflow
        assert "verify plan \"$plan\"" in execute_phase
        assert 'INIT=$(' in agent and "init plan-phase \"${PHASE}\"" in agent
        assert "```bash\ngpd config ensure-section\n" not in workflow
        assert 'if ! gpd verify plan "$plan"; then' not in execute_phase
        assert 'INIT=$(gpd init plan-phase "${PHASE}")' not in agent

    def test_help_like_skills_keep_canonical_local_cli_language(self, tmp_path: Path) -> None:
        """Codex skills keep canonical local CLI names in prose even when shell steps bridge."""
        _install_real_repo_for_runtime(tmp_path, "codex")
        skills = tmp_path / "skills"
        help_skill = (skills / "gpd-help" / "SKILL.md").read_text(encoding="utf-8")
        tour_skill = (skills / "gpd-tour" / "SKILL.md").read_text(encoding="utf-8")
        settings_skill = (skills / "gpd-settings" / "SKILL.md").read_text(encoding="utf-8")

        assert "Use `gpd --help` to inspect the executable local install/readiness/permissions/diagnostics surface directly." in help_skill
        assert "For a normal-terminal, current-workspace read-only recovery snapshot without launching the runtime, use `gpd resume`." in help_skill
        assert "For a normal-terminal, read-only machine-local usage / cost summary, use `gpd cost`." in help_skill
        assert "The normal terminal is where you install GPD, run `gpd --help`, and run" in tour_skill
        assert "`gpd resume` is the normal-terminal recovery step for reopening the right" in tour_skill
        assert "use `gpd --help` when you need the broader local CLI entrypoint" in settings_skill
        assert "use `gpd cost` after runs for advisory local usage / cost, optional USD budget guardrails, and the current profile tier mix" in settings_skill
        assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", help_skill) is None
        assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", tour_skill) is None
        assert re.search(r"`[^`\n]*gpd\.runtime_cli[^`\n]*(?:--help|resume|cost)[^`\n]*`", settings_skill) is None

    def test_slash_commands_converted(self, installed: tuple[Path, Path]) -> None:
        """Content replaces /gpd: with $gpd- for Codex invocation syntax."""
        target, _ = installed
        for md in (target / "get-physics-done").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "/gpd:" not in content, f"{md.name} still has /gpd:"

    def test_config_toml_has_notify(self, installed: tuple[Path, Path]) -> None:
        """config.toml has a notify hook entry."""
        target, _ = installed
        toml_path = target / "config.toml"
        assert toml_path.exists()
        content = toml_path.read_text(encoding="utf-8")
        assert "notify" in content
        assert "multi_agent = true" in content
        assert "[agents.gpd-executor]" in content

    def test_manifest_tracks_skills(self, installed: tuple[Path, Path]) -> None:
        """File manifest includes skill entries."""
        target, _ = installed
        manifest_path = target / "gpd-file-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "version" in manifest
        assert "files" in manifest


# ---------------------------------------------------------------------------
# OpenCode: install → read back → compare
# ---------------------------------------------------------------------------


class TestOpenCodeRoundtrip:
    """Install into .opencode/, verify flattened commands and permissions."""

    @pytest.fixture()
    def installed(self, gpd_root: Path, tmp_path: Path) -> Path:
        target = tmp_path / ".opencode"
        target.mkdir()
        OpenCodeAdapter().install(gpd_root, target)
        return target

    def test_commands_are_flattened(self, installed: Path) -> None:
        """OpenCode commands are flat: command/gpd-help.md (not commands/gpd/help.md)."""
        command_dir = installed / "command"
        assert command_dir.is_dir()
        gpd_cmds = [f for f in command_dir.iterdir() if f.name.startswith("gpd-") and f.suffix == ".md"]
        assert len(gpd_cmds) > 0

    def test_flattened_command_names(self, installed: Path, gpd_root: Path) -> None:
        """Flattened command names follow gpd-<name>.md convention."""
        command_dir = installed / "command"
        # help.md -> gpd-help.md, sub/deep.md -> gpd-sub-deep.md
        names = sorted(f.name for f in command_dir.iterdir() if f.name.startswith("gpd-"))
        assert "gpd-help.md" in names
        assert "gpd-sub-deep.md" in names

    def test_frontmatter_converted(self, installed: Path) -> None:
        """OpenCode frontmatter strips name: field, converts colors to hex."""
        for md in (installed / "command").glob("gpd-*.md"):
            content = md.read_text(encoding="utf-8")
            if content.startswith("---"):
                end = content.find("---", 3)
                fm = content[3:end]
                # name: should be stripped (OpenCode uses filename)
                assert "name:" not in fm, f"{md.name} still has name: field"

    def test_tool_names_converted(self, installed: Path) -> None:
        """OpenCode commands convert tool references (AskUserQuestion → question)."""
        for md in (installed / "command").glob("gpd-*.md"):
            content = md.read_text(encoding="utf-8")
            # AskUserQuestion should be converted to question
            assert "AskUserQuestion" not in content, f"{md.name} still has AskUserQuestion"

    def test_agents_installed(self, installed: Path, gpd_root: Path) -> None:
        """Agents are installed with OpenCode frontmatter conversion."""
        agents_dir = installed / "agents"
        assert agents_dir.is_dir()
        src_agents = sorted(f.name for f in (gpd_root / "agents").glob("*.md"))
        dest_agents = sorted(f.name for f in agents_dir.glob("*.md"))
        assert dest_agents == src_agents

    def test_gpd_content_installed(self, installed: Path) -> None:
        """get-physics-done/ content is installed."""
        gpd = installed / "get-physics-done"
        assert gpd.is_dir()
        for subdir in ("references", "templates", "workflows"):
            assert (gpd / subdir).is_dir()

    def test_shared_content_tool_references_are_translated(self, installed: Path) -> None:
        """Shared markdown content should use OpenCode runtime tool names."""
        workflow = (installed / "get-physics-done" / "workflows" / "wor.md").read_text(encoding="utf-8")
        reference = (installed / "get-physics-done" / "references" / "ref.md").read_text(encoding="utf-8")

        assert "question([" in workflow
        assert "AskUserQuestion" not in workflow
        assert "ask_user(" not in workflow
        assert "task(" in workflow
        assert "Task(" not in workflow
        assert "websearch" in reference
        assert "WebSearch" not in reference

    def test_shared_content_command_syntax_is_converted(self, installed: Path) -> None:
        """OpenCode shared content should use flat /gpd- command syntax."""
        for md in (installed / "get-physics-done").rglob("*.md"):
            content = md.read_text(encoding="utf-8")
            assert "/gpd:" not in content, f"{md.name} still has /gpd:"

    def test_version_file(self, installed: Path) -> None:
        """VERSION file present in get-physics-done/."""
        version = installed / "get-physics-done" / "VERSION"
        assert version.exists()
        assert len(version.read_text(encoding="utf-8").strip()) > 0

    def test_permissions_configured(self, installed: Path) -> None:
        """opencode.json has read + external_directory permissions for GPD."""
        config = json.loads((installed / "opencode.json").read_text(encoding="utf-8"))
        perms = config.get("permission", {})
        read_perms = perms.get("read", {})
        ext_perms = perms.get("external_directory", {})
        assert any("get-physics-done" in k for k in read_perms)
        assert any("get-physics-done" in k for k in ext_perms)

    def test_manifest_present(self, installed: Path) -> None:
        """File manifest tracks flattened commands."""
        manifest_path = installed / "gpd-file-manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.get("files", {})
        assert any(k.startswith("command/gpd-") for k in files)


def test_real_installed_opencode_artifacts_rewrite_gpd_cli_calls_to_runtime_bridge(tmp_path: Path) -> None:
    target = _install_real_repo_for_runtime(tmp_path, "opencode")
    expected_bridge = expected_opencode_bridge(target, is_global=False)
    command = (target / "command" / "gpd-settings.md").read_text(encoding="utf-8")
    workflow = (target / "get-physics-done" / "workflows" / "settings.md").read_text(encoding="utf-8")
    agent = (target / "agents" / "gpd-planner.md").read_text(encoding="utf-8")

    assert expected_bridge + " config ensure-section" in command
    assert f'INIT=$({expected_bridge} init progress --include state,config)' in command
    assert expected_bridge + " config ensure-section" in workflow
    assert f'INIT=$({expected_bridge} init progress --include state,config)' in workflow
    assert 'echo "ERROR: gpd initialization failed: $INIT"' in workflow
    assert f'INIT=$({expected_bridge} init plan-phase "<PHASE>")' in agent
    assert 'INIT=$(gpd init progress --include state,config)' not in workflow
    assert 'INIT=$(gpd init plan-phase "<PHASE>")' not in agent


# ---------------------------------------------------------------------------
# Cross-runtime: install/uninstall cycle for each runtime
# ---------------------------------------------------------------------------


class TestInstallUninstallCycle:
    """Install then uninstall for each runtime — verify clean removal."""

    def test_claude_code_cycle(self, gpd_root: Path, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter()
        target = tmp_path / ".claude"
        target.mkdir()

        adapter.install(gpd_root, target)
        assert (target / "commands" / "gpd").is_dir()
        assert (target / "get-physics-done").is_dir()

        adapter.uninstall(target)
        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()

    def test_gemini_cycle(self, gpd_root: Path, tmp_path: Path) -> None:
        target = tmp_path / ".gemini"
        target.mkdir()

        _install_gemini_for_tests(gpd_root, target)
        assert (target / "commands" / "gpd").is_dir()
        assert (target / "get-physics-done").is_dir()

        GeminiAdapter().uninstall(target)
        assert not (target / "commands" / "gpd").exists()
        assert not (target / "get-physics-done").exists()

    def test_codex_cycle(self, gpd_root: Path, tmp_path: Path) -> None:
        adapter = CodexAdapter()
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()

        adapter.install(gpd_root, target, skills_dir=skills)
        assert any(d.name.startswith("gpd-") for d in skills.iterdir() if d.is_dir())
        assert (target / "get-physics-done").is_dir()

        adapter.uninstall(target, skills_dir=skills)
        assert not skills.exists() or not any(d.name.startswith("gpd-") for d in skills.iterdir() if d.is_dir())
        assert not (target / "get-physics-done").exists()

    def test_opencode_cycle(self, gpd_root: Path, tmp_path: Path) -> None:
        adapter = OpenCodeAdapter()
        target = tmp_path / ".opencode"
        target.mkdir()

        adapter.install(gpd_root, target)
        assert (target / "command").is_dir()
        assert (target / "get-physics-done").is_dir()

        adapter.uninstall(target)
        assert not (target / "get-physics-done").exists()
        gpd_cmds = (
            [f for f in (target / "command").iterdir() if f.name.startswith("gpd-")]
            if (target / "command").exists()
            else []
        )
        assert len(gpd_cmds) == 0


# ---------------------------------------------------------------------------
# Serialization roundtrip: source spec → install → re-read matches
# ---------------------------------------------------------------------------


class TestSerializationRoundtrip:
    """Verify that content survives serialization through each adapter."""

    def test_claude_code_body_preserved(self, gpd_root: Path, tmp_path: Path) -> None:
        """The body text of a command survives Claude Code install."""
        target = tmp_path / ".claude"
        target.mkdir()
        ClaudeCodeAdapter().install(gpd_root, target)

        installed = (target / "commands" / "gpd" / "help.md").read_text(encoding="utf-8")
        # Body should contain the non-placeholder text
        assert "Help body" in installed

    def test_gemini_toml_preserves_body(self, gpd_root: Path, tmp_path: Path) -> None:
        """Command body text survives TOML conversion for Gemini."""
        target = tmp_path / ".gemini"
        target.mkdir()
        _install_gemini_for_tests(gpd_root, target)

        toml_file = target / "commands" / "gpd" / "help.toml"
        content = toml_file.read_text(encoding="utf-8")
        assert "Help body" in content

    def test_codex_skill_preserves_body(self, gpd_root: Path, tmp_path: Path) -> None:
        """Command body text survives Codex SKILL.md conversion."""
        target = tmp_path / ".codex"
        target.mkdir()
        skills = tmp_path / "skills"
        skills.mkdir()
        CodexAdapter().install(gpd_root, target, skills_dir=skills)

        skill_md = skills / "gpd-help" / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert "Help body" in content

    def test_opencode_flat_preserves_body(self, gpd_root: Path, tmp_path: Path) -> None:
        """Command body text survives OpenCode flattening."""
        target = tmp_path / ".opencode"
        target.mkdir()
        OpenCodeAdapter().install(gpd_root, target)

        cmd = target / "command" / "gpd-help.md"
        content = cmd.read_text(encoding="utf-8")
        assert "Help body" in content

    def test_nested_command_survives_all_runtimes(self, gpd_root: Path, tmp_path: Path) -> None:
        """The nested sub/deep.md command is reachable in every runtime."""
        # Claude Code: commands/gpd/sub/deep.md
        cc_target = tmp_path / "cc" / ".claude"
        cc_target.mkdir(parents=True)
        ClaudeCodeAdapter().install(gpd_root, cc_target)
        assert (cc_target / "commands" / "gpd" / "sub" / "deep.md").exists()

        # Gemini: commands/gpd/sub/deep.toml
        gem_target = tmp_path / "gem" / ".gemini"
        gem_target.mkdir(parents=True)
        _install_gemini_for_tests(gpd_root, gem_target)
        assert (gem_target / "commands" / "gpd" / "sub" / "deep.toml").exists()

        # Codex: skills/gpd-sub-deep/SKILL.md
        codex_target = tmp_path / "codex" / ".codex"
        codex_target.mkdir(parents=True)
        codex_skills = tmp_path / "codex" / "skills"
        codex_skills.mkdir(parents=True)
        CodexAdapter().install(gpd_root, codex_target, skills_dir=codex_skills)
        assert (codex_skills / "gpd-sub-deep" / "SKILL.md").exists()

        # OpenCode: command/gpd-sub-deep.md
        oc_target = tmp_path / "oc" / ".opencode"
        oc_target.mkdir(parents=True)
        OpenCodeAdapter().install(gpd_root, oc_target)
        assert (oc_target / "command" / "gpd-sub-deep.md").exists()


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
def test_real_installed_command_include_semantics_are_equivalent_across_runtimes(tmp_path: Path, runtime: str) -> None:
    target = _install_real_repo_for_runtime(tmp_path, runtime)
    content = _read_compare_experiment_command(tmp_path, target, runtime)
    normalized = _canonicalize_runtime_markdown(content, runtime=runtime)
    lowered = normalized.lower()

    assert "@ include not resolved:" not in content.lower()
    assert "@ include cycle detected:" not in content.lower()
    assert "@ include read error:" not in content.lower()
    assert "@ include depth limit reached:" not in content.lower()
    assert "Systematically compare theoretical predictions with experimental or observational data." in normalized
    assert "unit mismatches and convention mismatches are the two most common sources of discrepancy" in lowered
    assert "what decisive output or contract target was predicted" in lowered


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
def test_real_installed_shared_prompt_semantics_are_equivalent_across_runtimes(tmp_path: Path, runtime: str) -> None:
    target = _install_real_repo_for_runtime(tmp_path, runtime)
    delegation = _canonicalize_runtime_markdown(
        (target / "get-physics-done" / "references" / "orchestration" / "agent-delegation.md").read_text(
            encoding="utf-8"
        ),
        runtime=runtime,
    )
    execute_plan = _canonicalize_runtime_markdown(
        (target / "get-physics-done" / "workflows" / "execute-plan.md").read_text(encoding="utf-8"),
        runtime=runtime,
    )

    assert "gpd resolve-model" in delegation
    assert "Fresh context" in delegation
    assert "Assign an explicit write scope" in delegation
    assert "review_cadence" in execute_plan
    assert "Required first-result sanity gate" in execute_plan
    assert "Contract-backed plans" in execute_plan


@pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
def test_real_installed_contract_and_review_surfaces_keep_required_schema_bodies(
    tmp_path: Path, runtime: str
) -> None:
    target = _install_real_repo_for_runtime(tmp_path, runtime)

    verify_work = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(tmp_path, target, runtime, "verify-work"),
        runtime=runtime,
    )
    sync_state = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(tmp_path, target, runtime, "sync-state"),
        runtime=runtime,
    )
    write_paper = _canonicalize_runtime_markdown(
        _read_runtime_command_prompt(tmp_path, target, runtime, "write-paper"),
        runtime=runtime,
    )
    review_literature = _canonicalize_runtime_markdown(
        _read_runtime_agent_prompt(target, runtime, "gpd-review-literature"),
        runtime=runtime,
    )
    review_reader = _canonicalize_runtime_markdown(
        _read_runtime_agent_prompt(target, runtime, "gpd-review-reader"),
        runtime=runtime,
    )
    review_math = _canonicalize_runtime_markdown(
        _read_runtime_agent_prompt(target, runtime, "gpd-review-math"),
        runtime=runtime,
    )
    review_physics = _canonicalize_runtime_markdown(
        _read_runtime_agent_prompt(target, runtime, "gpd-review-physics"),
        runtime=runtime,
    )
    review_significance = _canonicalize_runtime_markdown(
        _read_runtime_agent_prompt(target, runtime, "gpd-review-significance"),
        runtime=runtime,
    )
    referee = _canonicalize_runtime_markdown(
        _read_runtime_agent_prompt(target, runtime, "gpd-referee"),
        runtime=runtime,
    )

    for content in (
        verify_work,
        sync_state,
        write_paper,
        review_literature,
        review_reader,
        review_math,
        review_physics,
        review_significance,
        referee,
    ):
        lowered = content.lower()
        assert "@ include not resolved:" not in lowered
        assert "@ include cycle detected:" not in lowered
        assert "@ include read error:" not in lowered
        assert "@ include depth limit reached:" not in lowered

    assert "Canonical source of truth for `plan_contract_ref`, `contract_results`, and `comparison_verdicts`" in verify_work
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference]" in verify_work
    assert 'gap_subject_kind: "{check_subject_kind}"' in verify_work
    assert "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]" not in verify_work
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]" not in verify_work
    assert "# state.json Schema" in sync_state
    write_paper_section = _review_contract_section(write_paper)
    registry_write_paper_section = _review_contract_section(get_command("write-paper").content)
    assert write_paper_section == registry_write_paper_section
    assert "review_contract:" in write_paper_section
    assert "review-contract:" not in write_paper_section
    assert write_paper.index("## Review Contract") < write_paper.index("Reproducibility Manifest Template")
    assert "Reproducibility Manifest Template" in write_paper
    for command_name in ("write-paper", "respond-to-referees", "verify-work", "arxiv-submission", "peer-review"):
        installed_content = _read_runtime_command_prompt(tmp_path, target, runtime, command_name)
        installed_section = _review_contract_section(installed_content)
        registry_section = _review_contract_section(get_command(command_name).content)
        assert installed_section == registry_section
        assert installed_content.count("## Review Contract") == 1
        assert installed_section.count("## Review Contract") == 1
    assert "Peer Review Panel Protocol" in review_literature
    assert '"stage_id": "reader | literature | math | physics | interestingness"' in review_literature
    assert '"stage_kind": "reader | literature | math | physics | interestingness"' in review_literature
    assert "Peer Review Panel Protocol" in review_reader
    for review_stage, stage_path, stage_kind in (
        (review_math, "STAGE-math.json", "math"),
        (review_physics, "STAGE-physics.json", "physics"),
        (review_significance, "STAGE-interestingness.json", "interestingness"),
    ):
        assert f"Required schema for `{stage_path}` (`StageReviewReport`, mirroring the staged-review contract):" in review_stage
        assert f"`stage_id` and `stage_kind` must both be `{stage_kind}`" in review_stage
        assert "do not collapse them to prose or scalars" in review_stage
    assert "Review Ledger Schema" in referee
    assert "Referee Decision Schema" in referee
