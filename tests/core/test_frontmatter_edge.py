"""Edge-case stress tests for gpd.core.frontmatter parsing and writing."""

from __future__ import annotations

import pytest

from gpd.core.frontmatter import (
    FrontmatterParseError,
    deep_merge_frontmatter,
    extract_frontmatter,
    reconstruct_frontmatter,
    splice_frontmatter,
)

# ---------------------------------------------------------------------------
# BOM (Byte Order Mark)
# ---------------------------------------------------------------------------


class TestBOM:
    """Frontmatter with a leading UTF-8 BOM (\ufeff)."""

    def test_bom_before_opening_delimiter(self):
        content = "\ufeff---\ntitle: Hello\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello"}
        assert "Body." in body

    def test_bom_with_crlf(self):
        content = "\ufeff---\r\ntitle: Hello\r\n---\r\n\r\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello"}
        assert "Body." in body

    def test_bom_with_empty_frontmatter(self):
        content = "\ufeff---\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body." in body

    def test_bom_splice_preserves_content(self):
        content = "\ufeff---\ntitle: Old\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert "Body." in body

    def test_bom_deep_merge(self):
        content = "\ufeff---\nouter:\n  a: 1\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"outer": {"b": 2}})
        meta, _ = extract_frontmatter(result)
        assert meta["outer"]["a"] == 1
        assert meta["outer"]["b"] == 2

    def test_multiple_boms_stripped(self):
        """Multiple consecutive BOMs should all be stripped."""
        content = "\ufeff\ufeff\ufeff---\nkey: val\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"key": "val"}
        assert "Body." in body


# ---------------------------------------------------------------------------
# Windows line endings (\r\n)
# ---------------------------------------------------------------------------


class TestWindowsLineEndings:
    """Frontmatter using CRLF line endings throughout."""

    def test_crlf_extraction(self):
        content = "---\r\ntitle: Hello\r\nauthor: World\r\n---\r\n\r\nBody text."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello", "author": "World"}
        assert "Body text." in body

    def test_crlf_empty_frontmatter(self):
        content = "---\r\n---\r\n\r\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body." in body

    def test_crlf_splice_preserves_line_endings(self):
        content = "---\r\ntitle: Old\r\n---\r\n\r\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        # The splice should detect and preserve CRLF
        assert "\r\n" in result
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert "Body." in body

    def test_crlf_deep_merge_preserves_line_endings(self):
        content = "---\r\ntitle: Old\r\n---\r\n\r\nBody."
        result = deep_merge_frontmatter(content, {"status": "done"})
        assert "\r\n" in result
        meta, _ = extract_frontmatter(result)
        assert meta["title"] == "Old"
        assert meta["status"] == "done"

    def test_mixed_line_endings_lf_dominant(self):
        """If content has mostly LF with a stray CRLF in the body, splice detects CRLF."""
        content = "---\ntitle: Test\n---\n\nBody with\r\nmixed endings."
        result = splice_frontmatter(content, {"title": "New"})
        # The `"\r\n" in content` check will find the CRLF in the body
        assert "\r\n" in result

    def test_crlf_no_trailing_newline(self):
        content = "---\r\ntitle: test\r\n---"
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "test"}
        assert body == ""


# ---------------------------------------------------------------------------
# Trailing whitespace
# ---------------------------------------------------------------------------


class TestTrailingWhitespace:
    """Frontmatter values and delimiters with trailing spaces/tabs."""

    def test_trailing_spaces_in_values(self):
        content = "---\ntitle: Hello   \nphase: '01'   \n---\n\nBody."
        meta, body = extract_frontmatter(content)
        # YAML spec: trailing spaces are part of scalar unless quoted
        assert meta["title"] == "Hello"
        assert meta["phase"] == "01"

    def test_trailing_whitespace_after_closing_delimiter(self):
        """Trailing whitespace after the closing --- should not prevent matching.

        Note: the regex requires exactly ``---`` at the start of a line followed
        by \\r?\\n or end-of-string, so trailing spaces break the match.
        This tests the actual behavior.
        """
        content = "---\ntitle: Hello\n---   \n\nBody."
        meta, body = extract_frontmatter(content)
        # The regex won't match because of trailing spaces after ---
        # So this falls through to "no frontmatter"
        assert meta == {}
        assert "---" in body

    def test_trailing_whitespace_after_opening_delimiter(self):
        """Trailing whitespace after opening --- breaks the regex too."""
        content = "---   \ntitle: Hello\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        # Opening delimiter must be exactly '---' at start of string
        assert meta == {}

    def test_tabs_in_yaml_values_raise(self):
        """YAML forbids literal tab characters in flow content; this should raise."""
        content = "---\ntitle: Hello\tWorld\n---\n\nBody."
        with pytest.raises(FrontmatterParseError):
            extract_frontmatter(content)

    def test_blank_lines_inside_frontmatter(self):
        content = "---\ntitle: Hello\n\nauthor: World\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["title"] == "Hello"
        assert meta["author"] == "World"


# ---------------------------------------------------------------------------
# Duplicate keys
# ---------------------------------------------------------------------------


class TestDuplicateKeys:
    """YAML spec says duplicate keys are allowed; last value wins."""

    def test_duplicate_keys_last_wins(self):
        content = "---\ntitle: First\ntitle: Second\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        # PyYAML safe_load: last value wins for duplicate keys
        assert meta["title"] == "Second"

    def test_duplicate_keys_different_types(self):
        content = "---\nval: 42\nval: hello\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["val"] == "hello"

    def test_duplicate_nested_keys(self):
        content = "---\nouter:\n  key: first\n  key: second\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["outer"]["key"] == "second"


# ---------------------------------------------------------------------------
# Very long values
# ---------------------------------------------------------------------------


class TestVeryLongValues:
    """Frontmatter with extremely long string values."""

    def test_long_string_value_10000_chars(self):
        long_val = "x" * 10_000
        content = f"---\ntitle: {long_val}\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["title"] == long_val
        assert "Body." in body

    def test_long_value_roundtrip(self):
        long_val = "y" * 10_000
        meta = {"description": long_val}
        body = "Body text."
        result = reconstruct_frontmatter(meta, body)
        meta2, body2 = extract_frontmatter(result)
        assert meta2["description"] == long_val
        assert "Body text." in body2

    def test_long_value_splice(self):
        long_val = "z" * 10_000
        content = "---\ntitle: short\n---\n\nBody."
        result = splice_frontmatter(content, {"title": long_val})
        meta, _ = extract_frontmatter(result)
        assert meta["title"] == long_val

    def test_many_keys(self):
        """Frontmatter with a large number of distinct keys."""
        lines = [f"key_{i}: value_{i}" for i in range(200)]
        yaml_block = "\n".join(lines)
        content = f"---\n{yaml_block}\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert len(meta) == 200
        assert meta["key_0"] == "value_0"
        assert meta["key_199"] == "value_199"
        assert "Body." in body


# ---------------------------------------------------------------------------
# Null / None values
# ---------------------------------------------------------------------------


class TestNullValues:
    """Frontmatter fields with YAML null/None values."""

    def test_explicit_null(self):
        content = "---\nphase: null\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"phase": None}

    def test_tilde_null(self):
        """YAML also treats ~ as null."""
        content = "---\nphase: ~\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"phase": None}

    def test_empty_value_is_null(self):
        """A key with no value in YAML is None."""
        content = "---\nphase:\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"phase": None}

    def test_all_null_frontmatter(self):
        """When every key is null, safe_load returns a dict with None values (not empty)."""
        content = "---\na: null\nb: ~\nc:\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"a": None, "b": None, "c": None}
        assert "Body." in body

    def test_null_value_roundtrip(self):
        meta = {"phase": None, "title": "test"}
        body = "Body."
        result = reconstruct_frontmatter(meta, body)
        meta2, _ = extract_frontmatter(result)
        assert meta2["phase"] is None
        assert meta2["title"] == "test"

    def test_splice_null_value(self):
        content = "---\ntitle: Hello\n---\n\nBody."
        result = splice_frontmatter(content, {"title": None})
        meta, _ = extract_frontmatter(result)
        assert meta["title"] is None


# ---------------------------------------------------------------------------
# Boolean values (true/false/yes/no)
# ---------------------------------------------------------------------------


class TestBooleanValues:
    """YAML boolean handling: true/false/yes/no/on/off."""

    def test_true_false(self):
        content = "---\ninteractive: true\nblocked: false\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["interactive"] is True
        assert meta["blocked"] is False

    def test_yes_no(self):
        """YAML 1.1 treats yes/no as booleans."""
        content = "---\ninteractive: yes\nblocked: no\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["interactive"] is True
        assert meta["blocked"] is False

    def test_on_off(self):
        """YAML 1.1 treats on/off as booleans."""
        content = "---\nflag_a: on\nflag_b: off\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["flag_a"] is True
        assert meta["flag_b"] is False

    def test_capitalized_booleans(self):
        content = "---\na: True\nb: False\nc: Yes\nd: No\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["a"] is True
        assert meta["b"] is False
        assert meta["c"] is True
        assert meta["d"] is False

    def test_boolean_roundtrip(self):
        meta = {"interactive": True, "blocked": False}
        body = "Body."
        result = reconstruct_frontmatter(meta, body)
        meta2, _ = extract_frontmatter(result)
        assert meta2["interactive"] is True
        assert meta2["blocked"] is False

    def test_quoted_booleans_are_strings(self):
        """Quoted yes/no/true/false should remain strings."""
        content = "---\nval1: 'true'\nval2: 'false'\nval3: 'yes'\nval4: 'no'\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["val1"] == "true"
        assert meta["val2"] == "false"
        assert meta["val3"] == "yes"
        assert meta["val4"] == "no"


# ---------------------------------------------------------------------------
# Empty file (0 bytes)
# ---------------------------------------------------------------------------


class TestEmptyFile:
    """Handling of completely empty input."""

    def test_empty_string(self):
        meta, body = extract_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_empty_string_splice(self):
        result = splice_frontmatter("", {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"

    def test_empty_string_deep_merge(self):
        result = deep_merge_frontmatter("", {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"

    def test_whitespace_only_content(self):
        meta, body = extract_frontmatter("   \n\n  \n")
        assert meta == {}

    def test_newline_only(self):
        meta, body = extract_frontmatter("\n")
        assert meta == {}
        assert body == "\n"

    def test_bom_only(self):
        """A file containing only a BOM and nothing else."""
        meta, body = extract_frontmatter("\ufeff")
        assert meta == {}
        assert body == ""


# ---------------------------------------------------------------------------
# Empty frontmatter (---\n---\n)
# ---------------------------------------------------------------------------


class TestEmptyFrontmatter:
    """The degenerate case: opening and closing delimiters with nothing between."""

    def test_empty_frontmatter_returns_empty_dict(self):
        content = "---\n---\n"
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert body == ""

    def test_empty_frontmatter_with_body(self):
        content = "---\n---\n\nBody text."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body text." in body

    def test_empty_frontmatter_no_trailing_newline(self):
        content = "---\n---"
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert body == ""

    def test_empty_frontmatter_crlf(self):
        content = "---\r\n---\r\n\r\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body." in body

    def test_splice_into_empty_frontmatter(self):
        content = "---\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert "Body." in body
        # Should not duplicate delimiters
        assert result.count("---") == 2

    def test_reconstruct_empty_meta(self):
        result = reconstruct_frontmatter({}, "Body.")
        # Even with empty meta, we get delimiters
        assert result.startswith("---\n")
        assert "\n---\n" in result
        meta, body = extract_frontmatter(result)
        assert "Body." in body


# ---------------------------------------------------------------------------
# Nested frontmatter delimiters (--- inside code blocks)
# ---------------------------------------------------------------------------


class TestNestedDelimiters:
    """Ensure --- inside fenced code blocks doesn't confuse the parser.

    Note: the frontmatter regex is anchored at ^ (start of string), so
    a --- appearing later in the document body won't be treated as a
    second frontmatter block. But we test that the body is preserved intact.
    """

    def test_triple_dash_in_body_preserved(self):
        content = "---\ntitle: Hello\n---\n\n---\nThis is not frontmatter.\n---\n"
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello"}
        assert "---" in body
        assert "This is not frontmatter." in body

    def test_code_block_with_frontmatter_like_content(self):
        body_text = (
            "```markdown\n"
            "---\n"
            "title: Fake\n"
            "---\n"
            "```\n"
        )
        content = f"---\ntitle: Real\n---\n\n{body_text}"
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Real"}
        assert "Fake" in body
        assert "```" in body

    def test_yaml_code_block_in_body(self):
        body_text = (
            "```yaml\n"
            "---\n"
            "key: value\n"
            "---\n"
            "```\n"
        )
        content = f"---\ntitle: Actual\n---\n\n{body_text}"
        meta, body = extract_frontmatter(content)
        assert meta["title"] == "Actual"
        assert "key: value" in body

    def test_no_frontmatter_but_code_block_has_dashes(self):
        """If there's no real frontmatter, a code block with --- shouldn't be parsed."""
        content = "Some text.\n\n```\n---\ntitle: NotMeta\n---\n```\n"
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_splice_preserves_body_with_dashes(self):
        content = "---\ntitle: Old\n---\n\nBody with --- inside."
        result = splice_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert "---" in body


# ---------------------------------------------------------------------------
# Additional edge cases (mixed / regression)
# ---------------------------------------------------------------------------


class TestMiscEdgeCases:
    """Grab-bag of additional edge cases."""

    def test_unicode_values(self):
        content = "---\ntitle: Schrodinger's cat\nauthor: \u00e9\u00e8\u00ea\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["title"] == "Schrodinger's cat"
        assert meta["author"] == "\u00e9\u00e8\u00ea"

    def test_unicode_roundtrip(self):
        meta = {"title": "\u2603 Snowman", "tags": ["\u2764", "\u2728"]}
        body = "Body with \u00fc\u00e4\u00f6."
        result = reconstruct_frontmatter(meta, body)
        meta2, body2 = extract_frontmatter(result)
        assert meta2["title"] == "\u2603 Snowman"
        assert meta2["tags"] == ["\u2764", "\u2728"]

    def test_numeric_string_phase(self):
        """Phase '01' should stay a string when quoted."""
        content = "---\nphase: '01'\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["phase"] == "01"
        assert isinstance(meta["phase"], str)

    def test_unquoted_numeric_phase(self):
        """Unquoted 01 is parsed as integer 1 by YAML."""
        content = "---\nphase: 01\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["phase"] == 1

    def test_multiline_yaml_literal_block(self):
        content = "---\ndescription: |\n  Line one.\n  Line two.\n  Line three.\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert "Line one." in meta["description"]
        assert "Line two." in meta["description"]
        assert "Line three." in meta["description"]

    def test_multiline_yaml_folded_block(self):
        content = "---\ndescription: >\n  This is a\n  folded block.\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert "This is a" in meta["description"]
        assert "folded block." in meta["description"]

    def test_special_yaml_characters_in_values(self):
        """Colons, brackets, braces in values should be handled."""
        content = "---\ntitle: 'Value: with [special] {chars}'\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["title"] == "Value: with [special] {chars}"

    def test_extract_then_reconstruct_preserves_meta(self):
        """Extracting and reconstructing should preserve metadata faithfully."""
        original_meta = {"title": "Test", "phase": "01", "tags": ["a", "b"]}
        original_body = "Body text here."
        content = reconstruct_frontmatter(original_meta, original_body)

        meta, body = extract_frontmatter(content)
        content2 = reconstruct_frontmatter(meta, body)
        meta2, body2 = extract_frontmatter(content2)

        assert meta == meta2
        # Note: reconstruct adds \n\n between --- and body, so each
        # roundtrip accumulates one extra leading newline in the body.
        # The metadata is perfectly preserved.
        assert body2.strip() == body.strip()

    def test_splice_into_content_with_only_body(self):
        content = "Just a plain document with no frontmatter at all."
        result = splice_frontmatter(content, {"added": True})
        meta, body = extract_frontmatter(result)
        assert meta["added"] is True
        assert "Just a plain document" in body

    def test_deep_merge_into_content_with_no_frontmatter(self):
        content = "No frontmatter here."
        result = deep_merge_frontmatter(content, {"new_key": "new_val"})
        meta, body = extract_frontmatter(result)
        assert meta["new_key"] == "new_val"
        assert "No frontmatter here." in body

    def test_frontmatter_with_comments(self):
        """YAML comments should be ignored during parsing."""
        content = "---\n# This is a comment\ntitle: Hello\n# Another comment\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello"}

    def test_frontmatter_with_anchors_and_aliases(self):
        """YAML anchors and aliases within frontmatter."""
        content = "---\ndefault: &default\n  color: red\ncustom:\n  <<: *default\n  size: large\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["custom"]["color"] == "red"
        assert meta["custom"]["size"] == "large"

    def test_date_values(self):
        """YAML parses unquoted dates as datetime.date objects."""
        content = "---\ncompleted: 2025-01-15\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        # PyYAML safe_load parses YYYY-MM-DD as datetime.date
        from datetime import date
        assert meta["completed"] == date(2025, 1, 15)

    def test_quoted_date_stays_string(self):
        content = "---\ncompleted: '2025-01-15'\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["completed"] == "2025-01-15"
        assert isinstance(meta["completed"], str)
