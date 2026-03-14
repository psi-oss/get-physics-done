"""Tests for gpd/registry.py — content registry edge cases."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.registry import (
    AgentDef,
    CommandDef,
    SkillDef,
    _parse_agent_file,
    _parse_command_file,
    _parse_frontmatter,
    _parse_tools,
    _RegistryCache,
    load_agents_from_dir,
)


class TestParseFrontmatter:
    """Tests for _parse_frontmatter edge cases."""

    def test_valid_frontmatter(self) -> None:
        meta, body = _parse_frontmatter("---\nname: test\ndescription: hello\n---\nBody here.")
        assert meta == {"name": "test", "description": "hello"}
        assert body == "Body here."

    def test_missing_frontmatter(self) -> None:
        text = "No frontmatter at all.\nJust body."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_empty_frontmatter(self) -> None:
        text = "---\n---\nBody only."
        meta, body = _parse_frontmatter(text)
        assert meta == {}
        assert body == "Body only."

    def test_frontmatter_with_only_whitespace(self) -> None:
        meta, body = _parse_frontmatter("---\n  \n---\nBody.")
        assert meta == {}
        assert body == "Body."

    def test_non_dict_frontmatter_raises(self) -> None:
        text = "---\n- item1\n- item2\n---\nBody."
        with pytest.raises(ValueError, match="Frontmatter must parse to a mapping"):
            _parse_frontmatter(text)

    def test_scalar_frontmatter_raises(self) -> None:
        text = "---\njust a string\n---\nBody."
        with pytest.raises(ValueError, match="Frontmatter must parse to a mapping"):
            _parse_frontmatter(text)

    def test_malformed_yaml_frontmatter_raises(self) -> None:
        text = "---\nname: test\nbad: [unterminated\n---\nBody."

        with pytest.raises(ValueError, match="Malformed YAML frontmatter"):
            _parse_frontmatter(text)

    def test_frontmatter_with_crlf_line_endings(self) -> None:
        meta, body = _parse_frontmatter("---\r\nname: test\r\n---\r\nBody.")
        assert meta == {"name": "test"}
        assert body == "Body."

    def test_frontmatter_no_body_after_closing(self) -> None:
        meta, body = _parse_frontmatter("---\nname: test\n---")
        assert meta == {"name": "test"}
        assert body == ""

    def test_frontmatter_with_unexpected_fields(self) -> None:
        meta, body = _parse_frontmatter("---\nname: test\nextra_field: surprise\nanother: 42\n---\nBody.")
        assert meta["name"] == "test"
        assert meta["extra_field"] == "surprise"
        assert meta["another"] == 42
        assert body == "Body."

    def test_frontmatter_with_leading_blank_lines_is_parsed(self) -> None:
        text = "\n\n---\nname: test\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta == {"name": "test"}
        assert body == "Body."

    def test_frontmatter_block_scalar_preserves_indented_triple_dash_lines(self) -> None:
        text = "---\ndescription: |\n  first\n  ---\n  second\n---\nBody."

        meta, body = _parse_frontmatter(text)

        assert meta == {"description": "first\n---\nsecond\n"}
        assert body == "Body."


class TestParseTools:
    """Tests for _parse_tools normalization."""

    def test_comma_separated_string(self) -> None:
        assert _parse_tools("file_read, file_write, shell") == ["file_read", "file_write", "shell"]

    def test_list_input(self) -> None:
        assert _parse_tools(["file_read", "file_write"]) == ["file_read", "file_write"]

    def test_empty_string(self) -> None:
        assert _parse_tools("") == []

    def test_none_returns_empty(self) -> None:
        assert _parse_tools(None) == []

    def test_int_returns_empty(self) -> None:
        assert _parse_tools(42) == []

    def test_list_with_non_string_elements(self) -> None:
        assert _parse_tools([1, True, "shell"]) == ["1", "True", "shell"]

    def test_string_with_extra_whitespace(self) -> None:
        assert _parse_tools("  file_read ,  , file_write  ") == ["file_read", "file_write"]


class TestParseAgentFile:
    """Tests for _parse_agent_file with various file contents."""

    def test_full_agent_file(self, tmp_path: Path) -> None:
        f = tmp_path / "my-agent.md"
        f.write_text(
            "---\nname: my-agent\ndescription: A test agent\ntools: file_read, file_write\n"
            "surface: public\nrole_family: worker\nartifact_write_authority: scoped_write\n"
            "shared_state_authority: direct\ncolor: blue\n---\nSystem prompt.",
            encoding="utf-8",
        )
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "my-agent"
        assert agent.description == "A test agent"
        assert agent.tools == ["file_read", "file_write"]
        assert agent.commit_authority == "orchestrator"
        assert agent.surface == "public"
        assert agent.role_family == "worker"
        assert agent.artifact_write_authority == "scoped_write"
        assert agent.shared_state_authority == "direct"
        assert agent.color == "blue"
        assert agent.system_prompt == "System prompt."
        assert agent.source == "agents"

    def test_agent_file_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "bare-agent.md"
        f.write_text("Just a body, no frontmatter.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "bare-agent"
        assert agent.description == ""
        assert agent.tools == []
        assert agent.system_prompt == "Just a body, no frontmatter."

    def test_agent_file_missing_optional_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "minimal.md"
        f.write_text("---\nname: minimal\n---\nPrompt.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "minimal"
        assert agent.description == ""
        assert agent.tools == []
        assert agent.commit_authority == "orchestrator"
        assert agent.surface == "internal"
        assert agent.role_family == "analysis"
        assert agent.artifact_write_authority == "scoped_write"
        assert agent.shared_state_authority == "return_only"
        assert agent.color == ""
        assert agent.source == "agents"

    def test_agent_file_parses_explicit_commit_authority(self, tmp_path: Path) -> None:
        f = tmp_path / "direct.md"
        f.write_text("---\nname: direct\ncommit_authority: direct\n---\nPrompt.", encoding="utf-8")

        agent = _parse_agent_file(f, source="agents")

        assert agent.commit_authority == "direct"

    def test_agent_file_invalid_commit_authority_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-authority.md"
        f.write_text("---\nname: bad\ncommit_authority: someday\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid commit_authority"):
            _parse_agent_file(f, source="agents")

    @pytest.mark.parametrize(
        ("field_name", "field_value", "expected_error"),
        [
            ("surface", "sometimes", "Invalid surface"),
            ("role_family", "planner", "Invalid role_family"),
            ("artifact_write_authority", "shared_write", "Invalid artifact_write_authority"),
            ("shared_state_authority", "scoped", "Invalid shared_state_authority"),
        ],
    )
    def test_agent_file_invalid_spawn_metadata_raises(
        self,
        tmp_path: Path,
        field_name: str,
        field_value: str,
        expected_error: str,
    ) -> None:
        f = tmp_path / "bad-metadata.md"
        f.write_text(f"---\nname: bad\n{field_name}: {field_value}\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match=expected_error):
            _parse_agent_file(f, source="agents")

    def test_agent_file_unexpected_extra_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "extra.md"
        f.write_text("---\nname: extra\nversion: 2\ncustom_key: hi\n---\nBody.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "extra"
        assert agent.system_prompt == "Body."

    def test_agent_file_tools_as_list(self, tmp_path: Path) -> None:
        f = tmp_path / "list-tools.md"
        f.write_text("---\nname: list-tools\ntools:\n  - file_read\n  - shell\n---\nBody.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.tools == ["file_read", "shell"]

    def test_agent_file_empty_body(self, tmp_path: Path) -> None:
        f = tmp_path / "nobody.md"
        f.write_text("---\nname: nobody\n---\n", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.system_prompt == ""

    def test_agent_file_invalid_frontmatter_raises_with_path(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.md"
        f.write_text("---\nname: broken\nbad: [unterminated\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid frontmatter in .*broken\\.md"):
            _parse_agent_file(f, source="agents")


class TestParseCommandFile:
    """Tests for _parse_command_file with various file contents."""

    def test_full_command_file(self, tmp_path: Path) -> None:
        f = tmp_path / "debug.md"
        f.write_text(
            "---\nname: gpd:debug\ndescription: Debug command\n"
            "argument-hint: <error>\nrequires:\n  project: true\n"
            "allowed-tools:\n  - file_read\n  - shell\n---\nCommand body.",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "gpd:debug"
        assert cmd.description == "Debug command"
        assert cmd.argument_hint == "<error>"
        assert cmd.context_mode == "project-required"
        assert cmd.requires == {"project": True}
        assert cmd.allowed_tools == ["file_read", "shell"]
        assert cmd.content == "Command body."

    def test_command_file_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "bare.md"
        f.write_text("No frontmatter command.", encoding="utf-8")
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "bare"
        assert cmd.description == ""
        assert cmd.argument_hint == ""
        assert cmd.context_mode == "project-required"
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

    def test_command_parses_explicit_context_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\ncontext_mode: global\n---\nBody.", encoding="utf-8")

        cmd = _parse_command_file(f, source="commands")

        assert cmd.context_mode == "global"

    def test_command_invalid_context_mode_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\ncontext_mode: somewhere\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid context_mode"):
            _parse_command_file(f, source="commands")

    def test_command_file_invalid_frontmatter_raises_with_path(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\nbad: [unterminated\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid frontmatter in .*help\\.md"):
            _parse_command_file(f, source="commands")

    def test_command_uses_default_peer_review_contract(self, tmp_path: Path) -> None:
        f = tmp_path / "peer-review.md"
        f.write_text(
            "---\nname: gpd:peer-review\ndescription: Peer review\nrequires:\n  files: [\"paper/*.tex\"]\n---\nBody.",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, source="commands")

        assert cmd.review_contract is not None
        assert cmd.context_mode == "project-required"
        assert cmd.review_contract.review_mode == "publication"
        assert "existing manuscript" in cmd.review_contract.required_evidence
        assert cmd.review_contract.preflight_checks == [
            "project_state",
            "roadmap",
            "conventions",
            "research_artifacts",
            "manuscript",
        ]
        assert ".gpd/REFEREE-REPORT.md" in cmd.review_contract.required_outputs
        assert ".gpd/REFEREE-REPORT.tex" in cmd.review_contract.required_outputs

    def test_command_review_contract_parses_false_string_for_fresh_context(self, tmp_path: Path) -> None:
        f = tmp_path / "review-contract-false.md"
        f.write_text(
            "---\n"
            "name: gpd:review-contract-false\n"
            "review-contract:\n"
            "  review_mode: publication\n"
            '  requires_fresh_context_per_stage: "false"\n'
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        cmd = _parse_command_file(f, source="commands")

        assert cmd.review_contract is not None
        assert cmd.review_contract.requires_fresh_context_per_stage is False

    def test_command_review_contract_invalid_max_rounds_reports_file_context(self, tmp_path: Path) -> None:
        f = tmp_path / "review-rounds.md"
        f.write_text(
            "---\n"
            "name: gpd:review-rounds\n"
            "review-contract:\n"
            "  review_mode: publication\n"
            "  max_review_rounds: many\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=r"Invalid review-contract in .*review-rounds\.md.*max_review_rounds"):
            _parse_command_file(f, source="commands")


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
        f = tmp_path / "bom-agent.md"
        f.write_bytes(b"\xef\xbb\xbf---\nname: bom-test\n---\nBody.")
        agent = _parse_agent_file(f, source="agents")
        assert agent.name == "bom-test"
        assert "Body." in agent.system_prompt


class TestDiscovery:
    """Tests for discovery from the primary commands/ and agents/ directories."""

    def test_discover_agents_empty_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        assert registry._discover_agents() == {}

    def test_discover_commands_empty_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        assert registry._discover_commands() == {}

    def test_discover_agents_missing_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        assert registry._discover_agents() == {}

    def test_discover_commands_missing_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "COMMANDS_DIR", tmp_path / "nonexistent-commands")
        assert registry._discover_commands() == {}

    def test_commands_keyed_by_stem_not_frontmatter_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "my-cmd.md").write_text("---\nname: gpd:my-cmd\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        result = registry._discover_commands()
        assert "my-cmd" in result
        assert "gpd:my-cmd" not in result

    def test_command_name_mismatch_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "execute-phase.md").write_text("---\nname: gpd:plan-phase\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)

        with pytest.raises(ValueError, match="does not match file stem"):
            registry._discover_commands()

    def test_command_name_without_gpd_prefix_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "peer-review.md").write_text("---\nname: peer-review\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)

        with pytest.raises(ValueError, match=r"expected 'gpd:peer-review'"):
            registry._discover_commands()

    def test_agents_keyed_by_declared_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "alias.md").write_text("---\nname: gpd-alias\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        result = registry._discover_agents()
        assert "gpd-alias" in result
        assert "alias" not in result

    def test_duplicate_agent_names_raise(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "first.md").write_text("---\nname: gpd-duplicate\n---\nFirst prompt.", encoding="utf-8")
        (agents_dir / "second.md").write_text("---\nname: gpd-duplicate\n---\nSecond prompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)

        with pytest.raises(ValueError, match="Duplicate agent name 'gpd-duplicate'"):
            registry._discover_agents()


class TestSkillDiscovery:
    """Tests for canonical skills derived from primary commands and agents."""

    def test_skills_use_primary_commands_and_agents_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "help.md").write_text(
            "---\nname: gpd:help\ndescription: primary help\n---\nPrimary help body.",
            encoding="utf-8",
        )

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "gpd-debugger.md").write_text(
            "---\nname: gpd-debugger\ndescription: primary debugger\n---\nPrimary debugger prompt.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)

        skills = registry._discover_skills(registry._discover_commands(), registry._discover_agents())

        assert set(skills) == {"gpd-debugger", "gpd-help"}
        assert skills["gpd-help"].source_kind == "command"
        assert skills["gpd-help"].content == "Primary help body."
        assert skills["gpd-debugger"].source_kind == "agent"
        assert skills["gpd-debugger"].content == "Primary debugger prompt."

    def test_duplicate_skill_names_across_command_and_agent_raise(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "foo.md").write_text("---\nname: gpd:foo\n---\nCommand body.", encoding="utf-8")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "gpd-foo.md").write_text("---\nname: gpd-foo\n---\nAgent prompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)

        with pytest.raises(ValueError, match="Duplicate skill name 'gpd-foo'"):
            registry._discover_skills(registry._discover_commands(), registry._discover_agents())


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
        result = registry._discover_agents()
        assert list(result.keys()) == ["valid"]

    def test_non_md_files_in_commands_dir_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "valid.md").write_text("---\nname: gpd:valid\n---\nBody.", encoding="utf-8")
        (commands_dir / "readme.txt").write_text("Not a command.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        result = registry._discover_commands()
        assert list(result.keys()) == ["valid"]


class TestRegistryCache:
    """Tests for _RegistryCache lazy-load and invalidation."""

    def test_lazy_load_agents(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "cached.md").write_text("---\nname: cached\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)

        cache = _RegistryCache()
        assert cache._agents is None
        agents = cache.agents()
        assert "cached" in agents
        assert cache._agents is not None

    def test_lazy_load_commands(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "cached.md").write_text("---\nname: gpd:cached\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)

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

        cache = _RegistryCache()
        first = cache.agents()
        second = cache.agents()
        assert first is second

    def test_invalidate_clears_all_caches(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "x.md").write_text("---\nname: x\n---\nPrompt.", encoding="utf-8")

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "y.md").write_text("---\nname: gpd:y\n---\nBody.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)

        cache = _RegistryCache()
        cache.agents()
        cache.commands()
        cache.skills()
        assert cache._agents is not None
        assert cache._commands is not None
        assert cache._skills is not None

        cache.invalidate()
        assert cache._agents is None
        assert cache._commands is None
        assert cache._skills is None

    def test_invalidate_forces_re_discovery(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "first.md").write_text("---\nname: first\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)

        cache = _RegistryCache()
        result1 = cache.agents()
        assert "first" in result1

        (agents_dir / "second.md").write_text("---\nname: second\n---\nPrompt2.", encoding="utf-8")
        cache.invalidate()

        result2 = cache.agents()
        assert "first" in result2
        assert "second" in result2
        assert result1 is not result2


class TestPublicAPI:
    """Tests for the module-level public API functions."""

    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        """Ensure registry cache is invalidated before and after each test."""
        from gpd import registry
        registry.invalidate_cache()
        yield
        registry.invalidate_cache()

    def test_get_agent_not_found_raises_key_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        with pytest.raises(KeyError, match="Agent not found: nonexistent"):
            registry.get_agent("nonexistent")

    def test_get_command_not_found_raises_key_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "COMMANDS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        with pytest.raises(KeyError, match="Command not found: nonexistent"):
            registry.get_command("nonexistent")

    def test_get_skill_not_found_raises_key_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(registry, "COMMANDS_DIR", tmp_path / "nonexistent")
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent")
        registry.invalidate_cache()

        with pytest.raises(KeyError, match="Skill not found: nonexistent"):
            registry.get_skill("nonexistent")

    def test_list_agents_returns_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "charlie.md").write_text("---\nname: charlie\n---\nC.", encoding="utf-8")
        (agents_dir / "alpha.md").write_text("---\nname: alpha\n---\nA.", encoding="utf-8")
        (agents_dir / "bravo.md").write_text("---\nname: bravo\n---\nB.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        assert registry.list_agents() == ["alpha", "bravo", "charlie"]

    def test_load_agents_from_dir_parses_arbitrary_agent_directory(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "gpd-public.md").write_text(
            "---\nname: gpd-public\ndescription: Public\ntools: file_read\nsurface: public\n---\nPublic prompt.",
            encoding="utf-8",
        )
        (agents_dir / "gpd-internal.md").write_text(
            "---\nname: gpd-internal\ndescription: Internal\ntools: file_read\nsurface: internal\n---\nInternal prompt.",
            encoding="utf-8",
        )

        agents = load_agents_from_dir(agents_dir)

        assert sorted(agents) == ["gpd-internal", "gpd-public"]
        assert agents["gpd-public"].surface == "public"
        assert agents["gpd-internal"].surface == "internal"

    def test_list_commands_returns_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "zebra.md").write_text("---\nname: gpd:zebra\n---\nZ.", encoding="utf-8")
        (commands_dir / "apple.md").write_text("---\nname: gpd:apple\n---\nA.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        registry.invalidate_cache()

        assert registry.list_commands() == ["apple", "zebra"]

    def test_list_skills_returns_sorted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "plan-phase.md").write_text("---\nname: gpd:plan-phase\n---\nPlan.", encoding="utf-8")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "gpd-debugger.md").write_text("---\nname: gpd-debugger\n---\nDebug.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        assert registry.list_skills() == ["gpd-debugger", "gpd-plan-phase"]

    def test_list_review_commands_returns_only_review_commands(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "peer-review.md").write_text(
            "---\nname: gpd:peer-review\ndescription: Peer review\n---\nReview body.",
            encoding="utf-8",
        )
        (commands_dir / "debug.md").write_text(
            "---\nname: gpd:debug\ndescription: Debug\n---\nDebug body.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        registry.invalidate_cache()

        assert registry.list_review_commands() == ["gpd:peer-review"]

    def test_get_agent_returns_correct_def(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text(
            "---\nname: test-agent\ndescription: Tested\ntools: file_read\nsurface: public\n"
            "role_family: coordination\nartifact_write_authority: scoped_write\n"
            "shared_state_authority: direct\ncolor: red\n---\nTest prompt.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        agent = registry.get_agent("test-agent")
        assert isinstance(agent, AgentDef)
        assert agent.name == "test-agent"
        assert agent.description == "Tested"
        assert agent.tools == ["file_read"]
        assert agent.surface == "public"
        assert agent.role_family == "coordination"
        assert agent.artifact_write_authority == "scoped_write"
        assert agent.shared_state_authority == "direct"

    def test_get_command_returns_correct_def(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "test-cmd.md").write_text(
            "---\nname: gpd:test-cmd\ndescription: Tested\n---\nCmd body.", encoding="utf-8"
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        registry.invalidate_cache()

        cmd = registry.get_command("test-cmd")
        assert isinstance(cmd, CommandDef)
        assert cmd.name == "gpd:test-cmd"
        assert cmd.description == "Tested"

    def test_get_command_accepts_public_command_label(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "peer-review.md").write_text(
            "---\nname: gpd:peer-review\ndescription: Peer review\n---\nReview body.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        registry.invalidate_cache()

        cmd = registry.get_command("/gpd:peer-review")

        assert isinstance(cmd, CommandDef)
        assert cmd.name == "gpd:peer-review"
        assert cmd.description == "Peer review"

    def test_get_skill_returns_correct_def(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "execute-phase.md").write_text(
            "---\nname: gpd:execute-phase\ndescription: Execute\n---\nExecute body.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        registry.invalidate_cache()

        skill = registry.get_skill("gpd:execute-phase")
        assert isinstance(skill, SkillDef)
        assert skill.name == "gpd-execute-phase"
        assert skill.registry_name == "execute-phase"
        assert skill.source_kind == "command"
        assert skill.content == "Execute body."

    def test_get_skill_accepts_registry_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "execute-phase.md").write_text(
            "---\nname: gpd:execute-phase\ndescription: Execute\n---\nExecute body.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        registry.invalidate_cache()

        skill = registry.get_skill("execute-phase")

        assert isinstance(skill, SkillDef)
        assert skill.name == "gpd-execute-phase"
        assert skill.registry_name == "execute-phase"

    def test_get_skill_accepts_public_command_label(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "execute-phase.md").write_text(
            "---\nname: gpd:execute-phase\ndescription: Execute\n---\nExecute body.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        registry.invalidate_cache()

        skill = registry.get_skill("/gpd:execute-phase")

        assert isinstance(skill, SkillDef)
        assert skill.name == "gpd-execute-phase"
        assert skill.registry_name == "execute-phase"

    def test_real_slides_command_metadata(self) -> None:
        registry.invalidate_cache()

        cmd = registry.get_command("slides")

        assert cmd.name == "gpd:slides"
        assert cmd.argument_hint == "[topic, talk title, audience, or source path]"
        assert cmd.context_mode == "projectless"
        assert cmd.allowed_tools == [
            "file_read",
            "file_write",
            "file_edit",
            "shell",
            "search_files",
            "find_files",
            "ask_user",
        ]

    def test_real_slides_skill_uses_output_category(self) -> None:
        registry.invalidate_cache()

        skill = registry.get_skill("gpd-slides")

        assert skill.name == "gpd-slides"
        assert skill.category == "output"

    def test_invalidate_cache_module_level(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        assert registry.list_agents() == []

        (agents_dir / "new.md").write_text("---\nname: new\n---\nPrompt.", encoding="utf-8")
        registry.invalidate_cache()

        assert registry.list_agents() == ["new"]


class TestDataclasses:
    """Tests for AgentDef, CommandDef, and SkillDef dataclass properties."""

    def test_agent_def_frozen(self) -> None:
        agent = AgentDef(
            name="a",
            description="d",
            system_prompt="s",
            tools=[],
            commit_authority="orchestrator",
            color="",
            path="/p",
            source="agents",
        )
        with pytest.raises(AttributeError):
            agent.name = "b"  # type: ignore[misc]

    def test_command_def_frozen(self) -> None:
        cmd = CommandDef(
            name="c",
            description="d",
            argument_hint="",
            context_mode="project-required",
            requires={},
            allowed_tools=[],
            content="",
            path="/p",
            source="commands",
        )
        with pytest.raises(AttributeError):
            cmd.name = "x"  # type: ignore[misc]

    def test_agent_def_slots(self) -> None:
        agent = AgentDef(
            name="a",
            description="d",
            system_prompt="s",
            tools=[],
            commit_authority="orchestrator",
            color="",
            path="/p",
            source="agents",
        )
        with pytest.raises((AttributeError, TypeError)):
            agent.new_attr = "nope"  # type: ignore[misc]

    def test_command_def_slots(self) -> None:
        cmd = CommandDef(
            name="c",
            description="d",
            argument_hint="",
            context_mode="project-required",
            requires={},
            allowed_tools=[],
            content="",
            path="/p",
            source="commands",
        )
        with pytest.raises((AttributeError, TypeError)):
            cmd.new_attr = "nope"  # type: ignore[misc]

    def test_skill_def_frozen(self) -> None:
        skill = SkillDef(
            name="gpd-test",
            description="d",
            content="body",
            category="other",
            path="/p",
            source_kind="command",
            registry_name="test",
        )
        with pytest.raises(AttributeError):
            skill.name = "gpd-other"  # type: ignore[misc]

    def test_skill_def_slots(self) -> None:
        skill = SkillDef(
            name="gpd-test",
            description="d",
            content="body",
            category="other",
            path="/p",
            source_kind="command",
            registry_name="test",
        )
        with pytest.raises((AttributeError, TypeError)):
            skill.new_attr = "nope"  # type: ignore[misc]


class TestSkillCategoryMap:
    """Tests for _SKILL_CATEGORY_MAP integrity."""

    def test_no_duplicate_keys_in_skill_category_map(self) -> None:
        """Verify _SKILL_CATEGORY_MAP has no duplicate keys (Python silently keeps last).

        We parse the source to detect duplicates that the dict literal would hide.
        """
        import ast
        import inspect


        source = inspect.getsource(registry)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "_SKILL_CATEGORY_MAP":
                assert isinstance(node.value, ast.Dict)
                keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
                duplicates = [k for k in keys if keys.count(k) > 1]
                assert duplicates == [], f"Duplicate keys in _SKILL_CATEGORY_MAP: {set(duplicates)}"
                break
        else:
            pytest.fail("_SKILL_CATEGORY_MAP not found in registry source")

    def test_peer_review_appears_exactly_once(self) -> None:
        """Regression: 'gpd-peer-review' was duplicated at two positions."""
        import ast
        import inspect

        source = inspect.getsource(registry)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "_SKILL_CATEGORY_MAP":
                assert isinstance(node.value, ast.Dict)
                keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
                assert keys.count("gpd-peer-review") == 1
                break

    def test_infer_skill_category_peer_review(self) -> None:
        from gpd.registry import _infer_skill_category

        assert _infer_skill_category("gpd-peer-review") == "paper"
