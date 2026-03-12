"""Regression tests for adapter frontmatter conversion edge cases."""

from __future__ import annotations

from gpd.adapters.codex import _convert_to_codex_skill
from gpd.adapters.gemini import _convert_frontmatter_to_gemini, _convert_to_gemini_toml
from gpd.adapters.install_utils import split_markdown_frontmatter
from gpd.adapters.opencode import convert_claude_to_opencode_frontmatter


def test_split_markdown_frontmatter_keeps_inline_triple_dash_in_field_value() -> None:
    content = "---\nname: test\ndescription: before --- after\n---\nBody\n"

    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)

    assert preamble == ""
    assert separator == "\n"
    assert frontmatter == "name: test\ndescription: before --- after"
    assert body == "Body\n"


def test_codex_skill_conversion_preserves_inline_triple_dash_in_description() -> None:
    content = "---\nname: test\ndescription: before --- after\nallowed-tools:\n  - shell\n---\nBody\n"

    converted = _convert_to_codex_skill(content, "test")

    assert "description: before --- after" in converted
    assert "allowed-tools:\n  - shell" in converted
    assert converted.endswith("---\nBody\n")


def test_gemini_frontmatter_conversion_preserves_inline_triple_dash_in_description() -> None:
    content = "---\nname: test\ndescription: before --- after\nallowed-tools:\n  - shell\n---\nBody\n"

    converted = _convert_frontmatter_to_gemini(content)

    assert "description: before --- after" in converted
    assert "tools:\n  - run_shell_command" in converted
    assert converted.endswith("---\nBody\n")


def test_gemini_toml_conversion_preserves_inline_triple_dash_in_description() -> None:
    content = "---\nname: test\ndescription: before --- after\nallowed-tools:\n  - shell\n---\nBody\n"

    converted = _convert_to_gemini_toml(content)

    assert 'description = "before --- after"' in converted
    assert "prompt = '''\nBody\n'''\n" in converted


def test_opencode_frontmatter_conversion_preserves_inline_triple_dash_in_description() -> None:
    content = "---\nname: test\ndescription: before --- after\nallowed-tools:\n  - shell\n---\nBody\n"

    converted = convert_claude_to_opencode_frontmatter(content, "~/.config/runtime/")

    assert "description: before --- after" in converted
    assert "tools:\n  shell: true" in converted
    assert converted.endswith("---\nBody\n")
