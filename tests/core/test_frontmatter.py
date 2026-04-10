"""Tests for gpd.core.frontmatter — YAML frontmatter CRUD + validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent

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
    verify_artifacts,
    verify_summary,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
STAGE4_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"


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
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n"
        "contract:\n"
        "  schema_version: 1\n"
        "  scope:\n"
        "    question: What benchmark must this plan recover?\n"
        "  context_intake:\n"
        "    must_read_refs: [ref-main]\n"
        "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
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


def _add_plan_conventions(content: str) -> str:
    if "conventions:" in content:
        return content
    return content.replace(
        "interactive: false\n",
        "interactive: false\n"
        "conventions:\n"
        "  units: natural\n"
        "  metric: (+,-,-,-)\n"
        "  coordinates: Cartesian\n",
        1,
    )


def _plan_frontmatter_with_knowledge_controls(
    *,
    knowledge_deps: object | None = None,
    knowledge_gate: str | None = None,
) -> str:
    metadata = ""
    if knowledge_gate is not None:
        metadata += f"knowledge_gate: {knowledge_gate}\n"
    if knowledge_deps is not None:
        if isinstance(knowledge_deps, list):
            metadata += "knowledge_deps:\n"
            for dep in knowledge_deps:
                metadata += f"  - {dep}\n"
        else:
            metadata += f"knowledge_deps: {knowledge_deps}\n"
    if not metadata:
        return _valid_plan_contract_frontmatter() + "Body.\n"
    return _valid_plan_contract_frontmatter().replace(
        "conventions:\n",
        f"{metadata}conventions:\n",
        1,
    ) + "Body.\n"


def _plan_contract_frontmatter_with_explicit_semantic_sections() -> str:
    return _valid_plan_contract_frontmatter(
        extra_contract_lines=(
            "  observables:\n"
            "    - id: obs-main\n"
            "      name: Benchmark value\n"
            "      kind: scalar\n"
            "      definition: Decisive benchmark observable\n"
            "  links:\n"
            "    - id: link-main\n"
            "      source: claim-main\n"
            "      target: deliv-main\n"
            "      relation: supports\n"
            "      verified_by: [test-main]"
        )
    )


def _summary_frontmatter_with_contract_ref(plan_contract_ref: str) -> str:
    return (
        "---\n"
        "phase: 01\n"
        "plan: 01\n"
        "depth: standard\n"
        "provides: []\n"
        "completed: 2025-01-01\n"
        f"plan_contract_ref: {plan_contract_ref}\n"
        "---\n\nBody.\n"
    )


def _project_local_plan_contract_frontmatter() -> str:
    return dedent(
        """\
        ---
        phase: 01-benchmark
        plan: 01
        type: execute
        wave: 1
        depends_on: []
        files_modified: []
        interactive: false
        conventions:
          units: natural
          metric: (+,-,-,-)
          coordinates: Cartesian
        contract:
          schema_version: 1
          scope:
            question: What benchmark must this plan recover?
          context_intake:
            must_read_refs: [ref-benchmark]
            must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]
          claims:
            - id: claim-benchmark
              statement: Recover the benchmark comparison
              deliverables: [deliv-figure]
              acceptance_tests: [test-benchmark]
              references: [ref-benchmark]
          deliverables:
            - id: deliv-figure
              kind: figure
              path: figures/benchmark.png
              description: Benchmark figure
          references:
            - id: ref-benchmark
              kind: prior_artifact
              locator: artifacts/benchmark/report.json
              role: benchmark
              why_it_matters: Project-local benchmark artifact
              applies_to: [claim-benchmark]
              must_surface: true
              required_actions: [read, compare, cite]
          acceptance_tests:
            - id: test-benchmark
              subject: claim-benchmark
              kind: benchmark
              procedure: Compare against the benchmark artifact
              pass_condition: Matches reference within tolerance
              evidence_required: [deliv-figure, ref-benchmark]
          forbidden_proxies:
            - id: fp-benchmark
              subject: claim-benchmark
              proxy: qualitative trend agreement without the benchmark artifact
              reason: Would miss the decisive local anchor
          uncertainty_markers:
            weakest_anchors: [Reference tolerance interpretation]
            disconfirming_observations: [Benchmark agreement disappears after normalization fix]
        ---

        Body.
        """
    )


def _proof_claim_statement() -> str:
    return "For all x > 0 and r_0 >= 0, F(x, r_0) >= 0."


def _proof_claim_statement_sha256() -> str:
    return hashlib.sha256(_proof_claim_statement().encode("utf-8")).hexdigest()


def _proof_artifact_path(phase_dir: Path) -> Path:
    return phase_dir / "derivations" / "theorem-proof.tex"


def _proof_redteam_artifact_path(phase_dir: Path) -> Path:
    return phase_dir / "01-01-PROOF-REDTEAM.md"


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_proof_contract_phase(tmp_path: Path) -> tuple[Path, Path]:
    phase_dir = tmp_path / "GPD" / "phases" / "01-proof"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text(
        dedent(
            f"""\
            ---
            phase: 01-proof
            plan: 01
            type: execute
            wave: 1
            depends_on: []
            files_modified: []
            interactive: false
            conventions:
              units: natural
              metric: (+,-,-,-)
              coordinates: Cartesian
            contract:
              schema_version: 1
              scope:
                question: Prove the full theorem without silently dropping r_0
              context_intake:
                must_read_refs: [ref-proof-anchor]
              observables:
                - id: obs-proof
                  name: theorem proof obligation
                  kind: proof_obligation
                  definition: Prove the theorem for all x > 0 and r_0 >= 0
              claims:
                - id: claim-proof
                  statement: "{_proof_claim_statement()}"
                  claim_kind: theorem
                  observables: [obs-proof]
                  deliverables: [deliv-proof]
                  acceptance_tests: [test-proof-alignment]
                  parameters:
                    - symbol: r_0
                      domain_or_type: nonnegative real
                    - symbol: x
                      domain_or_type: positive real
                  hypotheses:
                    - id: hyp-r0
                      text: r_0 >= 0
                      symbols: [r_0]
                    - id: hyp-x
                      text: x > 0
                      symbols: [x]
                  quantifiers: [for all x > 0, for all r_0 >= 0]
                  conclusion_clauses:
                    - id: concl-main
                      text: F(x, r_0) >= 0
                  proof_deliverables: [deliv-proof]
              deliverables:
                - id: deliv-proof
                  kind: derivation
                  path: derivations/theorem-proof.tex
                  description: Full theorem proof artifact
              acceptance_tests:
                - id: test-proof-alignment
                  subject: claim-proof
                  kind: claim_to_proof_alignment
                  procedure: Red-team the theorem statement against the proof
                  pass_condition: Every theorem parameter, hypothesis, and conclusion clause is accounted for
              forbidden_proxies:
                - id: fp-proof
                  subject: claim-proof
                  proxy: Prove only the r_0 = 0 subcase
                  reason: Would silently drop a named theorem parameter
              references:
                - id: ref-proof-anchor
                  kind: paper
                  locator: Author et al., Journal, 2024
                  role: background
                  why_it_matters: Concrete grounding for the theorem statement and proof audit.
                  applies_to: [claim-proof]
                  must_surface: true
                  required_actions: [read]
              uncertainty_markers:
                weakest_anchors: [Counterexample search scope remains finite]
                disconfirming_observations: [A valid counterexample at r_0 > 0 invalidates the theorem]
            ---

            Proof plan fixture.
            """
        ),
        encoding="utf-8",
    )
    proof_artifact = _proof_artifact_path(phase_dir)
    proof_artifact.parent.mkdir(parents=True, exist_ok=True)
    proof_artifact.write_text("% theorem proof artifact\n", encoding="utf-8")
    proof_redteam_artifact = _proof_redteam_artifact_path(phase_dir)
    proof_redteam_artifact.write_text(
        dedent(
            """\
            ---
            status: passed
            reviewer: gpd-check-proof
            claim_ids: [claim-proof]
            proof_artifact_paths: [derivations/theorem-proof.tex]
            ---

            # Proof Redteam
            """
        ),
        encoding="utf-8",
    )
    return phase_dir, plan_path


def _proof_verification_content(
    *,
    phase_dir: Path,
    proof_artifact_path: str = "derivations/theorem-proof.tex",
    proof_artifact_sha256: str | None = None,
    audit_artifact_path: str = "01-01-PROOF-REDTEAM.md",
    audit_artifact_sha256: str | None = None,
) -> str:
    resolved_proof_artifact_sha256 = (
        _sha256_path(_proof_artifact_path(phase_dir)) if proof_artifact_sha256 is None else proof_artifact_sha256
    )
    resolved_audit_artifact_sha256 = (
        _sha256_path(_proof_redteam_artifact_path(phase_dir))
        if audit_artifact_sha256 is None
        else audit_artifact_sha256
    )
    return dedent(
        f"""\
        ---
        phase: 01-proof
        verified: 2026-04-02T12:00:00Z
        status: passed
        score: 3/3 contract targets verified
        plan_contract_ref: GPD/phases/01-proof/01-01-PLAN.md#/contract
        contract_results:
          claims:
            claim-proof:
              status: passed
              summary: Proof-backed claim verified.
              linked_ids: [deliv-proof, test-proof-alignment]
              proof_audit:
                completeness: complete
                reviewed_at: "2026-04-02T12:00:00Z"
                reviewer: gpd-check-proof
                proof_artifact_path: {proof_artifact_path}
                proof_artifact_sha256: {resolved_proof_artifact_sha256}
                audit_artifact_path: {audit_artifact_path}
                audit_artifact_sha256: {resolved_audit_artifact_sha256}
                claim_statement_sha256: {_proof_claim_statement_sha256()}
                covered_hypothesis_ids: [hyp-r0, hyp-x]
                missing_hypothesis_ids: []
                covered_parameter_symbols: [r_0, x]
                missing_parameter_symbols: []
                uncovered_quantifiers: []
                uncovered_conclusion_clause_ids: []
                quantifier_status: matched
                scope_status: matched
                counterexample_status: none_found
                stale: false
          deliverables:
            deliv-proof:
              status: passed
              path: derivations/theorem-proof.tex
              summary: Proof artifact exists and matches the audited theorem.
              linked_ids: [claim-proof, test-proof-alignment]
          acceptance_tests:
            test-proof-alignment:
              status: passed
              summary: Proof-to-claim alignment review completed.
              linked_ids: [claim-proof, deliv-proof]
          references:
            ref-proof-anchor:
              status: completed
              completed_actions: [read]
              missing_actions: []
              summary: Concrete grounding anchor reviewed.
          forbidden_proxies:
            fp-proof:
              status: rejected
          uncertainty_markers:
            weakest_anchors: [Counterexample search explored the stated regime only]
            disconfirming_observations: [A counterexample at r_0 > 0 would break the theorem]
        ---

        Verification body.
        """
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

    def test_leading_blank_lines_before_frontmatter(self):
        content = "\n\n---\ntitle: Hello\n---\n\nBody text here."
        meta, body = extract_frontmatter(content)
        assert meta == {"title": "Hello"}
        assert body == "\nBody text here."

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

    def test_leading_blank_lines_before_frontmatter_are_replaced(self):
        content = "\n\n---\ntitle: Old\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert body == "\nBody."
        assert result.count("---") == 2
        assert result.startswith("\n\n---\n")

    def test_preserves_bom_when_rewriting_frontmatter(self):
        content = "\ufeff---\ntitle: Old\n---\n\nBody."
        result = splice_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert result.startswith("\ufeff---\n")
        assert meta["title"] == "New"
        assert "Body." in body


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

    def test_preserves_bom_when_merging_frontmatter(self):
        content = "\ufeff\n\n---\nmethods:\n  added:\n    - foo\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"methods": {"patterns": ["bar"]}})
        meta, body = extract_frontmatter(result)
        assert result.startswith("\ufeff\n\n---\n")
        assert meta["methods"]["added"] == ["foo"]
        assert meta["methods"]["patterns"] == ["bar"]
        assert "Body." in body

    def test_overwrite_non_dict(self):
        content = "---\ntitle: Old\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"title": "New"})
        meta, _ = extract_frontmatter(result)
        assert meta["title"] == "New"

    def test_leading_blank_lines_before_frontmatter_are_replaced(self):
        content = "\n\n---\ntitle: Old\n---\n\nBody."
        result = deep_merge_frontmatter(content, {"title": "New"})
        meta, body = extract_frontmatter(result)
        assert meta["title"] == "New"
        assert body == "\nBody."
        assert result.count("---") == 2
        assert result.startswith("\n\n---\n")

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

    def test_missing_context_intake_raises(self):
        content = _valid_plan_contract_frontmatter().replace(
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n",
            "",
            1,
        ) + "Body.\n"

        with pytest.raises(FrontmatterValidationError, match="context_intake is required"):
            parse_contract_block(content)

    def test_empty_context_intake_raises(self):
        content = _valid_plan_contract_frontmatter().replace(
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n",
            "  context_intake: {}\n",
            1,
        ) + "Body.\n"

        with pytest.raises(FrontmatterValidationError, match="context_intake must not be empty"):
            parse_contract_block(content)

    @pytest.mark.parametrize(
        ("missing_line", "collection_name", "field_name", "expected_value"),
        [
            ("      kind: scalar\n", "observables", "kind", "other"),
            ("      kind: figure\n", "deliverables", "kind", "other"),
            ("      kind: benchmark\n", "acceptance_tests", "kind", "other"),
            ("      kind: paper\n", "references", "kind", "other"),
            ("      role: benchmark\n", "references", "role", "other"),
            ("      relation: supports\n", "links", "relation", "other"),
        ],
    )
    def test_missing_defaultable_semantic_field_uses_contract_default(
        self,
        missing_line: str,
        collection_name: str,
        field_name: str,
        expected_value: str,
    ):
        content = _plan_contract_frontmatter_with_explicit_semantic_sections().replace(
            missing_line,
            "",
            1,
        ) + "Body.\n"

        contract = parse_contract_block(content)

        collection = getattr(contract, collection_name)
        assert getattr(collection[0], field_name) == expected_value

    def test_semantically_incomplete_contract_raises(self):
        content = (
            "---\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake: {}\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Benchmark interpretation remains fragile]\n"
            "    disconfirming_observations: [The claimed recovery disappears after normalization]\n"
            "---\n\nBody."
        )
        with pytest.raises(FrontmatterValidationError, match="missing acceptance_tests"):
            parse_contract_block(content)

    def test_rejects_coercive_reference_must_surface_scalar(self):
        content = _valid_plan_contract_frontmatter().replace("must_surface: true", 'must_surface: "yes"', 1) + "Body.\n"

        with pytest.raises(FrontmatterValidationError, match=r"references\.0\.must_surface must be a boolean"):
            parse_contract_block(content)

    def test_rejects_coercive_schema_version_scalar(self):
        content = _valid_plan_contract_frontmatter().replace("schema_version: 1\n", "schema_version: true\n", 1) + "Body.\n"

        with pytest.raises(FrontmatterValidationError, match="schema_version must be the integer 1"):
            parse_contract_block(content)

    def test_rejects_singleton_list_drift(self):
        content = _valid_plan_contract_frontmatter().replace("must_read_refs: [ref-main]\n", "must_read_refs: ref-main\n", 1) + "Body.\n"

        with pytest.raises(
            FrontmatterValidationError,
            match=r"context_intake\.must_read_refs must be a list, not str",
        ):
            parse_contract_block(content)

    def test_rejects_recoverable_extra_key_drift(self):
        content = _valid_plan_contract_frontmatter().replace(
            "      references: [ref-main]\n",
            "      references: [ref-main]\n      notes: harmless\n",
            1,
        ) + "Body.\n"

        with pytest.raises(
            FrontmatterValidationError,
            match=r"claims\.0\.notes: Extra inputs are not permitted",
        ):
            parse_contract_block(content)

    def test_project_root_relative_contract_anchor_uses_source_path_context(self, tmp_path: Path) -> None:
        project_root = tmp_path
        phase_dir = project_root / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True)
        artifact = project_root / "artifacts" / "benchmark" / "report.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}", encoding="utf-8")
        baseline_dir = project_root / "GPD" / "phases" / "00-baseline"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "00-01-SUMMARY.md").write_text("baseline summary", encoding="utf-8")

        plan_path = phase_dir / "01-01-PLAN.md"
        content = _project_local_plan_contract_frontmatter()

        without_source = validate_frontmatter(content, "plan")
        with_source = validate_frontmatter(content, "plan", source_path=plan_path)
        contract = parse_contract_block(content, source_path=plan_path)

        assert without_source.valid is False
        assert any("must include at least one must_surface=true anchor" in error for error in without_source.errors)
        assert with_source.valid is True
        assert contract is not None
        assert contract.references[0].locator == "artifacts/benchmark/report.json"


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def test_valid_plan(self):
        content = _add_plan_conventions((FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
        result = validate_frontmatter(content, "plan")
        assert isinstance(result, FrontmatterValidation)
        assert result.valid is True
        assert result.missing == []

    def test_plan_accepts_valid_tool_requirements(self):
        content = _valid_plan_contract_frontmatter().replace(
            "contract:\n",
            "tool_requirements:\n"
            "  - id: wolfram-cas\n"
            "    tool: wolfram\n"
            "    purpose: Symbolic tensor reduction\n"
            "    required: true\n"
            "    fallback: Use SymPy if unavailable\n"
            "contract:\n",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is True
        assert result.errors == []

    def test_plan_accepts_knowledge_dependency_controls(self):
        content = _plan_frontmatter_with_knowledge_controls(
            knowledge_gate="warn",
            knowledge_deps=["K-renormalization-group-fixed-points"],
        )

        result = validate_frontmatter(content, "plan")

        assert result.valid is True
        assert result.errors == []

    @pytest.mark.parametrize(
        ("knowledge_deps", "expected_error"),
        [
            ("K-renormalization-group-fixed-points", "knowledge_deps: expected a list"),
            (
                ["renormalization-group"],
                "knowledge_deps: entry 0 must use canonical K-{ascii-hyphen-slug} format",
            ),
            (
                ["K-renormalization-group-fixed-points", "K-renormalization-group-fixed-points"],
                "knowledge_deps: duplicate ids are not allowed: K-renormalization-group-fixed-points",
            ),
        ],
    )
    def test_plan_rejects_invalid_knowledge_deps(
        self,
        knowledge_deps: object,
        expected_error: str,
    ) -> None:
        content = _plan_frontmatter_with_knowledge_controls(knowledge_deps=knowledge_deps)

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert expected_error in result.errors

    @pytest.mark.parametrize(
        ("knowledge_gate", "expected_error"),
        [
            ("", "knowledge_gate: expected a string"),
            ("maybe", "knowledge_gate: must be one of off, warn, block"),
            ("blocker", "knowledge_gate: must be one of off, warn, block"),
        ],
    )
    def test_plan_rejects_invalid_knowledge_gate_values(
        self,
        knowledge_gate: str,
        expected_error: str,
    ) -> None:
        content = _plan_frontmatter_with_knowledge_controls(knowledge_gate=knowledge_gate)

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert expected_error in result.errors

    def test_summary_with_source_path_resolves_project_root_relative_sibling_plan_contract(
        self,
        tmp_path: Path,
    ) -> None:
        project_root = tmp_path
        phase_dir = project_root / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True)
        artifact = project_root / "artifacts" / "benchmark" / "report.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}", encoding="utf-8")
        baseline_dir = project_root / "GPD" / "phases" / "00-baseline"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "00-01-SUMMARY.md").write_text("baseline summary", encoding="utf-8")

        plan_path = phase_dir / "01-01-PLAN.md"
        plan_path.write_text(_project_local_plan_contract_frontmatter(), encoding="utf-8")
        summary_path = phase_dir / "01-01-SUMMARY.md"
        summary_path.write_text(
            (STAGE4_FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

        assert result.valid is True
        assert result.errors == []

    def test_plan_rejects_coercive_reference_must_surface_scalar(self):
        content = _valid_plan_contract_frontmatter().replace("must_surface: true", 'must_surface: "yes"', 1) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert "contract: references.0.must_surface must be a boolean" in result.errors

    def test_plan_rejects_coercive_schema_version_scalar(self):
        content = _valid_plan_contract_frontmatter().replace("schema_version: 1\n", "schema_version: true\n", 1) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert "contract: schema_version must be the integer 1" in result.errors

    def test_plan_rejects_invalid_tool_requirements(self):
        content = _valid_plan_contract_frontmatter().replace(
            "contract:\n",
            "tool_requirements:\n"
            "  - id: custom-main\n"
            "    tool: command\n"
            "    purpose: Run external solver\n"
            "contract:\n",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert any("tool_requirements:" in error for error in result.errors)

    def test_plan_rejects_singleton_list_drift_in_contract(self):
        content = _valid_plan_contract_frontmatter().replace("must_read_refs: [ref-main]\n", "must_read_refs: ref-main\n", 1) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert "contract: context_intake.must_read_refs must be a list, not str" in result.errors

    def test_plan_rejects_missing_context_intake(self):
        content = _valid_plan_contract_frontmatter().replace(
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n",
            "",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert any("context_intake is required" in error for error in result.errors)

    def test_plan_rejects_empty_context_intake(self):
        content = _valid_plan_contract_frontmatter().replace(
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n",
            "  context_intake: {}\n",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert any("context_intake must not be empty" in error for error in result.errors)

    @pytest.mark.parametrize(
        "missing_line",
        [
            "      kind: scalar\n",
            "      kind: figure\n",
            "      kind: benchmark\n",
            "      kind: paper\n",
            "      role: benchmark\n",
            "      relation: supports\n",
        ],
    )
    def test_plan_accepts_missing_defaultable_semantic_fields(
        self,
        missing_line: str,
    ):
        content = _plan_contract_frontmatter_with_explicit_semantic_sections().replace(
            missing_line,
            "",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is True
        assert result.errors == []

    def test_plan_accepts_valid_tool_requirements_with_mathematica_alias(self):
        content = (
            _valid_plan_contract_frontmatter()
            .replace(
                "conventions:\n"
                "  units: natural\n"
                "  metric: (+,-,-,-)\n"
                "  coordinates: Cartesian\n",
                "tool_requirements:\n"
                "  - id: wolfram-cas\n"
                "    tool: mathematica\n"
                "    purpose: Symbolic tensor reduction\n"
                "    required: false\n"
                "    fallback: Use SymPy instead\n"
                "conventions:\n"
                "  units: natural\n"
                "  metric: (+,-,-,-)\n"
                "  coordinates: Cartesian\n",
                1,
            )
            + "Body.\n"
        )

        result = validate_frontmatter(content, "plan")

        assert result.valid is True
        assert result.errors == []

    def test_plan_accepts_empty_tool_requirements_as_no_requirements(self):
        content = (
            _valid_plan_contract_frontmatter()
            .replace(
                "conventions:\n"
                "  units: natural\n"
                "  metric: (+,-,-,-)\n"
                "  coordinates: Cartesian\n",
                "tool_requirements: []\n"
                "conventions:\n"
                "  units: natural\n"
                "  metric: (+,-,-,-)\n"
                "  coordinates: Cartesian\n",
                1,
            )
            + "Body.\n"
        )

        result = validate_frontmatter(content, "plan")

        assert result.valid is True
        assert result.errors == []

    def test_missing_fields(self):
        content = "---\nphase: 01-test\n---\n\nBody."
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert len(result.missing) > 0
        assert "phase" not in result.missing
        assert "plan" in result.missing

    def test_plan_requires_conventions(self):
        content = _valid_plan_contract_frontmatter().replace(
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n",
            "",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert "conventions" in result.missing

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

    @pytest.mark.parametrize(
        ("schema_name", "content", "expected_error"),
        [
            (
                "plan",
                _valid_plan_contract_frontmatter().replace("interactive: false\n", "interactive: null\n", 1) + "Body.\n",
                "interactive: expected a boolean",
            ),
            (
                "summary",
                "---\nphase: 01\nplan: 01\ndepth: standard\nprovides: []\ncompleted: null\n---\n\nBody.",
                "completed: expected a date string or boolean",
            ),
            (
                "verification",
                "---\nphase: 01\nverified: null\nstatus: passed\nscore: 0/0 contract targets verified\n---\n\nBody.",
                "verified: expected a non-null scalar",
            ),
        ],
    )
    def test_required_frontmatter_fields_reject_null_values(
        self,
        schema_name: str,
        content: str,
        expected_error: str,
    ) -> None:
        result = validate_frontmatter(content, schema_name)

        assert result.valid is False
        assert expected_error in result.errors

    @pytest.mark.parametrize(
        ("schema_name", "content", "expected_error"),
        [
            (
                "plan",
                _valid_plan_contract_frontmatter().replace("wave: 1\n", 'wave: "one"\n', 1) + "Body.\n",
                "wave: expected an integer",
            ),
            (
                "summary",
                "---\nphase: 01\nplan: 01\ndepth: []\nprovides: []\ncompleted: 2025-01-01\n---\n\nBody.",
                "depth: expected a non-empty string",
            ),
            (
                "verification",
                "---\nphase: 01\nverified: 2025-01-01T00:00:00Z\nstatus: []\nscore: 0/0 contract targets verified\n---\n\nBody.",
                "status: expected a non-empty string",
            ),
        ],
    )
    def test_required_frontmatter_fields_reject_wrong_types(
        self,
        schema_name: str,
        content: str,
        expected_error: str,
    ) -> None:
        result = validate_frontmatter(content, schema_name)

        assert result.valid is False
        assert expected_error in result.errors

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

    @pytest.mark.parametrize("placeholder", ["[]", "null"])
    def test_summary_rejects_placeholder_contract_results_section_shapes(self, placeholder: str):
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "plan_contract_ref: GPD/phases/01-test/01-01-PLAN.md#/contract\n"
            "contract_results:\n"
            f"  claims: {placeholder}\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")
        assert result.valid is False
        assert any("claims" in error for error in result.errors)

    def test_summary_rejects_explicit_null_contract_results_block(self):
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "plan_contract_ref: GPD/phases/01-test/01-01-PLAN.md#/contract\n"
            "contract_results:\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")
        assert result.valid is False
        assert any("contract_results:" in error for error in result.errors)

    def test_summary_rejects_missing_uncertainty_markers_for_contract_backed_summary(self):
        content = (STAGE4_FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
            "",
            1,
        )

        result = validate_frontmatter(content, "summary")

        assert result.valid is False
        assert any("uncertainty_markers" in error for error in result.errors)

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

    def test_summary_rejects_verification_only_suggested_contract_checks(self):
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "suggested_contract_checks:\n"
            "  - check: Missing decisive benchmark comparison\n"
            "    reason: Verification-only gap ledger should not appear in summaries\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")
        assert result.valid is False
        assert any(error.startswith("suggested_contract_checks:") for error in result.errors)

    @pytest.mark.parametrize("schema_name", ["summary", "verification"])
    def test_summary_and_verification_reject_legacy_must_haves(self, schema_name: str):
        if schema_name == "summary":
            content = (
                "---\n"
                "phase: 01\n"
                "plan: 01\n"
                "depth: standard\n"
                "provides: []\n"
                "completed: 2025-01-01\n"
                "must_haves:\n"
                "  truths: [Obsolete block]\n"
                "---\n\nBody."
            )
        else:
            content = (
                "---\n"
                "phase: 01\n"
                "verified: 2025-01-01T00:00:00Z\n"
                "status: passed\n"
                "score: 0/0 contract targets verified\n"
                "must_haves:\n"
                "  truths: [Obsolete block]\n"
                "---\n\nBody."
            )

        result = validate_frontmatter(content, schema_name)

        assert result.valid is False
        assert any(error.startswith("must_haves:") for error in result.errors)

    def test_summary_coerces_integer_provides_entries(self):
        """Integer provides entries are coerced to strings (FULL-019)."""
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides:\n"
            "  - solver\n"
            "  - 12\n"
            "completed: 2025-01-01\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")

        assert "provides: entry 1 must be a non-empty string" not in result.errors

    def test_summary_rejects_non_coercible_provides_entries(self):
        """Boolean provides entries are still rejected (not coerced)."""
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides:\n"
            "  - solver\n"
            "  - true\n"
            "completed: 2025-01-01\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "summary")

        assert result.valid is False
        assert "provides: entry 1 must be a non-empty string" in result.errors

    def test_verification_rejects_noncanonical_independently_confirmed_field(self):
        content = (
            "---\n"
            "phase: 01\n"
            "verified: 2025-01-01T00:00:00Z\n"
            "status: gaps_found\n"
            "score: 0/0 contract targets verified\n"
            "independently_confirmed: 0/0\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "verification")
        assert result.valid is False
        assert any(error.startswith("independently_confirmed:") for error in result.errors)

    def test_verify_summary_enforces_same_summary_schema_contract(self, tmp_path: Path):
        summary_path = tmp_path / "01-01-SUMMARY.md"
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "verification_inputs:\n"
            "  truths: []\n"
            "contract_results:\n"
            "  claims: []\n"
            "---\n\nBody.\n"
        )
        summary_path.write_text(content, encoding="utf-8")

        validation = validate_frontmatter(content, "summary", source_path=summary_path)
        result = verify_summary(tmp_path, summary_path)

        assert result.summary_exists is True
        assert result.passed is False
        assert result.errors == validation.errors

    def test_verify_summary_reports_missing_required_summary_fields(self, tmp_path: Path):
        summary_path = tmp_path / "01-01-SUMMARY.md"
        content = "---\nphase: 01\nplan: 01\n---\n\nBody.\n"
        summary_path.write_text(content, encoding="utf-8")

        result = verify_summary(tmp_path, summary_path)

        assert result.summary_exists is True
        assert result.passed is False
        assert "depth is required" in result.errors
        assert "provides is required" in result.errors
        assert "completed is required" in result.errors

    def test_verify_summary_checks_root_level_key_files_in_declared_order(self, tmp_path: Path):
        summary_path = tmp_path / "01-01-SUMMARY.md"
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "existing.py").write_text("print('ok')\n", encoding="utf-8")
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "one-liner: Checked summary evidence ordering\n"
            "key-files:\n"
            "  - README.md\n"
            "  - src/existing.py\n"
            "---\n\nBody.\n"
        )
        summary_path.write_text(content, encoding="utf-8")

        result = verify_summary(tmp_path, summary_path, check_file_count=1)

        assert result.summary_exists is True
        assert result.passed is False
        assert result.files_created.checked == 1
        assert result.files_created.missing == ["README.md"]
        assert "Missing files: README.md" in result.errors

    def test_verify_summary_does_not_treat_backticked_hostnames_as_files(self, tmp_path: Path):
        summary_path = tmp_path / "01-01-SUMMARY.md"
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "one-liner: Mention external reference hostname\n"
            "---\n\nBody cites `example.com` for comparison.\n"
        )
        summary_path.write_text(content, encoding="utf-8")

        result = verify_summary(tmp_path, summary_path)

        assert result.summary_exists is True
        assert result.passed is True
        assert not any("example.com" in error for error in result.errors)

    def test_valid_plan_with_contract_only(self):
        content = _add_plan_conventions((FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
        result = validate_frontmatter(content, "plan")
        assert result.valid is True
        assert result.errors == []

    @pytest.mark.parametrize(
        ("field_block", "field_name"),
        [
            ("verification_inputs:\n  truths: []\n", "verification_inputs"),
            ("contract_evidence: []\n", "contract_evidence"),
            ("contract_results:\n  claims: []\n", "contract_results"),
            ("comparison_verdicts: []\n", "comparison_verdicts"),
            ("suggested_contract_checks: []\n", "suggested_contract_checks"),
        ],
    )
    def test_plan_rejects_summary_or_verification_only_fields(self, field_block: str, field_name: str):
        content = _valid_plan_contract_frontmatter().replace("---\n\n", f"{field_block}---\n\n", 1) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert any(error.startswith(f"{field_name}:") for error in result.errors)

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
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
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
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake: {}\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
            "---\n\nBody."
        )
        result = validate_frontmatter(content, "plan")
        assert result.valid is False
        assert any("missing acceptance_tests" in error for error in result.errors)
        assert any("missing references or explicit grounding context" in error for error in result.errors)
        assert any("missing forbidden_proxies" in error for error in result.errors)
        assert any("context_intake must not be empty" in error for error in result.errors)

    def test_exploratory_plan_contract_can_use_non_reference_grounding(self, tmp_path: Path):
        phase_dir = tmp_path / "GPD" / "phases" / "00-setup"
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "00-01-SUMMARY.md").write_text("setup summary\n", encoding="utf-8")
        plan_path = phase_dir / "01-01-PLAN.md"
        content = (
            "---\n"
            "phase: 01-setup\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What setup output should be ready for later comparison?\n"
            "    unresolved_questions: [\"Which benchmark will be authoritative?\"]\n"
            "  context_intake:\n"
            "    must_include_prior_outputs: [GPD/phases/00-setup/00-01-SUMMARY.md]\n"
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
        result = validate_frontmatter(content, "plan", source_path=plan_path)
        assert result.valid is True
        assert result.errors == []

    def test_scoping_plan_contract_can_preserve_open_questions_before_decomposition(self):
        content = (
            "---\n"
            "phase: 01-setup\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: true\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: Which formulation and anchors deserve a first serious pass?\n"
            "    unresolved_questions:\n"
            "      - Which benchmark should anchor the first computation?\n"
            "  context_intake:\n"
            "    must_include_prior_outputs: [GPD/phases/00-scan/00-01-SUMMARY.md]\n"
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
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake: {}\n"
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

    def test_plan_rejects_placeholder_only_context_intake(self, tmp_path: Path) -> None:
        content = _valid_plan_contract_frontmatter().replace(
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n",
            "  context_intake:\n"
            "    must_read_refs: []\n"
            "    must_include_prior_outputs: []\n"
            "    user_asserted_anchors: []\n"
            "    known_good_baselines: []\n"
            "    context_gaps: [TBD]\n"
            "    crucial_inputs: [placeholder]\n",
            1,
        )
        plan_path = tmp_path / "GPD" / "phases" / "01-test" / "01-01-PLAN.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        baseline = tmp_path / "GPD" / "phases" / "00-baseline" / "00-01-SUMMARY.md"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text("summary\n", encoding="utf-8")

        result = validate_frontmatter(content, "plan", source_path=plan_path)

        assert result.valid is False
        assert any("context_intake must not be empty" in error for error in result.errors)

    def test_plan_accepts_rootless_prior_output_as_visible_context_intake(self) -> None:
        content = _valid_plan_contract_frontmatter().replace(
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n",
            "    must_read_refs: []\n"
            "    must_include_prior_outputs: [./RESULTS.md]\n",
            1,
        )

        result = validate_frontmatter(content, "plan")

        assert result.valid is True
        assert not any("context_intake must not be empty" in error for error in result.errors)

    def test_plan_accepts_non_must_surface_reference_with_project_root_grounding(self, tmp_path: Path) -> None:
        content = _valid_plan_contract_frontmatter().replace("must_surface: true", "must_surface: false", 1)
        plan_path = tmp_path / "GPD" / "phases" / "01-test" / "01-01-PLAN.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        baseline = tmp_path / "GPD" / "phases" / "00-baseline" / "00-01-SUMMARY.md"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text("summary\n", encoding="utf-8")

        result = validate_frontmatter(content, "plan", source_path=plan_path)

        assert result.valid is True
        assert result.errors == []

    def test_plan_contract_parsing_normalizes_blank_nested_proof_lists(self, tmp_path: Path) -> None:
        _phase_dir, plan_path = _write_proof_contract_phase(tmp_path)
        content = plan_path.read_text(encoding="utf-8").replace(
            "- symbol: r_0\n"
            "          domain_or_type: nonnegative real\n",
            "- symbol: r_0\n"
            "          domain_or_type: nonnegative real\n"
            "          aliases: \"\"\n",
            1,
        ).replace(
            "- id: hyp-r0\n"
            "          text: r_0 >= 0\n"
            "          symbols: [r_0]\n",
            "- id: hyp-r0\n"
            "          text: r_0 >= 0\n"
            "          symbols: \"\"\n",
            1,
        )

        result = validate_frontmatter(content, "plan", source_path=plan_path)
        contract = parse_contract_block(content, source_path=plan_path)

        assert result.valid is True
        assert contract is not None
        assert contract.claims[0].parameters[0].aliases == []
        assert contract.claims[0].hypotheses[0].symbols == []

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
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
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
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
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

    def test_plan_rejects_cross_kind_contract_id_collision(self):
        content = _valid_plan_contract_frontmatter().replace("    - id: deliv-main\n", "    - id: claim-main\n", 1) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert any(
            "contract id claim-main is reused across claim, deliverable; target resolution is ambiguous" in error
            for error in result.errors
        )

    def test_plan_rejects_reference_carry_forward_to_contract_id(self):
        content = _valid_plan_contract_frontmatter().replace(
            "      required_actions: [read, compare, cite]\n",
            "      required_actions: [read, compare, cite]\n"
            "      carry_forward_to: [claim-main]\n",
            1,
        ) + "Body.\n"

        result = validate_frontmatter(content, "plan")

        assert result.valid is False
        assert any(
            "reference ref-main carry_forward_to must name workflow scope, not contract id claim-main" in error
            for error in result.errors
        )

    def test_valid_verification(self):
        content = "---\nphase: 01\nverified: 2025-01-01T00:00:00Z\nstatus: passed\nscore: 5/5\n---\n\nBody."
        result = validate_frontmatter(content, "verification")
        assert result.valid is True

    @pytest.mark.parametrize(
        ("schema_name", "content", "expected_error"),
        [
            (
                "plan",
                _valid_plan_contract_frontmatter().replace("type: execute\n", "type: legacy\n", 1) + "Body.\n",
                "type: must be one of execute, tdd",
            ),
            (
                "summary",
                "---\nphase: 01\nplan: 01\ndepth: ultra\nprovides: []\ncompleted: 2025-01-01\n---\n\nBody.",
                "depth: must be one of minimal, standard, full, complex",
            ),
        ],
    )
    def test_frontmatter_rejects_invalid_semantic_enum_literals(
        self,
        schema_name: str,
        content: str,
        expected_error: str,
    ) -> None:
        result = validate_frontmatter(content, schema_name)

        assert result.valid is False
        assert expected_error in result.errors

    @pytest.mark.parametrize(
        "verified_value",
        [
            "2025-01-01",
            "123",
        ],
    )
    def test_verification_rejects_non_timestamp_verified_field(self, verified_value: str) -> None:
        content = f"---\nphase: 01\nverified: {verified_value}\nstatus: passed\nscore: 5/5\n---\n\nBody."

        result = validate_frontmatter(content, "verification")

        assert result.valid is False
        assert "verified: expected an ISO 8601 timestamp" in result.errors

    def test_summary_rejects_case_drifted_comparison_verdict_literals(self):
        content = (
            "---\n"
            "phase: 01\n"
            "plan: 01\n"
            "depth: standard\n"
            "provides: []\n"
            "completed: 2025-01-01\n"
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract\n"
            "comparison_verdicts:\n"
            "  - subject_id: claim-main\n"
            "    subject_kind: Claim\n"
            "    subject_role: Decisive\n"
            "    comparison_kind: Benchmark\n"
            "    verdict: Pass\n"
            "---\n\nBody."
        )

        result = validate_frontmatter(content, "summary")

        assert result.valid is False
        assert any("comparison_verdicts:" in error and "must use exact literal 'claim'" in error for error in result.errors)

    def test_summary_rejects_symlinked_plan_contract_ref_escape(self, tmp_path: Path) -> None:
        phase_dir = tmp_path / "GPD" / "phases" / "01-proof"
        phase_dir.mkdir(parents=True)

        outside_plan = tmp_path.parent / "outside-plan.md"
        outside_plan.write_text(_valid_plan_contract_frontmatter(), encoding="utf-8")
        plan_link = phase_dir / "01-01-PLAN.md"
        try:
            plan_link.symlink_to(outside_plan)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")

        summary_path = phase_dir / "01-SUMMARY.md"
        summary_path.write_text(
            _summary_frontmatter_with_contract_ref("GPD/phases/01-proof/01-01-PLAN.md#/contract"),
            encoding="utf-8",
        )

        result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

        assert result.valid is False
        assert any("plan_contract_ref: must resolve inside the project root" in error for error in result.errors)

    def test_verification_status_passed_rejects_blocked_contract_results(self, tmp_path: Path):
        phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True)
        (phase_dir / "01-01-PLAN.md").write_text(
            (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        verification_path = phase_dir / "01-VERIFICATION.md"
        verification_path.write_text(
            (STAGE4_FIXTURES_DIR / "verification_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "      status: passed\n      summary: Claim independently verified.\n",
                "      status: blocked\n      summary: Claim remains blocked on the decisive benchmark.\n",
                1,
            ),
            encoding="utf-8",
        )

        result = validate_frontmatter(
            verification_path.read_text(encoding="utf-8"),
            "verification",
            source_path=verification_path,
        )

        assert result.valid is False
        assert "status: passed is inconsistent with non-passed contract_results targets: claim claim-benchmark" in result.errors

    def test_verification_rejects_absolute_proof_audit_artifact_path(self, tmp_path: Path) -> None:
        phase_dir, _ = _write_proof_contract_phase(tmp_path)
        outside_proof_artifact = tmp_path.parent / "outside-proof.tex"
        outside_proof_artifact.write_text("% outside proof artifact\n", encoding="utf-8")
        verification_path = phase_dir / "01-VERIFICATION.md"
        verification_path.write_text(
            _proof_verification_content(
                phase_dir=phase_dir,
                proof_artifact_sha256=_sha256_path(outside_proof_artifact),
                audit_artifact_path=str(outside_proof_artifact.resolve()),
            ),
            encoding="utf-8",
        )

        result = validate_frontmatter(
            verification_path.read_text(encoding="utf-8"),
            "verification",
            source_path=verification_path,
        )

        assert result.valid is False
        assert any(
            "claim claim-proof proof_audit audit_artifact_path must be a project-relative path" in error
            for error in result.errors
        )

    def test_verification_rejects_parent_traversal_proof_artifact_path_escape(
        self,
        tmp_path: Path,
    ) -> None:
        phase_dir, _ = _write_proof_contract_phase(tmp_path)
        outside_proof_artifact = tmp_path.parent / "outside-proof.tex"
        outside_proof_artifact.write_text("% outside proof artifact\n", encoding="utf-8")
        verification_path = phase_dir / "01-VERIFICATION.md"
        verification_path.write_text(
            _proof_verification_content(
                phase_dir=phase_dir,
                proof_artifact_path="../../../../outside-proof.tex",
                proof_artifact_sha256=_sha256_path(outside_proof_artifact),
            ),
            encoding="utf-8",
        )

        result = validate_frontmatter(
            verification_path.read_text(encoding="utf-8"),
            "verification",
            source_path=verification_path,
        )

        assert result.valid is False
        assert any(
            "must resolve inside the project root" in error
            for error in result.errors
        )

    def test_verification_rejects_symlinked_proof_artifact_path_escape(
        self,
        tmp_path: Path,
    ) -> None:
        phase_dir, _ = _write_proof_contract_phase(tmp_path)
        outside_proof_artifact = tmp_path.parent / "outside-proof.tex"
        outside_proof_artifact.write_text("% outside proof artifact\n", encoding="utf-8")
        symlink_path = phase_dir / "derivations" / "theorem-proof.tex"
        symlink_path.unlink()
        try:
            symlink_path.symlink_to(outside_proof_artifact)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")

        verification_path = phase_dir / "01-VERIFICATION.md"
        verification_path.write_text(
            _proof_verification_content(
                phase_dir=phase_dir,
                proof_artifact_sha256=_sha256_path(outside_proof_artifact),
            ),
            encoding="utf-8",
        )

        result = validate_frontmatter(
            verification_path.read_text(encoding="utf-8"),
            "verification",
            source_path=verification_path,
        )

        assert result.valid is False
        assert any(
            "must resolve inside the project root" in error
            for error in result.errors
        )

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


class TestTodoFrontmatterRegression:
    def test_leading_blank_lines_before_todo_frontmatter_are_parsed(self):
        from gpd.core.context import _extract_frontmatter_field, _read_todo_frontmatter

        content = '\n\n---\ntitle: Todo task\ncreated: "2026-01-01"\n---\nBody.\n'

        meta = _read_todo_frontmatter(content)
        assert meta == {"title": "Todo task", "created": "2026-01-01"}
        assert _extract_frontmatter_field(content, "title") == "Todo task"
        assert _extract_frontmatter_field(content, "created") == "2026-01-01"


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
        f.write_text("No file refs here.\n", encoding="utf-8")
        result = verify_references(tmp_path, f)
        assert result.valid is True
        assert result.total == 0

    def test_backtick_ref_found(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
        f = tmp_path / "test.md"
        f.write_text("See `src/main.py` for details.\n", encoding="utf-8")
        result = verify_references(tmp_path, f)
        assert result.valid is True
        assert result.found == 1

    def test_backtick_ref_missing(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("See `src/missing.py` for details.\n", encoding="utf-8")
        result = verify_references(tmp_path, f)
        assert result.valid is False
        assert "src/missing.py" in result.missing

    def test_at_ref_found(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "README.md").write_text("# Docs", encoding="utf-8")
        f = tmp_path / "test.md"
        f.write_text("@docs/README.md\n", encoding="utf-8")
        result = verify_references(tmp_path, f)
        assert result.valid is True
        assert result.found == 1

    def test_http_urls_skipped(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("See `http://example.com/foo.py`.\n", encoding="utf-8")
        result = verify_references(tmp_path, f)
        assert result.total == 0

    def test_template_vars_skipped(self, tmp_path):
        from gpd.core.frontmatter import verify_references

        f = tmp_path / "test.md"
        f.write_text("Use `${PROJECT}/src/foo.py` or `{{base}}/bar.py`.\n", encoding="utf-8")
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
        f.write_text("---\ntitle: test\n---\n\nNo artifacts.\n", encoding="utf-8")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False
        assert any("contract not found" in issue.lower() for artifact in result.artifacts for issue in artifact.issues)

    def test_contract_deliverable_exists(self, tmp_path):
        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "main.png").write_text("figure-bytes", encoding="utf-8")
        f = tmp_path / "plan.md"
        f.write_text(_valid_plan_contract_frontmatter() + "Body.\n", encoding="utf-8")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True
        assert result.passed_count == 1

    def test_project_root_relative_contract_anchor_uses_plan_path_context(self, tmp_path: Path) -> None:
        project_root = tmp_path
        phase_dir = project_root / "GPD" / "phases" / "01-benchmark"
        phase_dir.mkdir(parents=True)
        artifact = project_root / "artifacts" / "benchmark" / "report.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}", encoding="utf-8")
        baseline_dir = project_root / "GPD" / "phases" / "00-baseline"
        baseline_dir.mkdir(parents=True)
        (baseline_dir / "00-01-SUMMARY.md").write_text("baseline summary", encoding="utf-8")
        (phase_dir / "figures").mkdir()
        (phase_dir / "figures" / "benchmark.png").write_text("figure-bytes", encoding="utf-8")

        plan_path = phase_dir / "01-01-PLAN.md"
        plan_path.write_text(_project_local_plan_contract_frontmatter(), encoding="utf-8")

        result = verify_artifacts(project_root, plan_path)

        assert result.all_passed is True
        assert result.passed_count == 1

    def test_contract_deliverable_without_verifiable_path_fails_closed(self, tmp_path):
        f = tmp_path / "plan.md"
        content = _valid_plan_contract_frontmatter().replace("      path: figures/main.png\n", "", 1) + "Body.\n"
        f.write_text(content, encoding="utf-8")

        result = verify_artifacts(tmp_path, f)

        assert result.all_passed is False
        assert result.passed_count == 0
        assert result.total == 1
        assert any(
            "none have a verifiable path" in issue for artifact in result.artifacts for issue in artifact.issues
        )

    def test_contract_deliverable_missing(self, tmp_path):
        f = tmp_path / "plan.md"
        f.write_text(_valid_plan_contract_frontmatter() + "Body.\n", encoding="utf-8")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is False

    def test_contract_deliverable_must_contain_check(self, tmp_path):
        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "main.png").write_text("benchmark evidence\nreference within tolerance\n", encoding="utf-8")
        f = tmp_path / "plan.md"
        content = _valid_plan_contract_frontmatter(
            deliverable_must_contain=["benchmark evidence", "reference within tolerance"]
        ) + "Body.\n"
        f.write_text(content, encoding="utf-8")
        result = verify_artifacts(tmp_path, f)
        assert result.all_passed is True

    def test_contract_deliverable_missing_required_fragment(self, tmp_path):
        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "main.png").write_text("benchmark evidence only\n", encoding="utf-8")
        f = tmp_path / "plan.md"
        content = _valid_plan_contract_frontmatter(
            deliverable_must_contain=["benchmark evidence", "reference within tolerance"]
        ) + "Body.\n"
        f.write_text(content, encoding="utf-8")
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
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake: {}\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Missing benchmark decomposition]\n"
            "    disconfirming_observations: [The expected benchmark target is not the decisive observable]\n"
            "---\n\nBody.\n"
        )
        f.write_text(content, encoding="utf-8")
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
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake:\n"
            "    must_read_refs: [ref-main]\n"
            "    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]\n"
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
        f.write_text(content, encoding="utf-8")
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is True
        assert result.task_count == 1
        assert result.tasks[0].name == "Implement feature"
        assert result.tasks[0].has_action is True

    def test_missing_frontmatter_fields(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        f = tmp_path / "plan.md"
        f.write_text("---\nphase: 01-test\n---\n\nBody.\n", encoding="utf-8")
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
        f.write_text(content, encoding="utf-8")
        result = verify_plan_structure(tmp_path, f)
        assert any("missing <name>" in e for e in result.errors)

    def test_wave_gt1_empty_deps_warns(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = _valid_plan_contract_frontmatter().replace("wave: 1\n", "wave: 2\n") + "Body.\n"
        f = tmp_path / "plan.md"
        f.write_text(content, encoding="utf-8")
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
        f.write_text(content, encoding="utf-8")
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
        f.write_text(content, encoding="utf-8")
        result = verify_plan_structure(tmp_path, f)
        assert any("interactive is true" in e for e in result.errors)

    def test_incomplete_contract_is_reported(self, tmp_path):
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            "---\n"
            "phase: 01-test\nplan: 01\ntype: execute\nwave: 1\n"
            "depends_on: []\nfiles_modified: []\ninteractive: false\n"
            "contract:\n"
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake: {}\n"
            "  claims:\n"
            "    - id: claim-main\n"
            "      statement: Recover the benchmark value\n"
            "      deliverables: [deliv-main]\n"
            "  deliverables:\n"
            "    - id: deliv-main\n"
            "      kind: figure\n"
            "      path: figures/main.png\n"
            "      description: Main figure\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears after normalization fix]\n"
            "---\n\n"
            '<task type="code">\n'
            "  <name>Implement feature</name>\n"
            "  <action>Write the code</action>\n"
            "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content, encoding="utf-8")
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is False
        assert any("contract: missing acceptance_tests" in error for error in result.errors)

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
            "  schema_version: 1\n"
            "  scope:\n"
            "    question: What benchmark must this plan recover?\n"
            "  context_intake: {}\n"
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
        f.write_text(content, encoding="utf-8")
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
        f.write_text(content, encoding="utf-8")
        result = verify_plan_structure(tmp_path, f)
        assert result.valid is False
        assert any(error.startswith("must_haves:") for error in result.errors)

    @pytest.mark.parametrize(
        ("field_block", "expected_error"),
        [
            ("verification_inputs:\n  truths: []\n", "verification_inputs:"),
            ("contract_results:\n  claims: []\n", "contract_results:"),
            ("comparison_verdicts: []\n", "comparison_verdicts:"),
            ("suggested_contract_checks: []\n", "suggested_contract_checks:"),
        ],
    )
    def test_rejects_summary_or_verification_only_frontmatter_fields(
        self,
        tmp_path: Path,
        field_block: str,
        expected_error: str,
    ) -> None:
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            _valid_plan_contract_frontmatter().replace("---\n\n", f"{field_block}---\n\n", 1)
            + '<task type="code">\n'
            + "  <name>Implement feature</name>\n"
            + "  <files>src/main.py</files>\n"
            + "  <action>Write the code</action>\n"
            + "  <verify>Run tests</verify>\n"
            + "  <done>Tests pass</done>\n"
            + "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content, encoding="utf-8")

        result = verify_plan_structure(tmp_path, f)

        assert result.valid is False
        assert any(error.startswith(expected_error) for error in result.errors)

    def test_rejects_invalid_required_plan_scalar_types(self, tmp_path: Path) -> None:
        from gpd.core.frontmatter import verify_plan_structure

        content = (
            _valid_plan_contract_frontmatter().replace("wave: 1\n", 'wave: "one"\n', 1)
            + '<task type="code">\n'
            + "  <name>Implement feature</name>\n"
            + "  <files>src/main.py</files>\n"
            + "  <action>Write the code</action>\n"
            + "  <verify>Run tests</verify>\n"
            + "  <done>Tests pass</done>\n"
            + "</task>\n"
        )
        f = tmp_path / "plan.md"
        f.write_text(content, encoding="utf-8")

        result = verify_plan_structure(tmp_path, f)

        assert result.valid is False
        assert "wave: expected an integer" in result.errors



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


# ─── FULL-019: depends_on integer coercion ───────────────────────────────────


def test_validate_non_empty_string_list_field_coerces_integers():
    """FULL-019: depends_on: [5] should be accepted after int-to-str coercion."""
    from gpd.core.frontmatter import _validate_non_empty_string_list_field

    meta: dict[str, object] = {"depends_on": [5, "PLAN-02"]}
    errors: list[str] = []
    _validate_non_empty_string_list_field(meta, "depends_on", errors)
    assert errors == []
    assert meta["depends_on"] == ["5", "PLAN-02"]


def test_validate_non_empty_string_list_field_rejects_bool():
    """Booleans must not be coerced (isinstance(True, int) is True in Python)."""
    from gpd.core.frontmatter import _validate_non_empty_string_list_field

    meta: dict[str, object] = {"depends_on": [True]}
    errors: list[str] = []
    _validate_non_empty_string_list_field(meta, "depends_on", errors)
    assert len(errors) == 1


def test_validate_non_empty_string_list_field_coerces_float():
    """Float phase numbers like 72.1 (decimal phases) should be coerced."""
    from gpd.core.frontmatter import _validate_non_empty_string_list_field

    meta: dict[str, object] = {"depends_on": [72.1]}
    errors: list[str] = []
    _validate_non_empty_string_list_field(meta, "depends_on", errors)
    assert errors == []
    assert meta["depends_on"] == ["72.1"]
