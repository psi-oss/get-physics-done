"""Tests for gpd.core.frontmatter — YAML frontmatter CRUD + validation."""

from __future__ import annotations

import pytest

from gpd.core.frontmatter import (
    FrontmatterParseError,
    FrontmatterValidation,
    FrontmatterValidationError,
    deep_merge_frontmatter,
    extract_frontmatter,
    parse_must_haves_block,
    reconstruct_frontmatter,
    splice_frontmatter,
    validate_frontmatter,
)

# ---------------------------------------------------------------------------
# extract_frontmatter
# ---------------------------------------------------------------------------


class TestExtractFrontmatter:
    def test_basic_extraction(self):
        content = "---\ntitle: Hello\nphase: '01'\n---\n\nBody text here."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello", "phase": "01"}
        assert "Body text here." in body

    def test_no_frontmatter(self):
        content = "Just plain text, no YAML."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_empty_frontmatter(self):
        content = "---\n---\n\nBody after empty block."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body after empty block." in body

    def test_bom_stripped(self):
        content = "\ufeff---\nkey: value\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"key": "value"}

    def test_malformed_yaml_raises(self):
        content = "---\n: invalid: yaml: [unclosed\n---\n\nBody."
        with pytest.raises(FrontmatterParseError):
            extract_frontmatter(content)

    def test_non_dict_yaml_raises(self):
        content = "---\n- item1\n- item2\n---\n\nBody."
        with pytest.raises(FrontmatterParseError, match="Expected mapping"):
            extract_frontmatter(content)

    def test_multiline_values(self):
        content = "---\ntitle: Hello World\ndescription: A long description\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["title"] == "Hello World"
        assert meta["description"] == "A long description"

    def test_nested_dict(self):
        content = "---\nmust_haves:\n  truths:\n    - truth1\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["must_haves"]["truths"] == ["truth1"]


# ---------------------------------------------------------------------------
# reconstruct_frontmatter
# ---------------------------------------------------------------------------


class TestReconstructFrontmatter:
    def test_roundtrip(self):
        meta = {"title": "Test", "phase": "01"}
        body = "Some body text."
        result = reconstruct_frontmatter(meta, body)
        assert result.startswith("---\n")
        assert "title: Test" in result
        assert result.endswith("Some body text.")

    def test_empty_meta(self):
        result = reconstruct_frontmatter({}, "Body.")
        assert "---\n" in result
        assert "Body." in result


# ---------------------------------------------------------------------------
# splice_frontmatter
# ---------------------------------------------------------------------------


class TestSpliceFrontmatter:
    def test_update_existing_field(self):
        content = "---\ntitle: Old\nphase: '01'\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert meta["phase"] == "01"
        assert "Body." in body

    def test_add_new_field(self):
        content = "---\ntitle: Hello\n---\n\nBody."
        result = splice_frontmatter(content, {"author": "Test"})
        meta, _ = extract_frontmatter(result)
        assert meta["author"] == "Test"
        assert meta["title"] == "Hello"

    def test_no_existing_frontmatter(self):
        content = "Just text, no frontmatter."
        result = splice_frontmatter(content, {"title": "Added"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "Added"
        assert "Just text, no frontmatter." in body

    def test_crlf_preservation(self):
        content = "---\r\ntitle: Old\r\n---\r\n\r\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        assert "\r\n" in result


# ---------------------------------------------------------------------------
# deep_merge_frontmatter
# ---------------------------------------------------------------------------


class TestDeepMergeFrontmatter:
    def test_merge_nested_dicts(self):
        content = "---\nmethods:\n  added:\n    - foo\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"methods": {"patterns": ["bar"]}})
        meta, _ = extract_frontmatter(result)
        assert meta["methods"]["added"] == ["foo"]
        assert meta["methods"]["patterns"] == ["bar"]

    def test_overwrite_non_dict(self):
        content = "---\ntitle: Old\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"title": "New"})
        meta, _ = extract_frontmatter(result)
        assert meta["title"] == "New"

    def test_add_new_key(self):
        content = "---\ntitle: Hello\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"status": "done"})
        meta, _ = extract_frontmatter(result)
        assert meta["status"] == "done"
        assert meta["title"] == "Hello"


# ---------------------------------------------------------------------------
# parse_must_haves_block
# ---------------------------------------------------------------------------


class TestParseMustHavesBlock:
    def test_extract_truths(self):
        content = "---\nmust_haves:\n  truths:\n    - truth1\n    - truth2\n---\n\nBody."
        result = parse_must_haves_block(content, "truths")
        assert result == ["truth1", "truth2"]

    def test_hyphenated_key(self):
        content = "---\nmust-haves:\n  artifacts:\n    - art1\n---\n\nBody."
        result = parse_must_haves_block(content, "artifacts")
        assert result == ["art1"]

    def test_missing_block(self):
        content = "---\ntitle: Hello\n---\n\nBody."
        result = parse_must_haves_block(content, "truths")
        assert result == []

    def test_non_list_block(self):
        content = "---\nmust_haves:\n  truths: not_a_list\n---\n\nBody."
        result = parse_must_haves_block(content, "truths")
        assert result == []

    def test_no_frontmatter(self):
        result = parse_must_haves_block("No frontmatter here.", "truths")
        assert result == []


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_plan(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "autonomous: true\n"
            "must_haves: {}\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert isinstance(result, FrontmatterValidation)
        assert result.valid is True
        assert result.missing == []

    def test_missing_fields(self):
        content = "---\nphase: 01-test\n---\n\nBody."
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert len(result.missing) > 0
        assert "phase" not in result.missing
        assert "plan" in result.missing

    def test_hyphen_case_accepted(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends-on: []\n"
            "files-modified: []\n"
            "autonomous: true\n"
            "must-haves: {}\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is True

    def test_valid_summary(self):
        content = "---\nphase: 01\nplan: 01\ndepth: standard\nprovides: []\ncompleted: 2025-01-01\n---\n\nBody."
        result = validate_frontmatter(content, "summary")
        assert result.valid is True

    def test_valid_verification(self):
        content = "---\nphase: 01\nverified: 2025-01-01\nstatus: passed\nscore: 5/5\n---\n\nBody."
        result = validate_frontmatter(content, "verification")
        assert result.valid is True

    def test_unknown_schema_raises(self):
        with pytest.raises(FrontmatterValidationError, match="Unknown schema"):
            validate_frontmatter("---\nfoo: bar\n---\n", "nonexistent")

    def test_malformed_yaml_raises(self):
        with pytest.raises(FrontmatterParseError):
            validate_frontmatter("---\n: bad: yaml: [\n---\n", "plan")
