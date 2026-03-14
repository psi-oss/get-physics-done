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
    reconstruct_frontmatter,
    splice_frontmatter,
    validate_frontmatter,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _valid_plan_contract_frontmatter(
    extra_contract_lines: str = "",
    *,
    interactive: str = "false",
    deliverable_must_contain: list[str] | None = None,
) -> str:
    extra = extra_contract_lines.rstrip()
    contract_suffix = f"\n{extra}" if extra else ""
    must_contain = ""
    if deliverable_must_contain:
        must_contain_items = ", ".join(deliverable_must_contain)
        must_contain = f"\n      must_contain: [{must_contain_items}]"
    return (
        "---\n"
        "phase: 01-test\n"
        "plan: 01\n"
        "type: execute\n"
        "wave: 1\n"
        "depends_on: []\n"
        "files_modified: []\n"
        f"interactive: {interactive}\n"
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
        f"      description: Main benchmark figure{must_contain}\n"
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
        f"{contract_suffix}\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]"
        "\n"
        "---\n\n"
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
        content = "---\ncontract:\n  scope:\n    question: Example\n---\n\nBody."
        meta, body = extract_frontmatter(content)
        assert meta["contract"]["scope"]["question"] == "Example"


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

    def test_non_object_contract_raises(self):
        content = "---\ncontract: claim-main\n---\n\nBody."

        with pytest.raises(FrontmatterValidationError, match="expected an object"):
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

    def test_summary_rejects_non_list_comparison_verdicts(self):
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "comparison_verdicts:\n"
            "  claim-main:\n"
            "    verdict: pass\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")
        assert result.valid is False
        assert any("comparison_verdicts: expected a list" in error for error in result.errors)

    def test_plan_rejects_unsupported_must_haves_field(self):
        content = _valid_plan_contract_frontmatter().replace(
            "---\n\n",
            "must_haves:\n  truths: [Obsolete block]\n---\n\n",
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert any(error.startswith("must_haves:") for error in result.errors)

    def test_summary_rejects_unsupported_verification_inputs(self):
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "verification_inputs:\n"
            "  truths: []\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")
        assert result.valid is False
        assert any(error.startswith("verification_inputs:") for error in result.errors)

    def test_valid_plan_with_contract_only(self):
        content = (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8")
        result = validate_frontmatter(content, "plan")
        assert result.valid is True
        assert result.errors == []

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
        assert any("missing references or explicit grounding context" in error for error in result.errors)
        assert any("missing forbidden_proxies" in error for error in result.errors)
        assert any("missing uncertainty_markers.disconfirming_observations" in error for error in result.errors)

    def test_exploratory_plan_contract_can_use_non_reference_grounding(self):
        content = (
            "---\n"
            "phase: 01-setup\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "contract:\n"
            "  scope:\n"
            "    question: What setup output should be ready for later comparison?\n"
            "    unresolved_questions: [\"Which benchmark will be authoritative?\"]\n"
            "  context_intake:\n"
            "    must_include_prior_outputs: [.gpd/phases/00-setup/00-01-SUMMARY.md]\n"
            "    known_good_baselines: [Smoke-test CLI output]\n"
            "  claims:\n"
            "    - id: claim-setup\n"
            "      statement: Produce a reproducible setup note and runnable starter code\n"
            "      deliverables: [deliv-note, deliv-code]\n"
            "      acceptance_tests: [test-note, test-code]\n"
            "  deliverables:\n"
            "    - id: deliv-note\n"
            "      kind: note\n"
            "      path: notes/setup.md\n"
            "      description: Setup note with assumptions and next checks\n"
            "      must_contain: [assumptions, next checks]\n"
            "    - id: deliv-code\n"
            "      kind: code\n"
            "      path: scripts/setup.sh\n"
            "      description: Runnable setup bootstrap\n"
            "      must_contain: [set -e]\n"
            "  acceptance_tests:\n"
            "    - id: test-note\n"
            "      subject: deliv-note\n"
            "      kind: human_review\n"
            "      procedure: Review the note for preserved guidance and open questions\n"
            "      pass_condition: The note keeps assumptions and next checks explicit\n"
            "      evidence_required: [deliv-note]\n"
            "    - id: test-code\n"
            "      subject: deliv-code\n"
            "      kind: existence\n"
            "      procedure: Confirm the bootstrap script exists\n"
            "      pass_condition: Script is present in the workspace\n"
            "      evidence_required: [deliv-code]\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [The chosen setup path may not match the final benchmark stack]\n"
            "    disconfirming_observations: [Bootstrap assumptions fail against the first real target]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is True
        assert result.errors == []

    def test_scoping_plan_contract_can_preserve_open_questions_before_decomposition(self):
        content = (
            "---\n"
            "phase: 01-setup\n"
            "plan: 01\n"
            "type: discuss\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: true\n"
            "contract:\n"
            "  scope:\n"
            "    question: Which formulation and anchors deserve a first serious pass?\n"
            "    unresolved_questions:\n"
            "      - Which benchmark should anchor the first computation?\n"
            "  context_intake:\n"
            "    must_include_prior_outputs: [.gpd/phases/00-scan/00-01-SUMMARY.md]\n"
            "    context_gaps: [Need a decisive benchmark before committing to fanout]\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [The current framing may still be proxy-heavy]\n"
            "    disconfirming_observations: [The first decisive benchmark points to a different formulation]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is True
        assert result.errors == []

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

    def test_missing_contract_is_invalid(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        f = tmp_path / "plan.md"
        f.write_text("---\ntitle: test\n---\n\nNo artifacts.\n")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False
        assert any("contract not found" in issue.lower() for artifact in result.artifacts for issue in artifact.issues)

    def test_contract_deliverable_exists(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "main.png").write_text("figure-bytes")
        f = tmp_path / "plan.md"
        f.write_text(_valid_plan_contract_frontmatter() + "Body.\n")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True
        assert result.passed_count == 1

    def test_contract_deliverable_missing(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        f = tmp_path / "plan.md"
        f.write_text(_valid_plan_contract_frontmatter() + "Body.\n")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False

    def test_contract_deliverable_must_contain_check(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "main.png").write_text("benchmark evidence\nreference within tolerance\n")
        f = tmp_path / "plan.md"
        content = _valid_plan_contract_frontmatter(
            deliverable_must_contain=["benchmark evidence", "reference within tolerance"]
        ) + "Body.\n"
        f.write_text(content)
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True

    def test_contract_deliverable_missing_required_fragment(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "main.png").write_text("benchmark evidence only\n")
        f = tmp_path / "plan.md"
        content = _valid_plan_contract_frontmatter(
            deliverable_must_contain=["benchmark evidence", "reference within tolerance"]
        ) + "Body.\n"
        f.write_text(content)
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False
        assert any("Missing pattern: reference within tolerance" in i for a in result.artifacts for i in a.issues)

    def test_invalid_contract_fails_artifact_verification(self, tmp_path):
        from gpd.core.frontmatter import verify_artifacts

        f = tmp_path / "plan.md"
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
            "---\n\nBody.\n"
        )
        f.write_text(content)
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False
        assert any("missing claims" in issue for artifact in result.artifacts for issue in artifact.issues)


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
            _valid_plan_contract_frontmatter()
            +
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

        content = _valid_plan_contract_frontmatter().replace("wave: 1\n", "wave: 2\n") + "Body.\n"
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert any("Wave > 1" in w for w in result.warnings)

    def test_checkpoint_interactive_mismatch(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            _valid_plan_contract_frontmatter()
            +
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
            _valid_plan_contract_frontmatter(interactive="true")
            +
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

    def test_rejects_unsupported_must_haves_field(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            _valid_plan_contract_frontmatter().replace(
                "---\n\n",
                "must_haves:\n  truths: [Obsolete block]\n---\n\n",
            )
            + '<task type="code">\n'
            + "  <name>Implement feature</name>\n"
            + "  <files>src/main.py</files>\n"
            + "  <action>Write the code</action>\n"
            + "  <verify>Run tests</verify>\n"
            + "  <done>Tests pass</done>\n"
            + "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content)
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is False
        assert any("Unsupported frontmatter field: must_haves" in error for error in result.errors)



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
