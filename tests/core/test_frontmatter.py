"""Tests for gpd.core.frontmatter — YAML frontmatter CRUD + validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.frontmatter import (
    FrontmatterParseError,
    FrontmatterValidation,
    FrontmatterValidationError,
    deep_merge_frontmatter,
    extract_frontmatter,
    parse_contract_block,
    parse_must_haves_block,
    reconstruct_frontmatter,
    splice_frontmatter,
    validate_frontmatter,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"

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

    def test_hyphenated_key_returns_empty(self):
        content = "---\nmust-haves:\n  artifacts:\n    - art1\n---\n\nBody."
        result = parse_must_haves_block(content, "artifacts")
        assert result == []

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

    def test_derives_must_haves_from_contract(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What is the main benchmark?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-figure]\n"
            "  deliverables:\n"
            "    - id: deliv-figure\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main benchmark figure\n"
            "  acceptance_tests:\n"
            "    - id: test-benchmark\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against reference\n"
            "      pass_condition: Matches benchmark within tolerance\n"
            "---\n\nBody."
        )
        assert parse_must_haves_block(content, "truths") == ["Recover the benchmark value"]
        artifacts = parse_must_haves_block(content, "artifacts")
        assert artifacts == [
            {
                "path": "figures/main.png",
                "provides": "Main benchmark figure",
                "physics_check": "Matches benchmark within tolerance",
            }
        ]


class TestParseContractBlock:
    def test_returns_valid_contract_from_fixture(self):
        fixture = FIXTURES_DIR / "plan_with_contract.md"
        content = fixture.read_text(encoding="utf-8")
        contract = parse_contract_block(content)
        assert contract is not None
        assert contract.scope.question == "What benchmark must this plan recover?"

    def test_invalid_contract_raises(self):
        content = (
            "---\n"
            "contract:\n"
            "  scope:\n"
            "    in_scope: [benchmark]\n"
            "---\n\nBody."
        )
        with pytest.raises(FrontmatterValidationError, match="Invalid contract frontmatter"):
            parse_contract_block(content)

    def test_semantically_incomplete_contract_raises(self):
        content = (
            "---\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "---\n\nBody."
        )
        with pytest.raises(FrontmatterValidationError, match="missing acceptance_tests"):
            parse_contract_block(content)


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_plan(self):
        content = (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8")
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

    def test_hyphen_case_rejected(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends-on: []\n"
            "files-modified: []\n"
            "interactive: false\n"
            "contract: {}\n"
            "must-haves: {}\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert "depends_on" in result.missing
        assert "files_modified" in result.missing
        assert result.errors

    def test_valid_summary(self):
        content = "---\nphase: 01\nplan: 01\ndepth: standard\nprovides: []\ncompleted: 2025-01-01\n---\n\nBody."
        result = validate_frontmatter(content, "summary")
        assert result.valid is True

    def test_valid_plan_with_contract_only(self):
        content = (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8")
        result = validate_frontmatter(content, "plan")
        assert result.valid is True
        assert result.errors == []
        assert "must_haves" not in result.missing

    def test_plan_without_contract_is_invalid(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "must_haves: {}\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert "contract" in result.missing

    def test_invalid_contract_marks_plan_invalid(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    in_scope: [benchmark]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert result.errors

    def test_incomplete_plan_contract_marks_plan_invalid(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert any("missing acceptance_tests" in error for error in result.errors)
        assert any("missing references" in error for error in result.errors)
        assert any("missing forbidden_proxies" in error for error in result.errors)
        assert any("missing uncertainty_markers.disconfirming_observations" in error for error in result.errors)

    def test_incomplete_plan_contract_requires_must_surface_anchor(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-main]\n"
            "      required_actions: [read, compare]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches benchmark within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match\n"
            "      reason: Not decisive\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark mismatch after normalization fix]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert any("must_surface=true" in error for error in result.errors)

    def test_incomplete_plan_contract_requires_must_surface_anchor_metadata(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      must_surface: true\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches benchmark within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match\n"
            "      reason: Not decisive\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark mismatch after normalization fix]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert any("missing required_actions" in error for error in result.errors)
        assert any("missing applies_to" in error for error in result.errors)

    def test_incomplete_plan_contract_rejects_unknown_must_read_ref(self):
        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake:\n"
            "    must_read_refs: [ref-missing]\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-main]\n"
            "      must_surface: true\n"
            "      required_actions: [read, compare]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches benchmark within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match\n"
            "      reason: Not decisive\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark mismatch after normalization fix]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert any("must_read_refs references unknown reference ref-missing" in error for error in result.errors)

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
        content = "---\ninteractive: true\nblocked: false\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["interactive"] is True
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
        assert result.all_passed is True
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
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value within tolerance\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main benchmark figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-main]\n"
            "      must_surface: true\n"
            "      required_actions: [read, compare, cite]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match without numerical comparison\n"
            "      reason: Would allow false progress without the decisive benchmark\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
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
            "depends_on: []\nfiles_modified: []\ncontract: {}\ninteractive: false\nmust_haves: {}\n"
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
            "depends_on: []\nfiles_modified: []\ncontract: {}\ninteractive: false\nmust_haves: {}\n"
            "---\n\nBody.\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert any("Wave > 1" in w for w in result.warnings)

    def test_checkpoint_interactive_mismatch(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 1\n"
            "depends_on: []\nfiles_modified: []\ncontract: {}\ninteractive: false\nmust_haves: {}\n"
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

    def test_interactive_without_checkpoint_mismatch(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 1\n"
            "depends_on: []\nfiles_modified: []\ncontract: {}\ninteractive: true\nmust_haves: {}\n"
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
        assert any("interactive is true" in e for e in result.errors)

    def test_incomplete_contract_is_reported(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 1\n"
            "depends_on: []\nfiles_modified: []\ninteractive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "---\n\n"
            '<task type="code">\n'
            "  <name>Implement feature</name>\n"
            "  <action>Write the code</action>\n"
            "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is False
        assert any("Invalid contract: missing acceptance_tests" in error for error in result.errors)

    def test_warns_when_must_haves_drift_from_contract(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value within tolerance\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main benchmark figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-main]\n"
            "      must_surface: true\n"
            "      required_actions: [read, compare, cite]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match without numerical comparison\n"
            "      reason: Would allow false progress without the decisive benchmark\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
            "must_haves:\n"
            "  truths: [Wrong compatibility view]\n"
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
        assert any("must_haves does not match" in warning for warning in result.warnings)

    def test_invalid_reference_targets_are_reported(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value within tolerance\n"
            "      deliverables: [deliv-main]\n"
            "      acceptance_tests: [test-main]\n"
            "      references: [ref-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main benchmark figure\n"
            "  references:\n"
            "    - id: ref-main\n"
            "      kind: paper\n"
            "      locator: Author et al., Journal, 2024\n"
            "      role: benchmark\n"
            "      why_it_matters: Published comparison target\n"
            "      applies_to: [claim-missing]\n"
            "      must_surface: true\n"
            "      required_actions: [read, compare, cite]\n"
            "  acceptance_tests:\n"
            "    - id: test-main\n"
            "      subject: claim-main\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-main, ref-main]\n"
            "  forbidden_proxies:\n"
            "    - id: fp-main\n"
            "      subject: claim-main\n"
            "      proxy: Qualitative trend match without numerical comparison\n"
            "      reason: Would allow false progress without the decisive benchmark\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
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
        assert result.valid is False
        assert any("applies_to unknown target claim-missing" in error for error in result.errors)



# ---------------------------------------------------------------------------
# Self-check regex word boundaries (regression for substring matching)
# ---------------------------------------------------------------------------


class TestSelfCheckRegexBoundaries:
    """Regression: _SELF_CHECK_PASS/FAIL must not match substrings."""

    def test_fail_does_not_match_failures(self):
        from gpd.core.frontmatter import _SELF_CHECK_FAIL

        assert _SELF_CHECK_FAIL.search("fail") is not None
        assert _SELF_CHECK_FAIL.search("failed") is not None
        # "failures" should NOT match — "fail" is a substring without a word boundary
        assert _SELF_CHECK_FAIL.search("failures") is None
        # "no failures" should NOT match either
        assert _SELF_CHECK_FAIL.search("no failures") is None

    def test_fail_does_not_match_failsafe(self):
        from gpd.core.frontmatter import _SELF_CHECK_FAIL

        assert _SELF_CHECK_FAIL.search("failsafe") is None

    def test_pass_does_not_match_incomplete(self):
        from gpd.core.frontmatter import _SELF_CHECK_PASS

        # "complete" must not match inside "incomplete"
        assert _SELF_CHECK_PASS.search("incomplete") is None

    def test_pass_matches_valid_words(self):
        from gpd.core.frontmatter import _SELF_CHECK_PASS

        assert _SELF_CHECK_PASS.search("pass") is not None
        assert _SELF_CHECK_PASS.search("passed") is not None
        assert _SELF_CHECK_PASS.search("all pass") is not None
        assert _SELF_CHECK_PASS.search("all passed") is not None
        assert _SELF_CHECK_PASS.search("complete") is not None
        assert _SELF_CHECK_PASS.search("completed") is not None
        assert _SELF_CHECK_PASS.search("succeeded") is not None

    def test_fail_matches_valid_words(self):
        from gpd.core.frontmatter import _SELF_CHECK_FAIL

        assert _SELF_CHECK_FAIL.search("fail") is not None
        assert _SELF_CHECK_FAIL.search("failed") is not None
        assert _SELF_CHECK_FAIL.search("incomplete") is not None
        assert _SELF_CHECK_FAIL.search("blocked") is not None

    def test_pass_does_not_match_passover(self):
        from gpd.core.frontmatter import _SELF_CHECK_PASS

        assert _SELF_CHECK_PASS.search("passover") is None

    def test_pass_does_not_match_compass(self):
        from gpd.core.frontmatter import _SELF_CHECK_PASS

        assert _SELF_CHECK_PASS.search("compass") is None
