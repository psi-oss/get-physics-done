"""Tests for gpd/registry.py — content registry edge cases.

Covers: empty dirs, missing frontmatter, unexpected fields, non-UTF8 files,
cache invalidation, merge/override behavior, and public API error paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.registry import (
    AgentDef,
    CommandDef,
    _parse_agent_file,
    _parse_command_file,
    _parse_frontmatter,
    _parse_tools,
    _RegistryCache,
)

# ─── Frontmatter parsing ────────────────────────────────────────────────────


class TestParseFrontmatter:
    """Tests for _parse_frontmatter edge cases."""

    def test_valid_frontmatter(self) -> None:
        text = "---\nname: test\ndescription: hello\n---\nBody here."
        meta, body = _parse_frontmatter(text)
        assert meta == {"name": "test", "description": "hello"}
        assert body == "Body here."

    def test_missing_frontmatter(self) -> None:
        text = "No frontmatter at all.\nJust body."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_empty_frontmatter(self) -> None:
        # Regex requires content between --- delimiters; empty block doesn't match
        text = "---\n---\nBody only."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text  # No match → full text returned as body

    def test_frontmatter_with_only_whitespace(self) -> None:
        text = "---\n  \n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == "Body."

    def test_non_dict_frontmatter_returns_empty(self) -> None:
        text = "---\n- item1\n- item2\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_scalar_frontmatter_returns_empty(self) -> None:
        text = "---\njust a string\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_frontmatter_with_crlf_line_endings(self) -> None:
        text = "---\r\nname: test\r\n---\r\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {"name": "test"}
        assert body == "Body."

    def test_frontmatter_no_body_after_closing(self) -> None:
        text = "---\nname: test\n---"
        meta, body = _parse_frontmatter(text)
        assert meta == {"name": "test"}
        assert body == ""

    def test_frontmatter_with_unexpected_fields(self) -> None:
        text = "---\nname: test\nextra_field: surprise\nanother: 42\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta["name"] == "test"
        assert meta["extra_field"] == "surprise"
        assert meta["another"] == 42
        assert body == "Body."


# ─── _parse_tools ────────────────────────────────────────────────────────────


class TestParseTools:
    """Tests for _parse_tools normalization."""

    def test_comma_separated_string(self) -> None:
        assert _parse_tools("Read, Write, Bash") == ["Read", "Write", "Bash"]

    def test_list_input(self) -> None:
        assert _parse_tools(["Read", "Write"]) == ["Read", "Write"]

    def test_empty_string(self) -> None:
        assert _parse_tools("") == []

    def test_none_returns_empty(self) -> None:
        assert _parse_tools(None) == []

    def test_int_returns_empty(self) -> None:
        assert _parse_tools(42) == []

    def test_list_with_non_string_elements(self) -> None:
        assert _parse_tools([1, True, "Bash"]) == ["1", "True", "Bash"]

    def test_string_with_extra_whitespace(self) -> None:
        assert _parse_tools("  Read ,  , Write  ") == ["Read", "Write"]


# ─── Agent file parsing ─────────────────────────────────────────────────────


class TestParseAgentFile:
    """Tests for _parse_agent_file with various file contents."""

    def test_full_agent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "my-agent.md"
        f.write_text(
            "---\nname: my-agent\ndescription: A test agent\ntools: Read, Write\ncolor: blue\n---\nSystem prompt.",
            encoding="utf-8",
        )
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "my-agent"
        assert agent.description == "A test agent"
        assert agent.tools == ["Read", "Write"]
        assert agent.color == "blue"
        assert agent.system_prompt == "System prompt."
        assert agent.source == "agents"

    def test_agent_file_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "bare-agent.md"
        f.write_text("Just a body, no frontmatter.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "bare-agent"  # Falls back to stem
        assert agent.description == ""
        assert agent.tools == []
        assert agent.system_prompt == "Just a body, no frontmatter."

    def test_agent_file_missing_optional_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "minimal.md"
        f.write_text("---\nname: minimal\n---\nPrompt.", encoding="utf-8")
        agent = _parse_agent_file(f, source="specs/agents")
        assert agent.name == "minimal"
        assert agent.description == ""
        assert agent.tools == []
        assert agent.color == ""
        assert agent.source == "specs/agents"

    def test_agent_file_unexpected_extra_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "extra.md"
        f.write_text("---\nname: extra\nversion: 2\ncustom_key: hi\n---\nBody.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "extra"
        # Extra fields are silently ignored — no crash
        assert agent.system_prompt == "Body."

    def test_agent_file_tools_as_list(self, tmp_path: Path) -> None:
        f = tmp_path / "list-tools.md"
        f.write_text("---\nname: list-tools\ntools:\n  - Read\n  - Bash\n---\nBody.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.tools == ["Read", "Bash"]

    def test_agent_file_empty_body(self, tmp_path: Path) -> None:
        f = tmp_path / "nobody.md"
        f.write_text("---\nname: nobody\n---\n", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.system_prompt == ""


# ─── Command file parsing ───────────────────────────────────────────────────


class TestParseCommandFile:
    """Tests for _parse_command_file with various file contents."""

    def test_full_command_file(self, tmp_path: Path) -> None:
        f = tmp_path / "debug.md"
        f.write_text(
            "---\nname: gpd:debug\ndescription: Debug command\n"
            "argument-hint: <error>\nrequires:\n  project: true\n"
            "allowed-tools:\n  - Read\n  - Bash\n---\nCommand body.",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "gpd:debug"
        assert cmd.description == "Debug command"
        assert cmd.argument_hint == "<error>"
        assert cmd.requires == {"project": True}
        assert cmd.allowed_tools == ["Read", "Bash"]
        assert cmd.content == "Command body."

    def test_command_file_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "bare.md"
        f.write_text("No frontmatter command.", encoding="utf-8")
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "bare"  # Falls back to stem
        assert cmd.description == ""
        assert cmd.argument_hint == ""
        assert cmd.requires == {}
        assert cmd.allowed_tools == []

    def test_command_requires_non_dict_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-requires.md"
        f.write_text("---\nname: bad\nrequires: not-a-dict\n---\nBody.", encoding="utf-8")
        cmd = _parse_command_file(f, source="commands")
        assert cmd.requires == {}

    def test_command_allowed_tools_non_list_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools.md"
        f.write_text("---\nname: bad\nallowed-tools: just-a-string\n---\nBody.", encoding="utf-8")
        cmd = _parse_command_file(f, source="commands")
        assert cmd.allowed_tools == []

    def test_command_unexpected_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "extra.md"
        f.write_text("---\nname: extra\nversion: 99\nfoo: bar\n---\nBody.", encoding="utf-8")
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "extra"
        assert cmd.content == "Body."


# ─── Non-UTF8 / encoding edge cases ─────────────────────────────────────────


class TestEncodingEdgeCases:
    """Tests for files with encoding issues."""

    def test_agent_file_non_utf8_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-encoding.md"
        f.write_bytes(b"---\nname: broken\n---\n\xff\xfe Invalid UTF-8")
        with pytest.raises(UnicodeDecodeError):
            _parse_agent_file(f, source="agents")

    def test_command_file_non_utf8_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-encoding.md"
        f.write_bytes(b"---\nname: broken\n---\n\xff\xfe Invalid")
        with pytest.raises(UnicodeDecodeError):
            _parse_command_file(f, source="commands")

    def test_agent_file_utf8_with_bom(self, tmp_path: Path) -> None:
        # UTF-8 BOM prefix — yaml.safe_load handles this, but frontmatter regex may not match
        f = tmp_path / "bom-agent.md"
        f.write_bytes(b"\xef\xbb\xbf---\nname: bom-test\n---\nBody.")
        # BOM means the "---" doesn't start at position 0 of the string,
        # so frontmatter regex won't match — name falls back to stem
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "bom-agent"
        assert "Body." in agent.system_prompt


# ─── Discovery with empty/missing dirs ──────────────────────────────────────


class TestDiscoveryEmptyDirs:
    """Tests for _discover_agents/_discover_commands with empty or missing directories."""

    def test_discover_agents_empty_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        specs_agents_dir = tmp_path / "specs" / "agents"
        specs_agents_dir.mkdir(parents=True)

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", specs_agents_dir)

        result = registry._discover_agents()
        assert result == {}

    def test_discover_commands_empty_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        specs_skills_dir = tmp_path / "specs" / "skills"
        specs_skills_dir.mkdir(parents=True)

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", specs_skills_dir)

        result = registry._discover_commands()
        assert result == {}

    def test_discover_agents_missing_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent-specs")

        result = registry._discover_agents()
        assert result == {}

    def test_discover_commands_missing_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "COMMANDS_DIR", tmp_path / "nonexistent-commands")
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent-specs")

        result = registry._discover_commands()
        assert result == {}


# ─── Agent merge/override behavior ──────────────────────────────────────────


class TestAgentMergeBehavior:
    """Tests that primary agents/ overrides specs/agents/ for duplicate names."""

    def test_primary_overrides_specs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "agents"
        specs_dir.mkdir(parents=True)
        (specs_dir / "dupe.md").write_text(
            "---\nname: dupe\ndescription: from specs\ncolor: red\n---\nSpecs prompt.", encoding="utf-8"
        )

        primary_dir = tmp_path / "agents"
        primary_dir.mkdir()
        (primary_dir / "dupe.md").write_text(
            "---\nname: dupe\ndescription: from primary\ncolor: green\n---\nPrimary prompt.", encoding="utf-8"
        )

        monkeypatch.setattr(registry, "AGENTS_DIR", primary_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", specs_dir)

        result = registry._discover_agents()
        assert len(result) == 1
        assert result["dupe"].description == "from primary"
        assert result["dupe"].source == "agents"
        assert result["dupe"].color == "green"

    def test_specs_only_when_no_primary(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "agents"
        specs_dir.mkdir(parents=True)
        (specs_dir / "unique.md").write_text(
            "---\nname: unique\ndescription: only in specs\n---\nSpecs prompt.", encoding="utf-8"
        )

        primary_dir = tmp_path / "agents"
        primary_dir.mkdir()

        monkeypatch.setattr(registry, "AGENTS_DIR", primary_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", specs_dir)

        result = registry._discover_agents()
        assert "unique" in result
        assert result["unique"].source == "specs/agents"

    def test_mixed_agents_from_both_dirs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "agents"
        specs_dir.mkdir(parents=True)
        (specs_dir / "alpha.md").write_text("---\nname: alpha\n---\nSpecs alpha.", encoding="utf-8")
        (specs_dir / "beta.md").write_text("---\nname: beta\n---\nSpecs beta.", encoding="utf-8")

        primary_dir = tmp_path / "agents"
        primary_dir.mkdir()
        (primary_dir / "beta.md").write_text("---\nname: beta\n---\nPrimary beta.", encoding="utf-8")
        (primary_dir / "gamma.md").write_text("---\nname: gamma\n---\nPrimary gamma.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", primary_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", specs_dir)

        result = registry._discover_agents()
        assert set(result.keys()) == {"alpha", "beta", "gamma"}
        assert result["alpha"].source == "specs/agents"
        assert result["beta"].source == "agents"  # Primary wins
        assert result["gamma"].source == "agents"


# ─── Command merge/override behavior ────────────────────────────────────────


class TestCommandMergeBehavior:
    """Tests that primary commands/ overrides specs/skills/ for duplicate names."""

    def test_primary_commands_override_specs_skills(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "skills"
        specs_dir.mkdir(parents=True)
        skill_dir = specs_dir / "debug"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: gpd-debug\ndescription: from specs\n---\nSpecs body.", encoding="utf-8"
        )

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "debug.md").write_text(
            "---\nname: gpd:debug\ndescription: from primary\n---\nPrimary body.", encoding="utf-8"
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", specs_dir)

        result = registry._discover_commands()
        assert "debug" in result
        assert result["debug"].description == "from primary"
        assert result["debug"].source == "commands"

    def test_specs_skill_dir_without_skill_md_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "skills"
        specs_dir.mkdir(parents=True)
        # Directory without SKILL.md — should be ignored
        empty_skill = specs_dir / "empty-skill"
        empty_skill.mkdir()

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", specs_dir)

        result = registry._discover_commands()
        assert result == {}

    def test_specs_skill_file_not_dir_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "skills"
        specs_dir.mkdir(parents=True)
        # File instead of directory — should be skipped by is_dir() check
        (specs_dir / "not-a-dir.txt").write_text("I am a file", encoding="utf-8")

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", specs_dir)

        result = registry._discover_commands()
        assert result == {}

    def test_command_keyed_by_stem_not_frontmatter_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "my-cmd.md").write_text("---\nname: gpd:my-cmd\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")

        result = registry._discover_commands()
        # Keyed by filesystem stem, not frontmatter name
        assert "my-cmd" in result
        assert "gpd:my-cmd" not in result

    def test_specs_skill_keyed_by_dir_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        specs_dir = tmp_path / "specs" / "skills"
        specs_dir.mkdir(parents=True)
        skill_dir = specs_dir / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: gpd-my-skill\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", specs_dir)

        result = registry._discover_commands()
        # Keyed by directory name, not frontmatter name
        assert "my-skill" in result
        assert result["my-skill"].name == "my-skill"  # Overwritten to canonical dir name


# ─── Non-.md files ignored ───────────────────────────────────────────────────


class TestNonMdFilesIgnored:
    """Tests that non-.md files are ignored during discovery."""

    def test_non_md_files_in_agents_dir_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "valid.md").write_text("---\nname: valid\n---\nPrompt.", encoding="utf-8")
        (agents_dir / "notes.txt").write_text("Not an agent.", encoding="utf-8")
        (agents_dir / "data.json").write_text("{}", encoding="utf-8")
        (agents_dir / "__pycache__").mkdir()

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")

        result = registry._discover_agents()
        assert list(result.keys()) == ["valid"]

    def test_non_md_files_in_commands_dir_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "valid.md").write_text("---\nname: valid\n---\nBody.", encoding="utf-8")
        (commands_dir / "readme.txt").write_text("Not a command.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")

        result = registry._discover_commands()
        assert list(result.keys()) == ["valid"]


# ─── Cache behavior ─────────────────────────────────────────────────────────


class TestRegistryCache:
    """Tests for _RegistryCache lazy-load and invalidation."""

    def test_lazy_load_agents(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "cached.md").write_text("---\nname: cached\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")

        cache = _RegistryCache()
        assert cache._agents is None
        agents = cache.agents()
        assert "cached" in agents
        assert cache._agents is not None

    def test_lazy_load_commands(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "cached.md").write_text("---\nname: cached\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")

        cache = _RegistryCache()
        assert cache._commands is None
        cmds = cache.commands()
        assert "cached" in cmds
        assert cache._commands is not None

    def test_cache_returns_same_dict_on_second_call(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "a.md").write_text("---\nname: a\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")

        cache = _RegistryCache()
        first = cache.agents()
        second = cache.agents()
        assert first is second

    def test_invalidate_clears_both_caches(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "x.md").write_text("---\nname: x\n---\nPrompt.", encoding="utf-8")

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "y.md").write_text("---\nname: y\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")

        cache = _RegistryCache()
        cache.agents()
        cache.commands()
        assert cache._agents is not None
        assert cache._commands is not None

        cache.invalidate()
        assert cache._agents is None
        assert cache._commands is None

    def test_invalidate_forces_re_discovery(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "first.md").write_text("---\nname: first\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")

        cache = _RegistryCache()
        result1 = cache.agents()
        assert "first" in result1

        # Add a new file and invalidate
        (agents_dir / "second.md").write_text("---\nname: second\n---\nPrompt2.", encoding="utf-8")
        cache.invalidate()

        result2 = cache.agents()
        assert "first" in result2
        assert "second" in result2
        assert result1 is not result2


# ─── Public API ──────────────────────────────────────────────────────────────


class TestPublicAPI:
    """Tests for the module-level public API functions."""

    def test_get_agent_not_found_raises_key_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        with pytest.raises(KeyError, match="Agent not found: nonexistent"):
            registry.get_agent("nonexistent")

    def test_get_command_not_found_raises_key_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "COMMANDS_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        with pytest.raises(KeyError, match="Command not found: nonexistent"):
            registry.get_command("nonexistent")

    def test_list_agents_returns_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "charlie.md").write_text("---\nname: charlie\n---\nC.", encoding="utf-8")
        (agents_dir / "alpha.md").write_text("---\nname: alpha\n---\nA.", encoding="utf-8")
        (agents_dir / "bravo.md").write_text("---\nname: bravo\n---\nB.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        names = registry.list_agents()
        assert names == ["alpha", "bravo", "charlie"]

    def test_list_commands_returns_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "zebra.md").write_text("---\nname: zebra\n---\nZ.", encoding="utf-8")
        (commands_dir / "apple.md").write_text("---\nname: apple\n---\nA.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        names = registry.list_commands()
        assert names == ["apple", "zebra"]

    def test_get_agent_returns_correct_def(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text(
            "---\nname: test-agent\ndescription: Tested\ntools: Read\ncolor: red\n---\nTest prompt.", encoding="utf-8"
        )

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        agent = registry.get_agent("test-agent")
        assert isinstance(agent, AgentDef)
        assert agent.name == "test-agent"
        assert agent.description == "Tested"
        assert agent.tools == ["Read"]

    def test_get_command_returns_correct_def(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "test-cmd.md").write_text(
            "---\nname: gpd:test-cmd\ndescription: Tested\n---\nCmd body.", encoding="utf-8"
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "SPECS_SKILLS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        cmd = registry.get_command("test-cmd")
        assert isinstance(cmd, CommandDef)
        assert cmd.name == "gpd:test-cmd"  # Frontmatter name preserved
        assert cmd.description == "Tested"

    def test_invalidate_cache_module_level(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "SPECS_AGENTS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        assert registry.list_agents() == []

        (agents_dir / "new.md").write_text("---\nname: new\n---\nPrompt.", encoding="utf-8")
        registry.invalidate_cache()

        assert registry.list_agents() == ["new"]


# ─── Dataclass properties ───────────────────────────────────────────────────


class TestDataclasses:
    """Tests for AgentDef and CommandDef dataclass properties."""

    def test_agent_def_frozen(self) -> None:
        agent = AgentDef(name="a", description="d", system_prompt="s", tools=[], color="", path="/p", source="agents")
        with pytest.raises(AttributeError):
            agent.name = "b"  # type: ignore[misc]

    def test_command_def_frozen(self) -> None:
        cmd = CommandDef(
            name="c",
            description="d",
            argument_hint="",
            requires={},
            allowed_tools=[],
            content="",
            path="/p",
            source="commands",
        )
        with pytest.raises(AttributeError):
            cmd.name = "x"  # type: ignore[misc]

    def test_agent_def_slots(self) -> None:
        agent = AgentDef(name="a", description="d", system_prompt="s", tools=[], color="", path="/p", source="agents")
        with pytest.raises((AttributeError, TypeError)):
            agent.new_attr = "nope"  # type: ignore[misc]

    def test_command_def_slots(self) -> None:
        cmd = CommandDef(
            name="c",
            description="d",
            argument_hint="",
            requires={},
            allowed_tools=[],
            content="",
            path="/p",
            source="commands",
        )
        with pytest.raises((AttributeError, TypeError)):
            cmd.new_attr = "nope"  # type: ignore[misc]
