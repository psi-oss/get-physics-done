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


# ---------------------------------------------------------------------------
# Edge cases: splice / deep_merge with empty frontmatter (regression tests)
# ---------------------------------------------------------------------------


class TestSpliceEmptyFrontmatter:
    """Regression: splice/deep_merge must replace (not duplicate) empty ``---\\n---`` blocks."""

    def test_splice_replaces_empty_frontmatter(self):
        content = "---\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "Added"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "Added"
        assert "Body." in body
        # Must NOT contain duplicate --- delimiters
        assert result.count("---") == 2

    def test_splice_replaces_empty_frontmatter_with_blank_line(self):
        content = "---\n\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "Added"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "Added"
        assert "Body." in body
        assert result.count("---") == 2

    def test_deep_merge_replaces_empty_frontmatter(self):
        content = "---\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"title": "Added"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "Added"
        assert "Body." in body
        assert result.count("---") == 2

    def test_splice_crlf_empty_frontmatter(self):
        content = "---\r\n---\r\n\r\nBody."
        result = splice_frontmatter(content, {"title": "Added"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "Added"
        assert "\r\n" in result
        assert "Body." in body


class TestDeepMergeShallowSemantics:
    """Verify that deep_merge only merges one level of nested dicts."""

    def test_nested_dict_values_are_overwritten_not_merged(self):
        content = "---\nouter:\n  inner:\n    a: 1\n    b: 2\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"outer": {"inner": {"a": 3, "c": 4}}})
        meta, _ = extract_frontmatter(result)
        # outer.inner is replaced entirely because the merge is only 1-level deep on 'outer'
        assert meta["outer"]["inner"] == {"a": 3, "c": 4}

    def test_list_value_overwrites(self):
        content = "---\ntags:\n  - old\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"tags": ["new"]})
        meta, _ = extract_frontmatter(result)
        assert meta["tags"] == ["new"]


# ---------------------------------------------------------------------------
# extract_frontmatter additional edge cases
# ---------------------------------------------------------------------------


class TestExtractFrontmatterEdgeCases:
    def test_empty_string(self):
        meta, body = extract_frontmatter("")
        assert meta == {}
        assert body == ""

    def test_crlf_line_endings(self):
        content = "---\r\ntitle: Hello\r\n---\r\n\r\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello"}
        assert "Body." in body

    def test_frontmatter_only_no_trailing_newline(self):
        content = "---\ntitle: test\n---"
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "test"}
        assert body == ""

    def test_yaml_with_boolean_values(self):
        content = "---\nautonomous: true\nblocked: false\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["autonomous"] is True
        assert meta["blocked"] is False

    def test_yaml_with_integer_values(self):
        content = "---\nwave: 1\nscore: 42\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["wave"] == 1
        assert isinstance(meta["wave"], int)

    def test_yaml_with_null_value(self):
        content = "---\nphase: null\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        # yaml.safe_load parses 'null' as None; the or {} fallback only applies
        # when the entire document is None, not individual fields
        assert meta == {"phase": None}

    def test_whitespace_only_yaml(self):
        content = "---\n  \n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body." in body

    def test_bom_with_empty_frontmatter(self):
        content = "\ufeff---\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta == {}
        assert "Body." in body


# ---------------------------------------------------------------------------
# verify_commits
# ---------------------------------------------------------------------------


class TestVerifyCommits:
    def test_empty_hashes_raises(self):
        from pathlib import Path

        from gpd.core.frontmatter import FrontmatterValidationError, verify_commits

        with pytest.raises(FrontmatterValidationError, match="At least one"):
            verify_commits(Path("."), [])

    def test_invalid_hashes(self, tmp_path):
        from gpd.core.frontmatter import verify_commits

        # Use tmp_path (not a git repo) so all hashes are invalid
        result = verify_commits(tmp_path, ["0000000"])
        assert result.all_valid is False
        assert "0000000" in result.invalid_hashes
        assert result.total == 1


# ---------------------------------------------------------------------------
# verify_references
# ---------------------------------------------------------------------------


class TestVerifyReferences:
    def test_file_not_found(self, tmp_path):
        from pathlib import Path

        from gpd.core.frontmatter import verify_references

        result = verify_references(tmp_path, Path("nonexistent.md"))
        assert result.valid is False

    def test_no_references_in_content(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("No file refs here.\n")
        result = verify_references(tmp_path, f)
        assert result.valid is True
        assert result.total == 0

    def test_backtick_ref_found(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hi')")
        f = tmp_path / "test.md"
        f.write_text("See `src/main.py` for details.\n")
        result = verify_references(tmp_path, f)
        assert result.valid is True
        assert result.found == 1

    def test_backtick_ref_missing(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("See `src/missing.py` for details.\n")
        result = verify_references(tmp_path, f)
        assert result.valid is False
        assert "src/missing.py" in result.missing

    def test_at_ref_found(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "README.md").write_text("# Docs")
        f = tmp_path / "test.md"
        f.write_text("@docs/README.md\n")
        result = verify_references(tmp_path, f)
        assert result.valid is True
        assert result.found == 1

    def test_http_urls_skipped(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("See `http://example.com/foo.py`.\n")
        result = verify_references(tmp_path, f)
        assert result.total == 0

    def test_template_vars_skipped(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("Use `${PROJECT}/src/foo.py` or `{{base}}/bar.py`.\n")
        result = verify_references(tmp_path, f)
        assert result.total == 0


# ---------------------------------------------------------------------------
# verify_artifacts
# ---------------------------------------------------------------------------


class TestVerifyArtifacts:
    def test_plan_not_found(self, tmp_path):
        from pathlib import Path

        from gpd.core.frontmatter import verify_artifacts

        result = verify_artifacts(tmp_path, Path("nonexistent.md"))
        assert result.all_passed is False

    def test_no_artifacts_block(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        f = tmp_path / "plan.md"
        f.write_text("---\ntitle: test\n---\n\nNo artifacts.\n")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False
        assert result.total == 0

    def test_string_artifact_exists(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "output.txt").write_text("result")
        f = tmp_path / "plan.md"
        f.write_text("---\nmust_haves:\n  artifacts:\n    - output.txt\n---\n\nBody.\n")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True
        assert result.passed_count == 1

    def test_string_artifact_missing(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        f = tmp_path / "plan.md"
        f.write_text("---\nmust_haves:\n  artifacts:\n    - missing.txt\n---\n\nBody.\n")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False

    def test_dict_artifact_with_min_lines(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "data.csv").write_text("a\nb\nc\n")
        f = tmp_path / "plan.md"
        content = "---\nmust_haves:\n  artifacts:\n    - path: data.csv\n      min_lines: 2\n---\n\nBody.\n"
        f.write_text(content)
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True

    def test_dict_artifact_min_lines_too_few(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "data.csv").write_text("a\n")
        f = tmp_path / "plan.md"
        content = "---\nmust_haves:\n  artifacts:\n    - path: data.csv\n      min_lines: 100\n---\n\nBody.\n"
        f.write_text(content)
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False
        assert any("lines" in i for a in result.artifacts for i in a.issues)

    def test_dict_artifact_contains_check(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "output.py").write_text("def main():\n    pass\n")
        f = tmp_path / "plan.md"
        content = "---\nmust_haves:\n  artifacts:\n    - path: output.py\n      contains: def main\n---\n\nBody.\n"
        f.write_text(content)
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True


# ---------------------------------------------------------------------------
# verify_key_links
# ---------------------------------------------------------------------------


class TestVerifyKeyLinks:
    def test_plan_not_found(self, tmp_path):
        from pathlib import Path

        from gpd.core.frontmatter import verify_key_links

        result = verify_key_links(tmp_path, Path("nonexistent.md"))
        assert result.all_verified is False

    def test_no_key_links(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        f = tmp_path / "plan.md"
        f.write_text("---\ntitle: test\n---\n\nNo key links.\n")
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is False
        assert result.total == 0

    def test_string_key_link_exists(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        (tmp_path / "linked.md").write_text("# Linked")
        f = tmp_path / "plan.md"
        f.write_text("---\nmust_haves:\n  key_links:\n    - linked.md\n---\n\nBody.\n")
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is True
        assert result.verified_count == 1

    def test_string_key_link_missing(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        f = tmp_path / "plan.md"
        f.write_text("---\nmust_haves:\n  key_links:\n    - missing.md\n---\n\nBody.\n")
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is False

    def test_dict_link_target_referenced_in_source(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        (tmp_path / "source.py").write_text("import target_module  # see target.py\n")
        (tmp_path / "target.py").write_text("# target\n")
        f = tmp_path / "plan.md"
        content = "---\nmust_haves:\n  key_links:\n    - from: source.py\n      to: target.py\n---\n\nBody.\n"
        f.write_text(content)
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is True

    def test_dict_link_with_regex_pattern(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        (tmp_path / "source.py").write_text("from target import func\n")
        (tmp_path / "target.py").write_text("def func(): pass\n")
        f = tmp_path / "plan.md"
        content = (
            "---\n"
            "must_haves:\n"
            "  key_links:\n"
            "    - from: source.py\n"
            "      to: target.py\n"
            "      pattern: 'from target import'\n"
            "---\n\nBody.\n"
        )
        f.write_text(content)
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is True

    def test_unsafe_regex_rejected(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        (tmp_path / "source.py").write_text("content\n")
        (tmp_path / "target.py").write_text("content\n")
        f = tmp_path / "plan.md"
        # Use a pattern with adjacent quantifiers (e.g. a++) that the safety check detects
        content = (
            "---\n"
            "must_haves:\n"
            "  key_links:\n"
            "    - from: source.py\n"
            "      to: target.py\n"
            "      pattern: 'a++b'\n"
            "---\n\nBody.\n"
        )
        f.write_text(content)
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is False
        assert "Unsafe regex" in result.links[0].detail

    def test_malformed_link_missing_fields(self, tmp_path):
        from gpd.core.frontmatter import verify_key_links

        f = tmp_path / "plan.md"
        content = "---\nmust_haves:\n  key_links:\n    - from: source.py\n---\n\nBody.\n"
        f.write_text(content)
        result = verify_key_links(tmp_path, f)
        assert result.all_verified is False
        assert "Malformed" in result.links[0].detail


# ---------------------------------------------------------------------------
# verify_plan_structure
# ---------------------------------------------------------------------------


class TestVerifyPlanStructure:
    def test_file_not_found(self, tmp_path):
        from pathlib import Path

        from gpd.core.frontmatter import verify_plan_structure

        result = verify_plan_structure(tmp_path, Path("nonexistent.md"))
        assert result.valid is False
        assert any("not found" in e.lower() for e in result.errors)

    def test_valid_plan_with_tasks(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

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
            "---\n\n"
            '<task type="code">\n'
            "  <name>Implement feature</name>\n"
            "  <files>src/main.py</files>\n"
            "  <action>Write the code</action>\n"
            "  <verify>Run tests</verify>\n"
            "  <done>Tests pass</done>\n"
            "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is True
        assert result.task_count == 1
        assert result.tasks[0].name == "Implement feature"
        assert result.tasks[0].has_action is True

    def test_missing_frontmatter_fields(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        f = tmp_path / "plan.md"
        f.write_text("---\nphase: 01-test\n---\n\nBody.\n")
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is False
        assert any("Missing required" in e for e in result.errors)

    def test_task_missing_name(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 1\n"
            "depends_on: []\nfiles_modified: []\nautonomous: true\nmust_haves: {}\n"
            "---\n\n"
            '<task type="code">\n'
            "  <action>Do something</action>\n"
            "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert any("missing <name>" in e for e in result.errors)

    def test_wave_gt1_empty_deps_warns(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 2\n"
            "depends_on: []\nfiles_modified: []\nautonomous: true\nmust_haves: {}\n"
            "---\n\nBody.\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert any("Wave > 1" in w for w in result.warnings)

    def test_checkpoint_autonomous_mismatch(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 1\n"
            "depends_on: []\nfiles_modified: []\nautonomous: true\nmust_haves: {}\n"
            "---\n\n"
            '<task type="checkpoint">\n'
            "  <name>Review</name>\n"
            "  <action>Review code</action>\n"
            "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert any("checkpoint" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# select_template
# ---------------------------------------------------------------------------


class TestSelectTemplate:
    def test_plan_not_found_raises(self, tmp_path):
        from pathlib import Path

        from gpd.core.frontmatter import FrontmatterValidationError, select_template

        with pytest.raises(FrontmatterValidationError, match="not found"):
            select_template(tmp_path, Path("nonexistent.md"))

    def test_minimal_selection(self, tmp_path):
        from gpd.core.frontmatter import select_template

        f = tmp_path / "plan.md"
        f.write_text("---\ntitle: test\n---\n\n### Task 1\nDo stuff.\n")
        result = select_template(tmp_path, f)
        assert result.template_type == "minimal"
        assert result.task_count == 1

    def test_complex_selection_many_tasks(self, tmp_path):
        from gpd.core.frontmatter import select_template

        tasks = "\n".join(f"### Task {i}\nDo stuff {i}.\n" for i in range(1, 8))
        f = tmp_path / "plan.md"
        f.write_text(f"---\ntitle: test\n---\n\n{tasks}")
        result = select_template(tmp_path, f)
        assert result.template_type == "complex"

    def test_complex_selection_decisions(self, tmp_path):
        from gpd.core.frontmatter import select_template

        f = tmp_path / "plan.md"
        f.write_text("---\ntitle: test\n---\n\nWe need to make a Decision here.\n")
        result = select_template(tmp_path, f)
        assert result.template_type == "complex"

    def test_standard_selection(self, tmp_path):
        from gpd.core.frontmatter import select_template

        tasks = "\n".join(f"### Task {i}\nUse `src/mod{i}.py`.\n" for i in range(1, 4))
        f = tmp_path / "plan.md"
        f.write_text(f"---\ntitle: test\n---\n\n{tasks}")
        result = select_template(tmp_path, f)
        assert result.template_type == "standard"
