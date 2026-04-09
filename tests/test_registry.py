"""Tests for gpd/registry.py — content registry edge cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd import registry
from gpd.core.model_visible_text import (
    agent_visibility_note,
    command_visibility_note,
    review_contract_visibility_note,
    skeptical_rigor_guardrails_section,
)
from gpd.core.workflow_staging import WorkflowStageManifest
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
    render_command_visibility_sections_from_frontmatter,
)
from gpd.specs import SPECS_DIR as CANONICAL_SPECS_DIR

NEW_PROJECT_COMMAND_PATH = Path(__file__).resolve().parents[1] / "src" / "gpd" / "commands" / "new-project.md"
RESEARCH_SYNTHESIZER_SUMMARY_CONTRACT = {
    "write_scope": {"mode": "scoped_write", "allowed_paths": ["GPD/literature/SUMMARY.md"]},
    "expected_artifacts": ["GPD/literature/SUMMARY.md"],
    "shared_state_policy": "return_only",
}


def _write_review_contract_command(tmp_path: Path, file_name: str, review_contract_body: str) -> Path:
    """Write a minimal command file with a configurable review-contract body."""
    path = tmp_path / file_name
    path.write_text(
        "---\n"
        "name: gpd:test-review-contract\n"
        "review-contract:\n"
        "  review_mode: publication\n"
        "  schema_version: 1\n"
        f"{review_contract_body}"
        "---\n"
        "Body.",
        encoding="utf-8",
    )
    return path


class TestParseFrontmatter:
    """Tests for _parse_frontmatter edge cases."""

    def test_registry_exports_canonical_specs_dir(self) -> None:
        assert registry.SPECS_DIR == CANONICAL_SPECS_DIR

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

    def test_model_visible_wrapper_notes_use_concise_yaml_prefixes(self) -> None:
        assert agent_visibility_note().startswith("Agent YAML rules. Use this YAML.")
        assert command_visibility_note().startswith("Command YAML rules. Use this YAML.")
        assert review_contract_visibility_note().startswith("Review-contract YAML rules. Use this YAML.")

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

    def test_frontmatter_rejects_duplicate_keys(self) -> None:
        text = "---\nname: test\nname: duplicate\n---\nBody."

        with pytest.raises(ValueError, match="duplicate key"):
            _parse_frontmatter(text)

    def test_frontmatter_uses_shared_strict_yaml_loader(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, str] = {}

        def _fake_load_strict_yaml(content: str) -> object:
            seen["content"] = content
            return {"name": "test"}

        monkeypatch.setattr(registry, "load_strict_yaml", _fake_load_strict_yaml)

        meta, body = _parse_frontmatter("---\nname: test\n---\nBody.")

        assert seen["content"] == "name: test\n"
        assert meta == {"name": "test"}
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

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="tools must not contain blank entries"):
            _parse_tools("")

    def test_none_returns_empty(self) -> None:
        assert _parse_tools(None) == []

    def test_invalid_scalar_raises(self) -> None:
        with pytest.raises(ValueError, match="tools must be a string or list of strings"):
            _parse_tools(42)

    def test_list_with_non_string_elements_raises(self) -> None:
        with pytest.raises(ValueError, match="tools must contain only strings"):
            _parse_tools([1, True, "shell"])

    def test_string_with_extra_whitespace(self) -> None:
        assert _parse_tools("  file_read , file_write  ") == ["file_read", "file_write"]

    def test_string_with_blank_member_raises(self) -> None:
        with pytest.raises(ValueError, match="tools must not contain blank entries"):
            _parse_tools("file_read, ,file_write")


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
        assert agent.system_prompt.startswith("## Agent Requirements\n")
        assert "Agent YAML rules. Use this YAML." in agent.system_prompt
        assert "Closed schema; no extra keys." in agent.system_prompt
        assert agent_visibility_note() in agent.system_prompt
        assert "commit_authority: orchestrator" in agent.system_prompt
        assert "surface: public" in agent.system_prompt
        assert "role_family: worker" in agent.system_prompt
        assert "artifact_write_authority: scoped_write" in agent.system_prompt
        assert "shared_state_authority: direct" in agent.system_prompt
        assert "tools:\n- file_read\n- file_write" in agent.system_prompt
        assert skeptical_rigor_guardrails_section() in agent.system_prompt
        assert agent.system_prompt.endswith("System prompt.")
        assert agent.source == "agents"

    def test_agent_file_no_frontmatter_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bare-agent.md"
        f.write_text("Just a body, no frontmatter.", encoding="utf-8")

        with pytest.raises(ValueError, match="name for bare-agent must be a non-empty string"):
            _parse_agent_file(f, source="agents")

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
        assert agent.system_prompt.startswith("## Agent Requirements\n")
        assert skeptical_rigor_guardrails_section() in agent.system_prompt
        assert agent.system_prompt.endswith("Prompt.")

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

        with pytest.raises(ValueError, match=r"unknown frontmatter keys for extra: custom_key, version"):
            _parse_agent_file(f, source="agents")

    def test_agent_file_tools_as_list(self, tmp_path: Path) -> None:
        f = tmp_path / "list-tools.md"
        f.write_text("---\nname: list-tools\ntools:\n  - file_read\n  - shell\n---\nBody.", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.tools == ["file_read", "shell"]

    def test_agent_file_allowed_tools_alias_merges_into_tools(self, tmp_path: Path) -> None:
        f = tmp_path / "aliased-tools.md"
        f.write_text(
            "---\nname: aliased-tools\ntools: shell\nallowed-tools:\n  - file_read\n  - shell\n---\nBody.",
            encoding="utf-8",
        )

        agent = _parse_agent_file(f, source="agents")

        assert agent.tools == ["shell", "file_read"]

    def test_agent_file_invalid_tools_scalar_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools-scalar.md"
        f.write_text("---\nname: bad-agent\ntools: 7\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="tools for bad-agent must be a string or list of strings"):
            _parse_agent_file(f, source="agents")

    def test_agent_file_tools_list_rejects_non_string_members(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools-list.md"
        f.write_text("---\nname: bad-agent\ntools:\n  - file_read\n  - true\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="tools for bad-agent must contain only strings"):
            _parse_agent_file(f, source="agents")

    def test_agent_file_tools_list_rejects_blank_members(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools-list-blank.md"
        f.write_text("---\nname: bad-agent\ntools:\n  - file_read\n  - \"  \"\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="tools for bad-agent must not contain blank entries"):
            _parse_agent_file(f, source="agents")

    def test_agent_file_allowed_tools_list_rejects_blank_members(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-allowed-tools-list-blank.md"
        f.write_text("---\nname: bad-agent\nallowed-tools:\n  - file_read\n  - \"\"\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="allowed-tools for bad-agent must not contain blank entries"):
            _parse_agent_file(f, source="agents")

    def test_agent_file_blank_commit_authority_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "blank-authority.md"
        f.write_text("---\nname: bad\ncommit_authority: \"  \"\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match="commit_authority for bad must be a non-empty string"):
            _parse_agent_file(f, source="agents")

    def test_agent_file_null_commit_authority_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "null-authority.md"
        f.write_text("---\nname: bad\ncommit_authority:\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match="commit_authority for null-authority must be a non-empty string"):
            _parse_agent_file(f, source="agents")

    @pytest.mark.parametrize(
        ("field_name", "expected_error"),
        [
            ("surface", "surface for bad must be a non-empty string"),
            ("role_family", "role_family for bad must be a non-empty string"),
            ("artifact_write_authority", "artifact_write_authority for bad must be a non-empty string"),
            ("shared_state_authority", "shared_state_authority for bad must be a non-empty string"),
        ],
    )
    def test_agent_file_blank_spawn_metadata_raises(
        self,
        tmp_path: Path,
        field_name: str,
        expected_error: str,
    ) -> None:
        f = tmp_path / "bad-metadata-blank.md"
        f.write_text(f"---\nname: bad\n{field_name}: \"  \"\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match=expected_error):
            _parse_agent_file(f, source="agents")

    def test_agent_file_empty_body(self, tmp_path: Path) -> None:
        f = tmp_path / "nobody.md"
        f.write_text("---\nname: nobody\n---\n", encoding="utf-8")
        agent = _parse_agent_file(f, source="agents")
        assert agent.system_prompt.startswith("## Agent Requirements\n")
        assert "Agent YAML rules. Use this YAML." in agent.system_prompt
        assert "commit_authority:" in agent.system_prompt
        assert skeptical_rigor_guardrails_section() in agent.system_prompt
        assert agent.system_prompt.rstrip().endswith("disconfirming check still needed.")

    def test_agent_file_invalid_frontmatter_raises_with_path(self, tmp_path: Path) -> None:
        f = tmp_path / "broken.md"
        f.write_text("---\nname: broken\nbad: [unterminated\n---\nPrompt.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid frontmatter in .*broken\\.md"):
            _parse_agent_file(f, source="agents")

    @pytest.mark.parametrize(
        ("frontmatter_line", "expected_error"),
        [
            ("name: 7", r"name for bad-agent must be a string"),
            ("description: true", r"description for bad-agent must be a string"),
            ("color: 3", r"color for bad-agent must be a string"),
        ],
    )
    def test_agent_file_rejects_non_string_scalar_frontmatter(
        self, tmp_path: Path, frontmatter_line: str, expected_error: str
    ) -> None:
        f = tmp_path / "bad-agent.md"
        if frontmatter_line.startswith("name:"):
            f.write_text(
                f"---\n{frontmatter_line}\n---\nPrompt.",
                encoding="utf-8",
            )
        else:
            f.write_text(
                f"---\nname: bad-agent\n{frontmatter_line}\n---\nPrompt.",
                encoding="utf-8",
            )

        with pytest.raises(ValueError, match=expected_error):
            _parse_agent_file(f, source="agents")


class TestParseCommandFile:
    """Tests for _parse_command_file with various file contents."""

    def test_full_command_file(self, tmp_path: Path) -> None:
        f = tmp_path / "debug.md"
        f.write_text(
            "---\nname: gpd:debug\ndescription: Debug command\n"
            "argument-hint: <error>\nrequires:\n  files:\n    - GPD/ROADMAP.md\n"
            "allowed-tools:\n  - file_read\n  - shell\n---\nCommand body.",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "gpd:debug"
        assert cmd.description == "Debug command"
        assert cmd.argument_hint == "<error>"
        assert cmd.context_mode == "project-required"
        assert cmd.project_reentry_capable is False
        assert cmd.requires == {"files": ["GPD/ROADMAP.md"]}
        assert cmd.allowed_tools == ["file_read", "shell"]
        assert cmd.content.startswith("## Command Requirements\n\n")
        assert "Closed schema; no extra keys." in cmd.content
        assert "Strict booleans only." in cmd.content
        assert command_visibility_note() in cmd.content
        assert "GPD/ROADMAP.md" in cmd.content
        assert skeptical_rigor_guardrails_section() in cmd.content
        assert cmd.content.endswith("Command body.")

    def test_command_file_with_requires_and_review_contract_renders_requirements_first(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "review.md"
        f.write_text(
            "---\n"
            "name: gpd:review\n"
            "description: Review command\n"
            "argument-hint: <phase>\n"
            "requires:\n"
            "  files:\n"
            "    - GPD/ROADMAP.md\n"
            "review-contract:\n"
            "  review_mode: review\n"
            "  schema_version: 1\n"
            "  required_outputs:\n"
            "    - GPD/review/REPORT.md\n"
            "  required_evidence:\n"
            "    - phase artifacts\n"
            "  preflight_checks:\n"
            "    - project_state\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        cmd = _parse_command_file(f, source="commands")

        assert cmd.content.startswith("## Command Requirements\n\n")
        assert "Closed schema; no extra keys." in cmd.content
        assert "Strict booleans only." in cmd.content
        assert cmd.content.index("## Review Contract") > cmd.content.index("## Command Requirements")
        assert cmd.content.endswith("Body.")

    def test_command_file_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "bare.md"
        f.write_text("No frontmatter command.", encoding="utf-8")
        cmd = _parse_command_file(f, source="commands")
        assert cmd.name == "bare"
        assert cmd.description == ""
        assert cmd.argument_hint == ""
        assert cmd.context_mode == "project-required"
        assert cmd.project_reentry_capable is False
        assert cmd.requires == {}
        assert cmd.allowed_tools == []

    def test_command_requires_non_dict_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-requires.md"
        f.write_text("---\nname: bad\nrequires: not-a-dict\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="requires for bad must be a mapping"):
            _parse_command_file(f, source="commands")

    def test_command_requires_files_rejects_non_string_members(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-requires-files-members.md"
        f.write_text(
            "---\nname: bad\nrequires:\n  files:\n    - GPD/ROADMAP.md\n    - true\n---\nBody.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="files for bad must contain only strings"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize("field_name", ["state", "recommended"])
    def test_command_requires_rejects_unknown_keys(self, tmp_path: Path, field_name: str) -> None:
        f = tmp_path / f"bad-requires-{field_name}.md"
        f.write_text(
            f"---\nname: bad\nrequires:\n  {field_name}: phase_planned\n---\nBody.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=rf"requires for bad only supports files; got {field_name}"):
            _parse_command_file(f, source="commands")

    def test_command_allowed_tools_non_list_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools.md"
        f.write_text("---\nname: bad\nallowed-tools: just-a-string\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="allowed-tools for bad must be a list of strings"):
            _parse_command_file(f, source="commands")

    def test_command_allowed_tools_list_rejects_non_string_members(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools-members.md"
        f.write_text("---\nname: bad\nallowed-tools:\n  - file_read\n  - true\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="allowed-tools for bad must contain only strings"):
            _parse_command_file(f, source="commands")

    def test_command_allowed_tools_list_rejects_blank_members(self, tmp_path: Path) -> None:
        f = tmp_path / "bad-tools-members-blank.md"
        f.write_text("---\nname: bad\nallowed-tools:\n  - file_read\n  - \"\"\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="allowed-tools for bad must not contain blank entries"):
            _parse_command_file(f, source="commands")

    def test_command_unexpected_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "extra.md"
        f.write_text("---\nname: extra\nversion: 99\nfoo: bar\n---\nBody.", encoding="utf-8")
        with pytest.raises(ValueError, match=r"unknown frontmatter keys for extra: foo, version"):
            _parse_command_file(f, source="commands")

    def test_render_command_visibility_sections_rejects_unknown_frontmatter_keys(self) -> None:
        with pytest.raises(ValueError, match=r"unknown frontmatter keys for gpd:test: foo"):
            render_command_visibility_sections_from_frontmatter(
                "name: gpd:test\nfoo: bar\n",
                command_name="gpd:test",
            )

    def test_render_command_visibility_sections_include_agent_metadata(self) -> None:
        rendered = render_command_visibility_sections_from_frontmatter(
            "name: gpd:plan-phase\nagent: gpd-planner\n",
            command_name="gpd:plan-phase",
        )

        assert "agent: gpd-planner" in rendered
        assert "context_mode: project-required" in rendered

    def test_render_command_visibility_sections_comment_only_frontmatter_keeps_default_constraints(self) -> None:
        rendered = render_command_visibility_sections_from_frontmatter(
            "# comment only\n",
            command_name="gpd:test",
        )

        assert "## Command Requirements" in rendered
        assert "context_mode: project-required" in rendered
        assert "project_reentry_capable: false" in rendered

    def test_command_agent_frontmatter_key_is_explicitly_allowed(self, tmp_path: Path) -> None:
        f = tmp_path / "plan-phase.md"
        f.write_text("---\nname: gpd:plan-phase\nagent: gpd-planner\n---\nBody.", encoding="utf-8")

        cmd = _parse_command_file(f, source="commands")

        assert cmd.name == "gpd:plan-phase"
        assert cmd.agent == "gpd-planner"
        assert "agent: gpd-planner" in cmd.content
        assert cmd.content.endswith("Body.")

    def test_command_agent_validation_uses_canonical_inventory_not_patched_agents_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patched_agents_dir = tmp_path / "agents"
        patched_agents_dir.mkdir()
        monkeypatch.setattr(registry, "AGENTS_DIR", patched_agents_dir)
        registry.invalidate_cache()

        f = tmp_path / "plan-phase.md"
        f.write_text("---\nname: gpd:plan-phase\nagent: gpd-planner\n---\nBody.", encoding="utf-8")

        cmd = _parse_command_file(f, source="commands")

        assert cmd.agent == "gpd-planner"

    def test_command_parses_explicit_context_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\ncontext_mode: global\n---\nBody.", encoding="utf-8")

        cmd = _parse_command_file(f, source="commands")

        assert cmd.context_mode == "global"

    def test_command_parses_project_reentry_capable_for_project_required_commands(self, tmp_path: Path) -> None:
        f = tmp_path / "resume-work.md"
        f.write_text(
            "---\n"
            "name: gpd:resume-work\n"
            "context_mode: project-required\n"
            "project_reentry_capable: true\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        cmd = _parse_command_file(f, source="commands")

        assert cmd.context_mode == "project-required"
        assert cmd.project_reentry_capable is True


    def test_new_project_command_source_uses_narrow_contract_schema_without_include_markers(self) -> None:
        command_text = NEW_PROJECT_COMMAND_PATH.read_text(encoding="utf-8")

        assert "project-contract-schema.md" in command_text
        assert "project-contract-grounding-linkage.md" in command_text
        assert "staged_loading" not in command_text
        assert "new-project-stage-manifest.json" not in command_text
        assert "<!-- [included:" not in command_text
        assert "<!-- [end included] -->" not in command_text

    def test_new_project_command_source_stays_prompt_budget_thin(self) -> None:
        command_text = NEW_PROJECT_COMMAND_PATH.read_text(encoding="utf-8")

        assert "staged_loading" not in command_text
        assert "new-project-stage-manifest.json" not in command_text
        assert "conditional_authorities" not in command_text

    def test_command_project_reentry_capable_rejects_non_boolean_values(self, tmp_path: Path) -> None:
        f = tmp_path / "resume-work.md"
        f.write_text(
            "---\n"
            "name: gpd:resume-work\n"
            "project_reentry_capable: maybe\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="project_reentry_capable for gpd:resume-work must be a boolean"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize("raw_value", ['"true"', '"false"', "1", "0", "yes", "no"])
    def test_command_project_reentry_capable_rejects_legacy_boolean_aliases(
        self,
        tmp_path: Path,
        raw_value: str,
    ) -> None:
        f = tmp_path / "resume-work.md"
        f.write_text(
            "---\n"
            "name: gpd:resume-work\n"
            f"project_reentry_capable: {raw_value}\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="project_reentry_capable for gpd:resume-work must be a boolean"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize(("raw_value", "expected"), [("True", True), ("FALSE", False)])
    def test_command_project_reentry_capable_accepts_yaml_boolean_case_variants(
        self,
        tmp_path: Path,
        raw_value: str,
        expected: bool,
    ) -> None:
        f = tmp_path / "resume-work.md"
        f.write_text(
            "---\n"
            "name: gpd:resume-work\n"
            "context_mode: project-required\n"
            f"project_reentry_capable: {raw_value}\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        cmd = _parse_command_file(f, source="commands")

        assert cmd.project_reentry_capable is expected

    @pytest.mark.parametrize("frontmatter_line", ["project_reentry_capable:", "project_reentry_capable: null"])
    def test_command_project_reentry_capable_rejects_explicitly_empty_values(
        self,
        tmp_path: Path,
        frontmatter_line: str,
    ) -> None:
        f = tmp_path / "resume-work.md"
        f.write_text(
            "---\n"
            "name: gpd:resume-work\n"
            f"{frontmatter_line}\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="project_reentry_capable for gpd:resume-work must be a boolean"):
            _parse_command_file(f, source="commands")

    def test_command_project_reentry_capable_requires_project_required_context_mode(self, tmp_path: Path) -> None:
        f = tmp_path / "start.md"
        f.write_text(
            "---\n"
            "name: gpd:start\n"
            "context_mode: projectless\n"
            "project_reentry_capable: true\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(
            ValueError,
            match="project_reentry_capable for gpd:start requires context_mode 'project-required'",
        ):
            _parse_command_file(f, source="commands")

    def test_command_invalid_context_mode_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\ncontext_mode: somewhere\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid context_mode"):
            _parse_command_file(f, source="commands")

    def test_command_blank_context_mode_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\ncontext_mode: \"  \"\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="context_mode for gpd:help must be a non-empty string"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize("frontmatter_line", ["context_mode:", "context_mode: null"])
    def test_command_explicitly_empty_context_mode_raises(self, tmp_path: Path, frontmatter_line: str) -> None:
        f = tmp_path / "help.md"
        f.write_text(f"---\nname: gpd:help\n{frontmatter_line}\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="context_mode for gpd:help must be a non-empty string"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize("frontmatter_line", ["agent:", "agent: null"])
    def test_command_explicitly_empty_agent_raises(self, tmp_path: Path, frontmatter_line: str) -> None:
        f = tmp_path / "plan-phase.md"
        f.write_text(f"---\nname: gpd:plan-phase\n{frontmatter_line}\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="agent for gpd:plan-phase must be a non-empty string"):
            _parse_command_file(f, source="commands")

    def test_command_unknown_agent_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "plan-phase.md"
        f.write_text("---\nname: gpd:plan-phase\nagent: gpd-not-real\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match=r"Unknown agent 'gpd-not-real' for gpd:plan-phase"):
            _parse_command_file(f, source="commands")

    def test_command_builtin_agent_survives_monkeypatched_agent_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        f = tmp_path / "plan-phase.md"
        f.write_text("---\nname: gpd:plan-phase\nagent: gpd-planner\n---\nBody.", encoding="utf-8")

        patched_agents_dir = tmp_path / "agents"
        patched_agents_dir.mkdir()
        (patched_agents_dir / "gpd-debugger.md").write_text(
            "---\nname: gpd-debugger\ndescription: Debugger\n---\nPrompt.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "AGENTS_DIR", patched_agents_dir)
        registry.invalidate_cache()

        cmd = _parse_command_file(f, source="commands")

        assert cmd.agent == "gpd-planner"

    def test_command_file_invalid_frontmatter_raises_with_path(self, tmp_path: Path) -> None:
        f = tmp_path / "help.md"
        f.write_text("---\nname: gpd:help\nbad: [unterminated\n---\nBody.", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid frontmatter in .*help\\.md"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize(
        ("frontmatter_line", "expected_error"),
        [
            ("name: 9", r"name for help must be a string"),
            ("description: true", r"description for gpd:help must be a string"),
            ("argument-hint: 5", r"argument-hint for gpd:help must be a string"),
        ],
    )
    def test_command_file_rejects_non_string_scalar_frontmatter(
        self, tmp_path: Path, frontmatter_line: str, expected_error: str
    ) -> None:
        f = tmp_path / "help.md"
        if frontmatter_line.startswith("name:"):
            f.write_text(
                f"---\n{frontmatter_line}\n---\nBody.",
                encoding="utf-8",
            )
        else:
            f.write_text(
                f"---\nname: gpd:help\n{frontmatter_line}\n---\nBody.",
                encoding="utf-8",
            )

        with pytest.raises(ValueError, match=expected_error):
            _parse_command_file(f, source="commands")

    def test_command_without_review_contract_has_no_hidden_default_contract(self, tmp_path: Path) -> None:
        f = tmp_path / "peer-review.md"
        f.write_text(
            "---\nname: gpd:peer-review\ndescription: Peer review\nrequires:\n  files: [\"paper/*.tex\"]\n---\nBody.",
            encoding="utf-8",
        )
        cmd = _parse_command_file(f, source="commands")

        assert cmd.review_contract is None
        assert cmd.context_mode == "project-required"
        assert cmd.project_reentry_capable is False

    @pytest.mark.parametrize(
        "field_name",
        [
            "required_outputs",
            "required_evidence",
            "blocking_conditions",
            "preflight_checks",
            "stage_artifacts",
        ],
    )
    def test_command_review_contract_list_fields_reject_non_string_members(
        self, tmp_path: Path, field_name: str
    ) -> None:
        f = _write_review_contract_command(
            tmp_path,
            f"{field_name}-non-string-member.md",
            f"  {field_name}:\n"
            "    - valid\n"
            "    - true\n",
        )

        with pytest.raises(ValueError, match=rf"Invalid review-contract in .*{field_name}-non-string-member\.md.*{field_name}"):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize(
        "field_name",
        [
            "required_outputs",
            "required_evidence",
            "blocking_conditions",
            "preflight_checks",
            "stage_artifacts",
        ],
    )
    def test_command_review_contract_list_fields_reject_invalid_scalar_values(
        self, tmp_path: Path, field_name: str
    ) -> None:
        f = _write_review_contract_command(
            tmp_path,
            f"{field_name}-invalid-scalar.md",
            f"  {field_name}: 7\n",
        )

        with pytest.raises(ValueError, match=rf"Invalid review-contract in .*{field_name}-invalid-scalar\.md.*{field_name}"):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_list_fields_reject_singleton_string_scalars(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "singleton-string-list-fields.md",
            "  required_outputs: GPD/output.md\n"
            "  preflight_checks:\n"
            "    - manuscript\n"
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_outputs:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*singleton-string-list-fields\.md.*required_outputs must be a list of strings",
        ):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize(
        "field_name",
        [
            "required_outputs",
            "required_evidence",
            "blocking_conditions",
            "preflight_checks",
            "stage_artifacts",
        ],
    )
    def test_command_review_contract_list_fields_reject_blank_members(self, tmp_path: Path, field_name: str) -> None:
        f = _write_review_contract_command(
            tmp_path,
            f"{field_name}-blank-member.md",
            f"  {field_name}:\n"
            "    - valid\n"
            '    - "   "\n',
        )

        with pytest.raises(
            ValueError,
            match=rf"Invalid review-contract in .*{field_name}-blank-member\.md.*{field_name}",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_list_fields_reject_singleton_string_scalars(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "singleton-list-scalars.md",
            "  required_outputs:\n"
            "    - GPD/REFEREE-REPORT{round_suffix}.md\n"
            "  preflight_checks:\n"
            "    - manuscript\n"
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_outputs: GPD/review/PROOF-REDTEAM{round_suffix}.md\n",
        )

        with pytest.raises(
            ValueError,
            match=(
                r"Invalid review-contract in .*singleton-list-scalars\.md.*"
                r"conditional_requirements\[0\]\.required_outputs must be a list of strings"
            ),
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_parses_conditional_requirements(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements.md",
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_outputs:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n"
            "      stage_artifacts:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n",
        )

        cmd = _parse_command_file(f, source="commands")

        assert cmd.review_contract is not None
        assert len(cmd.review_contract.conditional_requirements) == 1
        requirement = cmd.review_contract.conditional_requirements[0]
        assert requirement.when == "theorem-bearing claims are present"
        assert requirement.required_outputs == ["GPD/review/PROOF-REDTEAM{round_suffix}.md"]
        assert requirement.required_evidence == []
        assert requirement.blocking_conditions == []
        assert requirement.stage_artifacts == ["GPD/review/PROOF-REDTEAM{round_suffix}.md"]

    def test_command_review_contract_rejects_duplicate_conditional_requirement_when(
        self, tmp_path: Path
    ) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "duplicate-conditional-requirements.md",
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_outputs:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_evidence:\n"
            "        - duplicate activation clause\n",
        )

        with pytest.raises(
            ValueError,
            match=(
                r"Invalid review-contract in .*duplicate-conditional-requirements\.md.*"
                r"conditional_requirements\[1\]\.when duplicates conditional_requirements\[0\]\.when: "
                r"theorem-bearing claims are present"
            ),
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_non_list(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-non-list.md",
            "  conditional_requirements: true\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-non-list\.md.*conditional_requirements",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_non_mapping_items(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-non-mapping-item.md",
            "  conditional_requirements:\n"
            "    - oops\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-non-mapping-item\.md.*conditional_requirements\[0\]",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_unknown_nested_fields(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-unknown-field.md",
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      legacy_note: stale\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-unknown-field\.md.*conditional_requirements\[0\].*legacy_note",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_blank_when(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-blank-when.md",
            '  conditional_requirements:\n    - when: "   "\n',
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-blank-when\.md.*conditional_requirements\[0\]\.when",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_unsupported_when(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-invalid-when.md",
            "  conditional_requirements:\n"
            "    - when: proof-bearing work is present\n"
            "      required_outputs:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-invalid-when\.md.*conditional_requirements\[0\]\.when",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_non_string_members(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-non-string-member.md",
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n"
            "      required_outputs:\n"
            "        - GPD/review/PROOF-REDTEAM{round_suffix}.md\n"
            "        - true\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-non-string-member\.md.*conditional_requirements\[0\]\.required_outputs",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_conditional_requirements_reject_empty_requirement(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "conditional-requirements-empty.md",
            "  conditional_requirements:\n"
            "    - when: theorem-bearing claims are present\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*conditional-requirements-empty\.md.*conditional_requirements\[0\]",
        ):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize(
        "field_name",
        [
            "stage_ids",
            "final_decision_output",
            "requires_fresh_context_per_stage",
            "max_review_rounds",
        ],
    )
    def test_command_review_contract_removed_dead_fields_raise_unknown_field_errors(
        self, tmp_path: Path, field_name: str
    ) -> None:
        f = _write_review_contract_command(
            tmp_path,
            f"removed-{field_name}.md",
            f"  {field_name}: legacy-value\n",
        )

        with pytest.raises(
            ValueError,
            match=rf"Invalid review-contract in .*removed-{field_name}\.md.*Unknown review-contract field\(s\):",
        ):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize("raw_value", ["7", "true"])
    def test_command_review_contract_review_mode_requires_string(self, tmp_path: Path, raw_value: str) -> None:
        f = tmp_path / f"review-mode-{raw_value}.md"
        f.write_text(
            "---\n"
            "name: gpd:review-mode-invalid\n"
            "review-contract:\n"
            f"  review_mode: {raw_value}\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=rf"Invalid review-contract in .*review-mode-{raw_value}\.md.*review_mode"):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_review_mode_rejects_unsupported_value(self, tmp_path: Path) -> None:
        f = tmp_path / "review-mode-unsupported.md"
        f.write_text(
            "---\n"
            "name: gpd:review-mode-unsupported\n"
            "review-contract:\n"
            "  review_mode: draft\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*review-mode-unsupported\.md.*review_mode.*draft",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_preflight_checks_reject_unsupported_value(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "preflight-checks-unsupported.md",
            "  preflight_checks:\n"
            "    - project_state\n"
            "    - review_queue\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*preflight-checks-unsupported\.md.*preflight_checks.*review_queue",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_required_state_rejects_unsupported_value(self, tmp_path: Path) -> None:
        f = _write_review_contract_command(
            tmp_path,
            "required-state-unsupported.md",
            "  required_state: milestone_complete\n",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*required-state-unsupported\.md.*required_state.*milestone_complete",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_does_not_accept_dead_requires_state_metadata(self, tmp_path: Path) -> None:
        f = tmp_path / "dead-requires-state.md"
        f.write_text(
            "---\n"
            "name: gpd:dead-requires-state\n"
            "requires:\n"
            "  state: phase_executed\n"
            "review-contract:\n"
            "  review_mode: review\n"
            "  schema_version: 1\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="requires for gpd:dead-requires-state only supports files; got state"):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_requires_explicit_schema_version(self, tmp_path: Path) -> None:
        f = tmp_path / "missing-schema-version.md"
        f.write_text(
            "---\n"
            "name: gpd:missing-schema-version\n"
            "review-contract:\n"
            "  review_mode: publication\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*missing-schema-version\.md.*must set schema_version",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_rejects_explicit_null_block(self, tmp_path: Path) -> None:
        f = tmp_path / "null-review-contract.md"
        f.write_text(
            "---\n"
            "name: gpd:null-review-contract\n"
            "review-contract:\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*null-review-contract\.md.*must set schema_version, review_mode",
        ):
            _parse_command_file(f, source="commands")

    @pytest.mark.parametrize("schema_version", ['"v1"', "2"])
    def test_command_review_contract_invalid_schema_version_reports_file_context(
        self, tmp_path: Path, schema_version: str
    ) -> None:
        f = tmp_path / "peer-review.md"
        f.write_text(
            "---\n"
            "name: gpd:peer-review\n"
            "review-contract:\n"
            "  review_mode: publication\n"
            f"  schema_version: {schema_version}\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=r"Invalid review-contract in .*peer-review\.md.*schema_version"):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_unknown_keys_raise(self, tmp_path: Path) -> None:
        f = tmp_path / "write-paper.md"
        f.write_text(
            "---\n"
            "name: gpd:write-paper\n"
            "review-contract:\n"
            "  approval_gate: strict\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=r"Invalid review-contract in .*write-paper\.md.*approval_gate"):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_rejects_review_contract_frontmatter_alias(self, tmp_path: Path) -> None:
        f = tmp_path / "write-paper.md"
        f.write_text(
            "---\n"
            "name: gpd:write-paper\n"
            "review_contract:\n"
            "  schema_version: 1\n"
            "  review_mode: publication\n"
            "  required_outputs:\n"
            "    - GPD/output.md\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*write-paper\.md.*must use the canonical frontmatter key 'review-contract'",
        ):
            _parse_command_file(f, source="commands")

    def test_command_review_contract_rejects_duplicate_frontmatter_aliases(self, tmp_path: Path) -> None:
        f = tmp_path / "write-paper.md"
        f.write_text(
            "---\n"
            "name: gpd:write-paper\n"
            "review-contract:\n"
            "  schema_version: 1\n"
            "  review_mode: publication\n"
            "review_contract:\n"
            "  schema_version: 1\n"
            "  review_mode: publication\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        with pytest.raises(
            ValueError,
            match=r"Invalid review-contract in .*write-paper\.md.*must use the canonical frontmatter key 'review-contract'",
        ):
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
        assert agent.system_prompt.startswith("## Agent Requirements\n")
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
        (agents_dir / "gpd-alias.md").write_text("---\nname: gpd-alias\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        result = registry._discover_agents()
        assert "gpd-alias" in result

    def test_agent_name_mismatch_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "alias.md").write_text("---\nname: gpd-alias\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)

        with pytest.raises(ValueError, match="does not match file stem"):
            registry._discover_agents()

    def test_debug_command_and_debugger_agent_remain_registry_discoverable(self) -> None:
        registry.invalidate_cache()

        debug_command = registry.get_command("gpd:debug")
        debug_skill = registry.get_skill("gpd-debug")
        debugger_agent = registry.get_agent("gpd-debugger")
        debugger_skill = registry.get_skill("gpd-debugger")

        assert debug_command.name == "gpd:debug"
        assert debug_command.agent is None
        assert debug_command.context_mode == "project-required"
        assert debug_command.project_reentry_capable is False
        assert debug_command.allowed_tools == ["file_read", "shell", "task", "ask_user"]
        assert "gpd-debugger" in debug_command.content

        assert debug_skill.source_kind == "command"
        assert debugger_skill.source_kind == "agent"
        assert debug_skill.name == "gpd-debug"
        assert debugger_skill.name == "gpd-debugger"
        assert debugger_agent.surface == "public"
        assert debugger_agent.role_family == "worker"
        assert "public writable production agent specialized for discrepancy investigation" in debugger_agent.system_prompt
        assert {"gpd-debug", "gpd-debugger"}.issubset(registry.list_skills())

    def test_consistency_checker_remains_registry_discoverable(self) -> None:
        registry.invalidate_cache()

        skill = registry.get_skill("gpd-consistency-checker")
        agent = registry.get_agent("gpd-consistency-checker")

        assert skill.name == "gpd-consistency-checker"
        assert skill.source_kind == "agent"
        assert skill.category == "verification"
        assert skill.path.endswith("gpd-consistency-checker.md")
        assert agent.surface == "internal"
        assert agent.role_family == "verification"
        assert agent.commit_authority == "orchestrator"
        assert agent.artifact_write_authority == "scoped_write"
        assert agent.shared_state_authority == "return_only"
        assert agent.tools == ["file_read", "file_write", "shell", "search_files", "find_files"]
        assert "gpd-consistency-checker" in registry.list_skills()

    def test_research_phase_vertical_remains_registry_discoverable(self) -> None:
        registry.invalidate_cache()

        research_command = registry.get_command("gpd:research-phase")
        research_skill = registry.get_skill("gpd-research-phase")
        phase_researcher_skill = registry.get_skill("gpd-phase-researcher")

        assert research_command.name == "gpd:research-phase"
        assert research_command.context_mode == "project-required"
        assert research_skill.name == "gpd-research-phase"
        assert research_skill.category == "research"
        assert phase_researcher_skill.name == "gpd-phase-researcher"
        assert phase_researcher_skill.category == "research"
        assert {"gpd-research-phase", "gpd-phase-researcher"}.issubset(registry.list_skills())

    def test_literature_review_vertical_remains_registry_discoverable(self) -> None:
        registry.invalidate_cache()

        literature_command = registry.get_command("gpd:literature-review")
        literature_skill = registry.get_skill("gpd-literature-review")
        reviewer_skill = registry.get_skill("gpd-literature-reviewer")

        assert literature_command.name == "gpd:literature-review"
        assert literature_command.context_mode == "project-aware"
        assert literature_skill.name == "gpd-literature-review"
        assert literature_skill.category == "research"
        assert reviewer_skill.name == "gpd-literature-reviewer"
        assert reviewer_skill.category == "research"
        assert {"gpd-literature-review", "gpd-literature-reviewer"}.issubset(registry.list_skills())

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
        assert skills["gpd-help"].content.startswith("## Command Requirements\n")
        assert skills["gpd-help"].content.endswith("Primary help body.")
        assert skills["gpd-debugger"].source_kind == "agent"
        assert skills["gpd-debugger"].content.startswith("## Agent Requirements\n")
        assert skills["gpd-debugger"].content.endswith("Primary debugger prompt.")

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


class TestRegistryPromptIncludeInlining:
    """Tests for registry-loaded content surfaces that inline shared includes."""

    def _assert_lightweight_source_surface(self, skill: SkillDef, paths: tuple[str, ...]) -> None:
        for path in paths:
            lightweight = f"{{GPD_INSTALL_DIR}}/{path}"
            eager = f"@{{GPD_INSTALL_DIR}}/{path}"
            assert lightweight in skill.content
            assert eager not in skill.content

    def test_registry_projection_strips_generic_html_comments(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "commented.md").write_text(
            "---\nname: gpd:commented\ndescription: Commented command\n---\n"
            "Command body.\n"
            "<!-- hidden command note -->\n"
            "Inline marker prose keeps <!-- AI-drafted --> visible.\n"
            "```markdown\n"
            "<!-- AI-drafted -->\n"
            "```\n"
            "Visible tail.",
            encoding="utf-8",
        )

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "gpd-commented.md").write_text(
            "---\nname: gpd-commented\ndescription: Commented agent\ntools: file_read\n---\n"
            "Agent body.\n"
            "<!-- hidden agent note -->\n"
            "Inline marker prose keeps <!-- AI-drafted --> visible.\n"
            "```markdown\n"
            "<!-- AI-drafted -->\n"
            "```\n"
            "Visible tail.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        try:
            command = registry.get_command("gpd:commented")
            agent = registry.get_agent("gpd-commented")

            assert "<!-- hidden command note -->" not in command.content
            assert "<!-- hidden agent note -->" not in agent.system_prompt
            assert "Inline marker prose keeps <!-- AI-drafted --> visible." in command.content
            assert "Inline marker prose keeps <!-- AI-drafted --> visible." in agent.system_prompt
            assert "```markdown\n<!-- AI-drafted -->\n```" in command.content
            assert "```markdown\n<!-- AI-drafted -->\n```" in agent.system_prompt
            assert "Visible tail." in command.content
            assert "Visible tail." in agent.system_prompt
        finally:
            registry.invalidate_cache()

    def test_verifier_system_prompt_keeps_verifier_routing_stub_and_schema_references_visible(self) -> None:
        agent = registry.get_agent("gpd-verifier")

        assert "## Domain Routing Stub" in agent.system_prompt
        assert "Load only the matching domain checklist pack(s);" in agent.system_prompt
        assert "# Verification Report Template" in agent.system_prompt
        assert "# Contract Results Schema" in agent.system_prompt
        assert "# Canonical Schema Discipline" in agent.system_prompt
        assert "<!-- [included:" not in agent.system_prompt

    def test_project_researcher_system_prompt_keeps_one_shot_checkpoint_contract_visible(self) -> None:
        agent = registry.get_skill("gpd-project-researcher")

        assert agent.source_kind == "agent"
        assert agent.path.endswith("gpd-project-researcher.md")
        assert "Checkpoint after the initial survey with scope confirmation." in agent.content
        assert "gpd_return:" in agent.content
        assert "status: completed | checkpoint | blocked | failed" in agent.content
        assert "Do NOT run `gpd commit`, `git commit`, or stage files." in agent.content
        assert "wait for confirmation" not in agent.content
        assert "pause here for approval" not in agent.content
        assert "ask the user then continue" not in agent.content

    def test_plan_checker_registry_surface_keeps_direct_plan_contract_schema_and_checkpoint_contract_visible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from functools import lru_cache
        from shutil import copytree

        agents_dir = tmp_path / "agents"
        copytree(Path(__file__).resolve().parents[1] / "src" / "gpd" / "agents", agents_dir)
        plan_checker_path = agents_dir / "gpd-plan-checker.md"
        plan_checker_text = plan_checker_path.read_text(encoding="utf-8")
        plan_checker_text = plan_checker_text.replace(
            "artifact_write_authority: return_only",
            "artifact_write_authority: read_only",
        )
        plan_checker_path.write_text(
            plan_checker_text.replace(
                "tools: file_read, file_write, shell, find_files, search_files, web_search, web_fetch",
                "tools: file_read, shell, find_files, search_files, web_search, web_fetch",
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        monkeypatch.setattr(registry, "_builtin_agent_names", lru_cache(maxsize=1)(lambda: frozenset()))
        registry.invalidate_cache()

        skill = registry.get_skill("gpd-plan-checker")

        assert skill.source_kind == "agent"
        assert skill.path.endswith("gpd-plan-checker.md")
        assert "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in skill.content
        assert "This is a one-shot handoff. If user input is needed, return `status: checkpoint`; do not wait inside the same run." in skill.content
        assert "approved_plans: [list of plan IDs that passed]" in skill.content
        assert "blocked_plans: [list of plan IDs needing revision or escalation]" in skill.content

    def test_write_paper_command_surface_uses_staged_loading_for_contract_schemas(self) -> None:
        command = registry.get_command("gpd:write-paper")

        assert command.staged_loading is not None
        assert "Paper Config Schema" not in command.content
        assert "Review Ledger Schema" not in command.content
        assert "Referee Decision Schema" not in command.content
        assert "templates/paper/paper-config-schema.md" in command.staged_loading.stage(
            "outline_and_scaffold"
        ).loaded_authorities
        assert "references/publication/peer-review-panel.md" in command.staged_loading.stage(
            "publication_review"
        ).loaded_authorities
        assert "templates/paper/review-ledger-schema.md" in command.staged_loading.stage(
            "publication_review"
        ).loaded_authorities
        assert "templates/paper/referee-decision-schema.md" in command.staged_loading.stage(
            "publication_review"
        ).loaded_authorities

    def test_publication_review_skills_keep_the_needed_contract_references_visible(self) -> None:
        from gpd.mcp.servers.skills_server import get_skill

        referee = get_skill("gpd-referee")
        review_reader = get_skill("gpd-review-reader")

        assert "error" not in referee
        assert any(path.endswith("peer-review-panel.md") for path in referee["contract_references"])
        assert any(
            entry["path"].endswith("publication-review-round-artifacts.md") for entry in referee["referenced_files"]
        )
        assert any(
            entry["path"].endswith("publication-response-artifacts.md") for entry in referee["referenced_files"]
        )
        assert any(path.endswith("review-ledger-schema.md") for path in referee["schema_references"])
        assert any(path.endswith("referee-decision-schema.md") for path in referee["schema_references"])

        assert "error" not in review_reader
        assert any(path.endswith("peer-review-panel.md") for path in review_reader["contract_references"])
        assert review_reader["schema_references"] == []
        assert any(path.endswith("review-ledger-schema.md") for path in review_reader["transitive_schema_references"])
        assert any(path.endswith("referee-decision-schema.md") for path in review_reader["transitive_schema_references"])

    def test_check_proof_registry_surface_preserves_lightweight_path_mentions(self) -> None:
        skill = registry.get_skill("gpd-check-proof")

        assert skill.source_kind == "agent"
        assert skill.path.endswith("gpd-check-proof.md")
        self._assert_lightweight_source_surface(
            skill,
            (
                "references/shared/shared-protocols.md",
                "references/orchestration/agent-infrastructure.md",
                "references/physics-subfields.md",
                "references/verification/core/verification-core.md",
                "templates/proof-redteam-schema.md",
                "references/verification/core/proof-redteam-protocol.md",
                "references/publication/peer-review-panel.md",
            ),
        )
        assert "Proof-redteam" in skill.content
        assert "Manuscript review on demand only" in skill.content

    def test_paper_writer_registry_surface_preserves_lightweight_path_mentions(self) -> None:
        skill = registry.get_skill("gpd-paper-writer")

        assert skill.source_kind == "agent"
        assert skill.path.endswith("gpd-paper-writer.md")
        self._assert_lightweight_source_surface(
            skill,
            (
                "references/shared/shared-protocols.md",
                "references/orchestration/agent-infrastructure.md",
                "templates/notation-glossary.md",
                "templates/latex-preamble.md",
                "references/publication/publication-pipeline-modes.md",
                "references/publication/paper-writer-cookbook.md",
                "references/publication/figure-generation-templates.md",
                "references/publication/publication-response-writer-handoff.md",
                "templates/paper/author-response.md",
                "templates/paper/referee-response.md",
            ),
        )

    def test_bibliographer_registry_surface_preserves_lightweight_path_mentions(self) -> None:
        skill = registry.get_skill("gpd-bibliographer")

        assert skill.source_kind == "agent"
        assert skill.path.endswith("gpd-bibliographer.md")
        self._assert_lightweight_source_surface(
            skill,
            (
                "references/shared/shared-protocols.md",
                "references/physics-subfields.md",
                "references/orchestration/agent-infrastructure.md",
                "templates/notation-glossary.md",
                "references/publication/bibtex-standards.md",
                "references/publication/publication-pipeline-modes.md",
                "references/publication/bibliography-advanced-search.md",
            ),
        )


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

    def test_invalidate_cache_clears_workflow_stage_manifest_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []

        monkeypatch.setattr(registry, "invalidate_workflow_stage_manifest_cache", lambda: calls.append("called"))

        registry.invalidate_cache()

        assert calls == ["called"]

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

    def test_canonical_agent_names_follows_monkeypatched_agent_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        agents_dir = tmp_path / "patched-agents"
        agents_dir.mkdir()
        (agents_dir / "zeta.md").write_text("---\nname: zeta\n---\nPrompt.", encoding="utf-8")
        (agents_dir / "alpha.md").write_text("---\nname: alpha\n---\nPrompt.", encoding="utf-8")

        monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
        registry.invalidate_cache()

        assert registry.canonical_agent_names() == ("alpha", "zeta")

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
            "---\n"
            "name: gpd:peer-review\n"
            "description: Peer review\n"
            "review-contract:\n"
            "  review_mode: publication\n"
            "  schema_version: 1\n"
            "---\n"
            "Review body.",
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
        assert agent.system_prompt.startswith("## Agent Requirements\n")
        assert agent.system_prompt.endswith("Test prompt.")

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

    def test_get_command_new_project_surfaces_staged_loading_manifest(self) -> None:
        registry.invalidate_cache()

        cmd = registry.get_command("gpd:new-project")

        assert cmd.staged_loading is not None
        assert cmd.staged_loading.workflow_id == "new-project"
        assert cmd.staged_loading.stage_ids() == ("scope_intake", "scope_approval", "post_scope")
        assert cmd.staged_loading.stages[0].loaded_authorities == ("workflows/new-project.md",)
        assert "project_contract_gate" in cmd.staged_loading.stages[0].required_init_fields
        assert "project_contract_load_info" in cmd.staged_loading.stages[0].required_init_fields
        assert cmd.staged_loading.stages[0].produced_state == (
            "intake routing state",
            "scoping-contract gate state",
        )
        assert cmd.staged_loading.stages[0].checkpoints == (
            "detect existing workspace state",
            "surface the first scoping question",
            "preserve contract gate visibility without assuming approval-stage authority",
        )
        assert cmd.staged_loading.stages[1].produced_state == (
            "approved project contract",
            "approval-state persistence",
        )
        assert cmd.staged_loading.stages[1].checkpoints == (
            "approval gate has passed",
            "project contract is ready for persistence",
        )
        assert cmd.staged_loading.stages[2].produced_state == (
            "project artifacts",
            "workflow preferences",
            "downstream stage handoff",
        )
        assert cmd.staged_loading.stages[2].checkpoints == (
            "approval gate has passed",
            "stage-aware deferred reads are now allowed",
        )

    def test_get_command_new_project_surfaces_spawn_contract_inventory(self) -> None:
        registry.invalidate_cache()

        command = registry.get_command("gpd:new-project")
        skill = registry.get_skill("gpd-new-project")

        assert command.spawn_contracts
        assert skill.spawn_contracts == command.spawn_contracts
        assert len(command.spawn_contracts) == 7
        assert all("write_scope" in contract for contract in command.spawn_contracts)
        assert all("expected_artifacts" in contract for contract in command.spawn_contracts)
        assert {contract["shared_state_policy"] for contract in command.spawn_contracts} == {
            "return_only",
            "direct",
        }
        assert {contract["write_scope"]["mode"] for contract in command.spawn_contracts} == {"scoped_write"}

    def test_get_command_new_milestone_surfaces_roadmapper_handoff(self) -> None:
        registry.invalidate_cache()

        command = registry.get_command("gpd:new-milestone")

        assert "gpd-roadmapper spawned with staged continuation context" in command.content
        assert "gpd-roadmapper" in command.content
        assert "roadmapper" in command.content

    def test_get_command_new_milestone_surfaces_staged_loading_manifest(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        manifest_path = tmp_path / "new-milestone-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "new-milestone",
                    "stages": [
                        {
                            "id": "milestone_bootstrap",
                            "order": 1,
                            "purpose": "milestone lookup and routing",
                            "mode_paths": ["workflows/new-milestone.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/new-milestone.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/research/questioning.md"],
                            "allowed_tools": ["file_read", "task"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(
            registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path
            if workflow_id == "new-milestone"
            else original_resolve_manifest_path(workflow_id),
        )
        registry.invalidate_cache()

        command = registry.get_command("gpd:new-milestone")

        assert command.staged_loading is not None
        assert command.staged_loading.workflow_id == "new-milestone"
        assert command.staged_loading.stage_ids() == ("milestone_bootstrap",)
        assert command.staged_loading.stages[0].loaded_authorities == ("workflows/new-milestone.md",)
        assert command.staged_loading.stages[0].must_not_eager_load == ("references/research/questioning.md",)
        assert command.staged_loading.stages[0].writes_allowed == ()
        assert command.staged_loading.stages[0].next_stages == ()

    def test_research_synthesizer_surface_keeps_canonical_summary_return_contract_visible(self) -> None:
        registry.invalidate_cache()

        synthesizer = registry.get_skill("gpd-research-synthesizer")
        new_project = registry.get_skill("gpd-new-project")
        new_milestone = registry.get_skill("gpd-new-milestone")
        new_project_command = registry.get_command("gpd:new-project")
        new_milestone_command = registry.get_command("gpd:new-milestone")

        assert synthesizer.source_kind == "agent"
        assert synthesizer.path.endswith("gpd-research-synthesizer.md")
        assert "This agent writes only `GPD/literature/SUMMARY.md`;" in synthesizer.content
        assert "files_written` must list only files actually written in this run." in synthesizer.content
        assert "Use only status names: `completed` | `checkpoint` | `blocked` | `failed`." in synthesizer.content
        assert "gpd_return:" in synthesizer.content

        assert new_project.spawn_contracts == new_project_command.spawn_contracts
        assert new_milestone.spawn_contracts == new_milestone_command.spawn_contracts
        assert RESEARCH_SYNTHESIZER_SUMMARY_CONTRACT in new_project.spawn_contracts
        assert RESEARCH_SYNTHESIZER_SUMMARY_CONTRACT in new_milestone.spawn_contracts
        assert new_project.spawn_contracts[4] == RESEARCH_SYNTHESIZER_SUMMARY_CONTRACT
        assert new_milestone.spawn_contracts[1] == RESEARCH_SYNTHESIZER_SUMMARY_CONTRACT

    def test_get_command_plan_phase_surfaces_staged_loading_manifest(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            commands_dir = Path(tmp) / "commands"
            commands_dir.mkdir()
            (commands_dir / "plan-phase.md").write_text(
                "---\n"
                "name: gpd:plan-phase\n"
                "description: Plan phase\n"
                "allowed-tools:\n"
                "  - file_read\n"
                "---\n"
                "Body.",
                encoding="utf-8",
            )

            manifest_path = Path(tmp) / "plan-phase-stage-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "workflow_id": "plan-phase",
                        "stages": [
                            {
                                "id": "phase_bootstrap",
                                "order": 1,
                                "purpose": "phase lookup and routing",
                                "mode_paths": ["workflows/plan-phase.md"],
                                "required_init_fields": [],
                                "loaded_authorities": ["workflows/plan-phase.md"],
                                "conditional_authorities": [],
                                "must_not_eager_load": ["references/ui/ui-brand.md"],
                                "allowed_tools": ["file_read"],
                                "writes_allowed": [],
                                "produced_state": [],
                                "next_stages": ["research_routing"],
                                "checkpoints": [],
                            },
                            {
                                "id": "planner_authoring",
                                "order": 2,
                                "purpose": "planner handoff",
                                "mode_paths": ["workflows/plan-phase.md"],
                                "required_init_fields": ["researcher_model"],
                                "loaded_authorities": [
                                    "workflows/plan-phase.md",
                                    "templates/planner-subagent-prompt.md",
                                ],
                                "conditional_authorities": [],
                                "must_not_eager_load": ["references/ui/ui-brand.md"],
                                "allowed_tools": ["file_read"],
                                "writes_allowed": ["GPD/phases"],
                                "produced_state": [],
                                "next_stages": [],
                                "checkpoints": [],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            original_resolve_manifest_path = registry.resolve_workflow_stage_manifest_path
            monkeypatch = pytest.MonkeyPatch()
            monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
            monkeypatch.setattr(
                registry,
                "resolve_workflow_stage_manifest_path",
                lambda workflow_id: manifest_path if workflow_id == "plan-phase" else original_resolve_manifest_path(workflow_id),
            )
            try:
                registry.invalidate_cache()
                cmd = registry.get_command("plan-phase")
            finally:
                monkeypatch.undo()
                registry.invalidate_cache()

            assert cmd.staged_loading is not None
            assert cmd.staged_loading.workflow_id == "plan-phase"
            assert cmd.staged_loading.stage_ids() == ("phase_bootstrap", "planner_authoring")
            assert cmd.staged_loading.stages[0].loaded_authorities == ("workflows/plan-phase.md",)
            assert "templates/planner-subagent-prompt.md" in cmd.staged_loading.stages[1].loaded_authorities

    def test_get_command_verify_work_surfaces_staged_loading_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest_path = repo_root / "src" / "gpd" / "specs" / "workflows" / "verify-work-stage-manifest.json"
        original_resolve_manifest_path = registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(
            registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path
            if workflow_id == "verify-work"
            else original_resolve_manifest_path(workflow_id),
        )
        registry.invalidate_cache()

        cmd = registry.get_command("verify-work")

        assert cmd.staged_loading is not None
        assert cmd.staged_loading.workflow_id == "verify-work"
        assert cmd.staged_loading.stage_ids() == (
            "session_router",
            "phase_bootstrap",
            "inventory_build",
            "interactive_validation",
            "gap_repair",
        )
        assert cmd.staged_loading.stages[0].loaded_authorities == ("workflows/verify-work.md",)
        assert cmd.staged_loading.stages[2].loaded_authorities == (
            "workflows/verify-work.md",
            "references/verification/meta/verification-independence.md",
        )
        assert cmd.staged_loading.stages[2].next_stages == ("interactive_validation",)
        assert cmd.staged_loading.stages[2].checkpoints == (
            "verifier delegation completed",
            "handoff remains fail-closed",
            "anchor obligations explicit",
        )
        assert cmd.staged_loading.stages[3].allowed_tools == (
            "ask_user",
            "file_read",
            "file_edit",
            "file_write",
            "find_files",
            "search_files",
            "shell",
            "task",
        )
        assert cmd.staged_loading.stages[3].loaded_authorities == (
            "workflows/verify-work.md",
            "templates/research-verification.md",
            "templates/verification-report.md",
            "templates/contract-results-schema.md",
            "references/shared/canonical-schema-discipline.md",
        )
        assert cmd.staged_loading.stages[3].writes_allowed == ("GPD/phases/XX-name/XX-VERIFICATION.md",)
        assert cmd.staged_loading.stages[3].next_stages == ("gap_repair",)
        assert cmd.staged_loading.stages[3].checkpoints == (
            "verification file can be written",
            "writer-stage schema is visible",
            "check results remain contract-backed",
        )
        assert cmd.staged_loading.stages[4].loaded_authorities == (
            "workflows/verify-work.md",
            "templates/research-verification.md",
            "templates/verification-report.md",
            "templates/contract-results-schema.md",
            "references/shared/canonical-schema-discipline.md",
            "references/protocols/error-propagation-protocol.md",
        )
        assert cmd.staged_loading.stages[4].writes_allowed == ("GPD/phases/XX-name/XX-VERIFICATION.md",)
        assert cmd.staged_loading.stages[4].next_stages == ()
        assert cmd.staged_loading.stages[4].checkpoints == (
            "gaps are diagnosed",
            "repair plans are verified",
            "verification closeout is ready",
        )

    def test_get_command_execute_phase_surfaces_staged_loading_manifest(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "execute-phase.md").write_text(
            "---\n"
            "name: gpd:execute-phase\n"
            "description: Execute phase\n"
            "allowed-tools:\n"
            "  - file_read\n"
            "---\n"
            "Body.",
            encoding="utf-8",
        )

        manifest_path = tmp_path / "execute-phase-stage-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow_id": "execute-phase",
                    "stages": [
                        {
                            "id": "phase_bootstrap",
                            "order": 1,
                            "purpose": "phase lookup and routing",
                            "mode_paths": ["workflows/execute-phase.md"],
                            "required_init_fields": [],
                            "loaded_authorities": ["workflows/execute-phase.md"],
                            "conditional_authorities": [],
                            "must_not_eager_load": ["references/ui/ui-brand.md"],
                            "allowed_tools": ["file_read"],
                            "writes_allowed": [],
                            "produced_state": [],
                            "next_stages": [],
                            "checkpoints": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        original_resolve_manifest_path = registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(
            registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path if workflow_id == "execute-phase" else original_resolve_manifest_path(workflow_id),
        )
        registry.invalidate_cache()

        cmd = registry.get_command("execute-phase")

        assert cmd.staged_loading is not None
        assert cmd.staged_loading.workflow_id == "execute-phase"
        assert cmd.staged_loading.stage_ids() == ("phase_bootstrap",)
        assert cmd.staged_loading.stages[0].loaded_authorities == ("workflows/execute-phase.md",)

    def test_get_command_research_phase_surfaces_staged_loading_manifest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        manifest_path = repo_root / "src" / "gpd" / "specs" / "workflows" / "research-phase-stage-manifest.json"
        original_resolve_manifest_path = registry.resolve_workflow_stage_manifest_path
        monkeypatch.setattr(
            registry,
            "resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path
            if workflow_id == "research-phase"
            else original_resolve_manifest_path(workflow_id),
        )
        registry.invalidate_cache()

        cmd = registry.get_command("research-phase")

        assert cmd.staged_loading is not None
        assert cmd.staged_loading.workflow_id == "research-phase"
        assert cmd.staged_loading.stage_ids() == ("phase_bootstrap", "research_handoff")
        assert cmd.staged_loading.stages[0].loaded_authorities == (
            "workflows/research-phase.md",
            "references/orchestration/model-profile-resolution.md",
        )
        assert "references/orchestration/runtime-delegation-note.md" in cmd.staged_loading.stages[0].must_not_eager_load
        assert cmd.staged_loading.stages[1].loaded_authorities == (
            "workflows/research-phase.md",
            "references/orchestration/model-profile-resolution.md",
            "references/orchestration/runtime-delegation-note.md",
        )
        assert cmd.staged_loading.stages[1].writes_allowed == ("GPD/phases/XX-name/XX-RESEARCH.md",)
        assert "reference_artifacts_content" in cmd.staged_loading.stages[1].required_init_fields

    def test_get_agent_phase_researcher_surfaces_one_shot_handoff_contract(self) -> None:
        agent = registry.get_agent("gpd-phase-researcher")

        assert agent.name == "gpd-phase-researcher"
        assert "## Active Anchor References" in agent.system_prompt
        assert "## Don't Re-Derive" in agent.system_prompt
        assert "## RESEARCH COMPLETE" in agent.system_prompt
        assert "## RESEARCH BLOCKED" in agent.system_prompt
        assert "gpd_return:" in agent.system_prompt
        assert "status: completed | checkpoint | blocked | failed" in agent.system_prompt
        assert "RESEARCH.md" in agent.system_prompt

    def test_registry_cache_invalidation_clears_new_project_stage_manifest(self) -> None:
        registry.invalidate_cache()
        first = registry.get_command("gpd:new-project").staged_loading
        assert first is not None

        registry.invalidate_cache()
        second = registry.get_command("gpd:new-project").staged_loading
        assert second is not None

        assert first is not second

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

    def test_get_command_rejects_foreign_bare_slash_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "help.md").write_text("---\nname: gpd:help\ndescription: Help\n---\nHelp body.", encoding="utf-8")

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        registry.invalidate_cache()

        with pytest.raises(KeyError, match=r"Command not found: /help"):
            registry.get_command("/help")

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
        assert skill.content.startswith("## Command Requirements\n")
        assert skill.content.endswith("Execute body.")

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

    def test_get_skill_rejects_foreign_bare_slash_command(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "execute-phase.md").write_text(
            "---\nname: gpd:execute-phase\ndescription: Execute\n---\nExecute body.",
            encoding="utf-8",
        )

        monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
        monkeypatch.setattr(registry, "AGENTS_DIR", tmp_path / "nonexistent-agents")
        registry.invalidate_cache()

        with pytest.raises(KeyError, match=r"Skill not found: /help"):
            registry.get_skill("/help")

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

    def test_real_recovery_commands_expose_project_reentry_metadata(self) -> None:
        registry.invalidate_cache()

        progress = registry.get_command("progress")
        resume_work = registry.get_command("resume-work")
        quick = registry.get_command("quick")

        assert progress.context_mode == "project-required"
        assert progress.project_reentry_capable is True
        assert resume_work.context_mode == "project-required"
        assert resume_work.project_reentry_capable is True
        assert quick.context_mode == "project-required"
        assert quick.project_reentry_capable is False

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

    def test_command_def_accepts_staged_loading_sidecar(self) -> None:
        from gpd.core.workflow_staging import WorkflowStage

        staged_loading = WorkflowStageManifest(
            schema_version=1,
            workflow_id="new-project",
            stages=(
                WorkflowStage(
                    id="scope_intake",
                    order=1,
                    purpose="intake",
                    mode_paths=("workflows/new-project.md",),
                    required_init_fields=(),
                    loaded_authorities=("workflows/new-project.md",),
                    conditional_authorities=(),
                    must_not_eager_load=(),
                    allowed_tools=(),
                    writes_allowed=(),
                    produced_state=(),
                    next_stages=(),
                    checkpoints=(),
                ),
            ),
        )
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
            staged_loading=staged_loading,
        )

        assert cmd.staged_loading is staged_loading

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


def test_executor_skill_defers_completion_only_materials_until_summary_creation() -> None:
    skill = registry.get_skill("gpd-executor")
    bootstrap, _, _ = skill.content.partition("<summary_creation>")

    assert skill.name == "gpd-executor"
    assert skill.source_kind == "agent"
    assert "templates/summary.md" not in bootstrap
    assert "templates/calculation-log.md" not in bootstrap
    assert "Order-of-Limits Awareness" not in bootstrap


def test_planner_skill_defers_late_planning_materials_into_on_demand_references() -> None:
    skill = registry.get_skill("gpd-planner")
    bootstrap, separator, _ = skill.content.partition("On-demand references:")

    assert skill.name == "gpd-planner"
    assert skill.source_kind == "agent"
    assert separator == "On-demand references:"
    assert "Phase Plan Prompt" in bootstrap
    assert "PLAN Contract Schema" in bootstrap
    assert "Read config.json for planning behavior settings." not in bootstrap
    assert "## Summary Template" not in bootstrap
    assert "Order-of-Limits Awareness" not in bootstrap
