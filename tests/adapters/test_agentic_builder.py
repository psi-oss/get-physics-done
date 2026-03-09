"""Tests for the Agentic Builder runtime adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters.agentic_builder import (
    AgenticBuilderAdapter,
    _resolve_placeholders,
    build_placeholder_context,
)
from gpd.registry import _parse_frontmatter


@pytest.fixture()
def adapter() -> AgenticBuilderAdapter:
    return AgenticBuilderAdapter()


class TestProperties:
    def test_runtime_name(self, adapter: AgenticBuilderAdapter) -> None:
        assert adapter.runtime_name == "agentic-builder"

    def test_display_name(self, adapter: AgenticBuilderAdapter) -> None:
        assert adapter.display_name == "Agentic Builder"

    def test_config_dir_name(self, adapter: AgenticBuilderAdapter) -> None:
        assert adapter.config_dir_name == ".psi"

    def test_help_command(self, adapter: AgenticBuilderAdapter) -> None:
        assert adapter.help_command == "gpd help"


class TestTranslateToolName:
    def test_identity_mapping(self, adapter: AgenticBuilderAdapter) -> None:
        assert adapter.translate_tool_name("file_read") == "file_read"
        assert adapter.translate_tool_name("shell") == "shell"
        assert adapter.translate_tool_name("web_search") == "web_search"

    def test_legacy_alias_canonicalized(self, adapter: AgenticBuilderAdapter) -> None:
        assert adapter.translate_tool_name("Read") == "file_read"
        assert adapter.translate_tool_name("Bash") == "shell"


class TestParseFrontmatter:
    def test_no_frontmatter(self) -> None:
        meta, body = _parse_frontmatter("Just body text")
        assert meta == {}
        assert body == "Just body text"

    def test_basic_frontmatter(self) -> None:
        content = "---\nname: test\ndescription: A description\n---\nBody text"
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "test"
        assert meta["description"] == "A description"
        assert body.strip() == "Body text"

    def test_tools_comma_separated(self) -> None:
        content = "---\nname: test\ntools: Read, Write, Bash\n---\nBody"
        meta, body = _parse_frontmatter(content)
        assert meta["tools"] == "Read, Write, Bash"

    def test_tools_yaml_array(self) -> None:
        content = "---\nname: test\ntools:\n  - Read\n  - Write\n---\nBody"
        meta, body = _parse_frontmatter(content)
        assert meta["tools"] == ["Read", "Write"]

    def test_malformed_frontmatter(self) -> None:
        content = "---\nnot_a_dict\n---\nBody"
        meta, body = _parse_frontmatter(content)
        # Scalar YAML → treated as no frontmatter (returns empty meta)
        assert meta == {}
        assert body == content


class TestResolvePlaceholders:
    def test_resolves_known_keys(self) -> None:
        result = _resolve_placeholders("Dir: {GPD_INSTALL_DIR}/foo", {"GPD_INSTALL_DIR": "/opt/gpd"})
        assert result == "Dir: /opt/gpd/foo"

    def test_unknown_left_as_is(self) -> None:
        result = _resolve_placeholders("Dir: {UNKNOWN}/foo", {"GPD_INSTALL_DIR": "/opt/gpd"})
        assert "{UNKNOWN}" in result

    def test_multiple_placeholders(self) -> None:
        result = _resolve_placeholders(
            "{a} and {b}",
            {"a": "X", "b": "Y"},
        )
        assert result == "X and Y"

    def test_no_placeholders(self) -> None:
        assert _resolve_placeholders("no placeholders here", {}) == "no placeholders here"


class TestBuildPlaceholderContext:
    def test_default_gpd_install_dir(self) -> None:
        ctx = build_placeholder_context()
        assert "GPD_INSTALL_DIR" in ctx
        assert ctx["GPD_INSTALL_DIR"]  # non-empty

    def test_custom_gpd_install_dir(self, tmp_path: Path) -> None:
        ctx = build_placeholder_context(gpd_install_dir=tmp_path)
        assert ctx["GPD_INSTALL_DIR"] == str(tmp_path)

    def test_convention_context(self) -> None:
        ctx = build_placeholder_context(convention_context="metric=(-,+,+,+)")
        assert ctx["convention_context"] == "metric=(-,+,+,+)"

    def test_role_identity(self) -> None:
        ctx = build_placeholder_context(role_identity="Phase verifier")
        assert ctx["role_identity"] == "Phase verifier"

    def test_extra_merged(self) -> None:
        ctx = build_placeholder_context(extra={"custom_key": "custom_value"})
        assert ctx["custom_key"] == "custom_value"

    def test_empty_convention_context_excluded(self) -> None:
        ctx = build_placeholder_context(convention_context="")
        assert "convention_context" not in ctx


class TestGenerateCommand:
    def test_creates_txt_file(self, adapter: AgenticBuilderAdapter, tmp_path: Path) -> None:
        result = adapter.generate_command({"name": "help", "content": "Help text"}, tmp_path)
        assert result == tmp_path / "prompts" / "help.txt"
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "Help text"

    def test_creates_prompts_dir(self, adapter: AgenticBuilderAdapter, tmp_path: Path) -> None:
        adapter.generate_command({"name": "test", "content": "body"}, tmp_path)
        assert (tmp_path / "prompts").is_dir()


class TestGenerateAgent:
    def test_creates_txt_file(self, adapter: AgenticBuilderAdapter, tmp_path: Path) -> None:
        result = adapter.generate_agent({"name": "gpd-verifier", "content": "Agent prompt"}, tmp_path)
        assert result == tmp_path / "agents" / "gpd-verifier.txt"
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "Agent prompt"


class TestGenerateHook:
    def test_returns_empty_dict(self, adapter: AgenticBuilderAdapter) -> None:
        result = adapter.generate_hook("test", {"command": "cmd"})
        assert result == {}
