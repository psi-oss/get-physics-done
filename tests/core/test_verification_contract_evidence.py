from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent, indent

import pytest

from gpd.core.frontmatter import validate_frontmatter, verify_summary

FIXTURES_STAGE0 = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
FIXTURES_STAGE4 = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"


def _summary_with_reference_usage(*, status: str, completed_actions: str, missing_actions: str) -> str:
    return (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("status: completed", f"status: {status}", 1)
        .replace("completed_actions: [read, compare, cite]", f"completed_actions: {completed_actions}", 1)
        .replace("missing_actions: []", f"missing_actions: {missing_actions}", 1)
    )


def _verification_with_contract_results() -> str:
    return (
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      status: rejected\n"
            "comparison_verdicts:\n",
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      status: rejected\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n"
            "comparison_verdicts:\n",
            1,
        )
    )


def _proof_claim_statement() -> str:
    return "For all x > 0 and r_0 >= 0, F(x, r_0) >= 0."


def _proof_claim_statement_sha256() -> str:
    return hashlib.sha256(_proof_claim_statement().encode("utf-8")).hexdigest()


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _proof_artifact_path(phase_dir: Path) -> Path:
    return phase_dir / "derivations" / "theorem-proof.tex"


def _proof_redteam_artifact_path(phase_dir: Path) -> Path:
    return phase_dir / "01-01-PROOF-REDTEAM.md"


def _proof_audit_block(
    phase_dir: Path,
    *,
    completeness: str = "complete",
    reviewed_at: str = "2026-04-02T12:00:00Z",
    reviewer: str = "gpd-check-proof",
    proof_artifact_path: str = "derivations/theorem-proof.tex",
    proof_artifact_sha256: str | None = None,
    audit_artifact_path: str = "01-01-PROOF-REDTEAM.md",
    audit_artifact_sha256: str | None = None,
    claim_statement_sha256: str | None = None,
    covered_hypothesis_ids: str = "[hyp-r0, hyp-x]",
    missing_hypothesis_ids: str = "[]",
    covered_parameter_symbols: str = "[r_0, x]",
    missing_parameter_symbols: str = "[]",
    uncovered_quantifiers: str = "[]",
    uncovered_conclusion_clause_ids: str = "[]",
    quantifier_status: str = "matched",
    scope_status: str = "matched",
    counterexample_status: str = "none_found",
    stale: str = "false",
) -> str:
    resolved_proof_artifact_sha256 = (
        _sha256_path(_proof_artifact_path(phase_dir)) if proof_artifact_sha256 is None else proof_artifact_sha256
    )
    resolved_audit_artifact_sha256 = (
        _sha256_path(_proof_redteam_artifact_path(phase_dir)) if audit_artifact_sha256 is None else audit_artifact_sha256
    )
    resolved_claim_statement_sha256 = _proof_claim_statement_sha256() if claim_statement_sha256 is None else claim_statement_sha256
    return (
        "      proof_audit:\n"
        f"        completeness: {completeness}\n"
        f'        reviewed_at: "{reviewed_at}"\n'
        f"        reviewer: {reviewer}\n"
        f"        proof_artifact_path: {proof_artifact_path}\n"
        f"        proof_artifact_sha256: {resolved_proof_artifact_sha256}\n"
        f"        audit_artifact_path: {audit_artifact_path}\n"
        f"        audit_artifact_sha256: {resolved_audit_artifact_sha256}\n"
        f"        claim_statement_sha256: {resolved_claim_statement_sha256}\n"
        f"        covered_hypothesis_ids: {covered_hypothesis_ids}\n"
        f"        missing_hypothesis_ids: {missing_hypothesis_ids}\n"
        f"        covered_parameter_symbols: {covered_parameter_symbols}\n"
        f"        missing_parameter_symbols: {missing_parameter_symbols}\n"
        f"        uncovered_quantifiers: {uncovered_quantifiers}\n"
        f"        uncovered_conclusion_clause_ids: {uncovered_conclusion_clause_ids}\n"
        f"        quantifier_status: {quantifier_status}\n"
        f"        scope_status: {scope_status}\n"
        f"        counterexample_status: {counterexample_status}\n"
        f"        stale: {stale}\n"
    )


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
            contract:
              schema_version: 1
              scope:
                question: Prove the full theorem without silently dropping r_0
              context_intake:
                must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]
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

            ## Proof Inventory
            - Exact claim / theorem text: For all x > 0 and r_0 >= 0, F(x, r_0) >= 0.
            - Claim / theorem target: Nonnegativity over the full stated domain.
            - Named parameters:
              - `r_0`: nonnegative real
              - `x`: positive real
            - Hypotheses:
              - `hyp-r0`: r_0 >= 0
              - `hyp-x`: x > 0
            - Quantifier / domain obligations:
              - for all x > 0
              - for all r_0 >= 0
            - Conclusion clauses:
              - `concl-main`: F(x, r_0) >= 0

            ## Coverage Ledger
            ### Named-Parameter Coverage
            | Parameter | Role / Domain | Proof Location | Status | Notes |
            | --- | --- | --- | --- | --- |
            | `r_0` | nonnegative real | theorem-proof.tex:12 | covered | Explicit in the bound. |
            | `x` | positive real | theorem-proof.tex:9 | covered | Used in the positivity step. |

            ### Hypothesis Coverage
            | Hypothesis | Proof Location | Status | Notes |
            | --- | --- | --- | --- |
            | `hyp-r0` | theorem-proof.tex:12 | covered | Used to keep the correction term nonnegative. |
            | `hyp-x` | theorem-proof.tex:9 | covered | Used in the base inequality. |

            ### Quantifier / Domain Coverage
            | Obligation | Proof Location | Status | Notes |
            | --- | --- | --- | --- |
            | `for all x > 0` | theorem-proof.tex:9 | covered | No specialization introduced. |
            | `for all r_0 >= 0` | theorem-proof.tex:12 | covered | Retained through the final inequality. |

            ### Conclusion-Clause Coverage
            | Clause | Proof Location | Status | Notes |
            | --- | --- | --- | --- |
            | `F(x, r_0) >= 0` | theorem-proof.tex:14 | covered | Final displayed inequality. |

            ## Adversarial Probe
            - Probe type: dropped-parameter test
            - Result: The proof still tracks r_0 in the correction term, so the full claim survives.

            ## Verdict
            - Scope status: `matched`
            - Quantifier status: `matched`
            - Counterexample status: `none_found`
            - Blocking gaps:
              - None.

            ## Required Follow-Up
            - None.
            """
        ),
        encoding="utf-8",
    )
    return phase_dir, plan_path


def _proof_verification_content(
    *,
    proof_audit_block: str,
    acceptance_test_status: str = "passed",
) -> str:
    proof_audit_text = indent(dedent(proof_audit_block).rstrip(), "              ")
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
{proof_audit_text}
          deliverables:
            deliv-proof:
              status: passed
              path: derivations/theorem-proof.tex
              summary: Proof artifact exists and matches the audited theorem.
              linked_ids: [claim-proof, test-proof-alignment]
          acceptance_tests:
            test-proof-alignment:
              status: {acceptance_test_status}
              summary: Proof-to-claim alignment review completed.
              linked_ids: [claim-proof, deliv-proof]
          references: {{}}
          forbidden_proxies:
            fp-proof:
              status: rejected
          uncertainty_markers:
            weakest_anchors: [Counterexample search explored the stated regime only]
            disconfirming_observations: [A counterexample at r_0 > 0 invalidates the theorem]
        comparison_verdicts: []
        ---

        # Verification

        Proof verification fixture.
        """
    )


def test_validate_frontmatter_summary_accepts_contract_results() -> None:
    content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8")

    result = validate_frontmatter(content, "summary")

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_rejects_missing_uncertainty_markers_for_contract_backed_summary() -> None:
    content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
        "",
        1,
    )

    result = validate_frontmatter(content, "summary")

    assert result.valid is False
    assert any("uncertainty_markers" in error for error in result.errors)


def test_validate_frontmatter_verification_accepts_contract_results() -> None:
    content = _verification_with_contract_results()

    result = validate_frontmatter(content, "verification")

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_rejects_passed_proof_claim_without_complete_proof_audit(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(proof_audit_block=_proof_audit_block(phase_dir, completeness="incomplete")),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert any("claim claim-proof status=passed requires proof_audit.completeness=complete" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_passed_proof_claim_without_passed_proof_specific_acceptance_test(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(phase_dir),
            acceptance_test_status="partial",
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
        "claim claim-proof status=passed requires all declared proof-specific acceptance_tests to pass"
        in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_accepts_complete_passed_proof_audit(tmp_path: Path) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(proof_audit_block=_proof_audit_block(phase_dir)),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_rejects_passed_proof_claim_when_named_parameter_disappears_from_coverage(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                covered_parameter_symbols="[x]",
            )
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert any("claim claim-proof proof_audit does not cover required parameter symbols: r_0" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_passed_proof_claim_with_unclear_quantifier_status(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                quantifier_status="unclear",
            ),
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
        "claim claim-proof proof_audit quantifier_status must be explicit for quantified claims" in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_proof_claim_with_proof_artifact_path_not_declared_in_contract(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    alternate_proof = phase_dir / "derivations" / "alternate-proof.tex"
    alternate_proof.write_text("% alternate theorem proof artifact\n", encoding="utf-8")
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                proof_artifact_path="derivations/alternate-proof.tex",
                proof_artifact_sha256=_sha256_path(alternate_proof),
            ),
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
        "claim claim-proof proof_audit.proof_artifact_path must match a declared proof_deliverables path"
        in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_proof_claim_with_non_redteam_audit_artifact_path(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    alternate_audit = phase_dir / "01-01-REVIEW.md"
    alternate_audit.write_text("# alternate proof review artifact\n", encoding="utf-8")
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                audit_artifact_path="01-01-REVIEW.md",
                audit_artifact_sha256=_sha256_path(alternate_audit),
            ),
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
        "claim claim-proof proof_audit.audit_artifact_path must point to a proof-redteam artifact"
        in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_proof_claim_with_stale_statement_hash(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    stale_statement_sha = hashlib.sha256(b"For all x > 0, F(x, 0) >= 0.").hexdigest()
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                claim_statement_sha256=stale_statement_sha,
            )
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
        "claim claim-proof proof_audit.claim_statement_sha256 does not match the current claim statement" in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_proof_claim_without_audit_artifact_hash(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                audit_artifact_sha256="",
            )
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert any("audit_artifact_sha256" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_passed_proof_claim_with_unreadable_audit_artifact(
    tmp_path: Path,
) -> None:
    phase_dir, _ = _write_proof_contract_phase(tmp_path)
    (_proof_redteam_artifact_path(phase_dir)).unlink()
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _proof_verification_content(
            proof_audit_block=_proof_audit_block(
                phase_dir,
                audit_artifact_sha256="a" * 64,
            )
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert any("proof_audit audit_artifact_path does not resolve to a readable file" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_status_passed_with_incomplete_reference_ledger(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    verification_path = phase_dir / "01-VERIFICATION.md"
    content = _verification_with_contract_results().replace(
        "    ref-benchmark:\n"
        "      status: completed\n"
        "      completed_actions: [read, compare, cite]\n"
        "      missing_actions: []\n",
        "    ref-benchmark:\n"
        "      status: not_applicable\n"
        "      completed_actions: []\n"
        "      missing_actions: []\n",
        1,
    )

    result = validate_frontmatter(content, "verification", source_path=verification_path)

    assert result.valid is False
    assert any("status: passed is inconsistent with non-completed contract_results references" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_missing_uncertainty_markers_for_contract_backed_verification() -> None:
    content = (FIXTURES_STAGE4 / "verification_with_contract_results.md").read_text(encoding="utf-8").replace(
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Verification spot-check coverage]\n"
        "    disconfirming_observations: [Independent rerun misses the benchmark tolerance]\n",
        "",
        1,
    )

    result = validate_frontmatter(content, "verification")

    assert result.valid is False
    assert any("uncertainty_markers" in error for error in result.errors)


@pytest.mark.parametrize(
    ("schema_name", "content"),
    [
        (
            "summary",
            (FIXTURES_STAGE4 / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "    claim-benchmark:\n"
                "      status: passed\n"
                "      summary: Benchmark claim verified against the decisive anchor.\n",
                "    claim-benchmark:\n"
                "      summary: Benchmark claim verified against the decisive anchor.\n",
                1,
            ),
        ),
        (
            "verification",
            (FIXTURES_STAGE4 / "verification_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "    claim-benchmark:\n"
                "      status: passed\n"
                "      summary: Claim independently verified.\n",
                "    claim-benchmark:\n"
                "      summary: Claim independently verified.\n",
                1,
            ),
        ),
    ],
)
def test_validate_frontmatter_contract_results_rejects_omitted_status_fields(
    schema_name: str,
    content: str,
) -> None:
    result = validate_frontmatter(content, schema_name)

    assert result.valid is False
    assert any("status must be explicit in contract-backed contract_results" in error for error in result.errors)


@pytest.mark.parametrize(
    ("schema_name", "content"),
    [
        (
            "summary",
            (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
                "  uncertainty_markers:\n"
                "    weakest_anchors: [Reference tolerance interpretation]\n"
                "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
                "  uncertainty_markers:\n"
                "    weakest_anchors: []\n"
                "    disconfirming_observations: []\n",
                1,
            ),
        ),
        (
            "verification",
            (FIXTURES_STAGE4 / "verification_with_contract_results.md").read_text(encoding="utf-8").replace(
                "  uncertainty_markers:\n"
                "    weakest_anchors: [Verification spot-check coverage]\n"
                "    disconfirming_observations: [Independent rerun misses the benchmark tolerance]\n",
                "  uncertainty_markers:\n"
                "    weakest_anchors: []\n"
                "    disconfirming_observations: []\n",
                1,
            ),
        ),
    ],
)
def test_validate_frontmatter_contract_results_rejects_empty_uncertainty_markers(
    schema_name: str,
    content: str,
) -> None:
    result = validate_frontmatter(content, schema_name)

    assert result.valid is False
    assert any("weakest_anchors must be non-empty" in error for error in result.errors)
    assert any("disconfirming_observations must be non-empty" in error for error in result.errors)


def test_validate_frontmatter_summary_with_source_path_checks_plan_alignment(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_with_source_path_accepts_canonical_plan_contract_ref(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


@pytest.mark.parametrize(
    ("ref_kind", "expected_error"),
    [
        ("absolute", "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"),
        ("external", "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"),
        ("relative", "plan_contract_ref: must reference a canonical project-root-relative GPD PLAN path"),
        ("traversal", "plan_contract_ref: must not traverse parent directories"),
    ],
)
def test_validate_frontmatter_summary_rejects_unsafe_plan_contract_refs(
    tmp_path: Path,
    ref_kind: str,
    expected_error: str,
) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    plan_path = artifact_dir / "01-01-PLAN.md"
    plan_path.write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_dir = artifact_dir / "nested"
    summary_dir.mkdir()
    summary_path = summary_dir / "01-SUMMARY.md"

    ref_value = {
        "absolute": f"{plan_path.resolve().as_posix()}#/contract",
        "external": "https://example.com/01-01-PLAN.md#/contract",
        "relative": "01-01-PLAN.md#/contract",
        "traversal": "../01-01-PLAN.md#/contract",
    }[ref_kind]
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract",
            f"plan_contract_ref: {ref_value}",
            1,
        ),
        encoding="utf-8",
    )

    schema_only_result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary")
    validation_result = validate_frontmatter(
        summary_path.read_text(encoding="utf-8"),
        "summary",
        source_path=summary_path,
    )
    verification_result = verify_summary(summary_dir, summary_path)

    assert validation_result.valid is False
    assert schema_only_result.valid is False
    assert verification_result.passed is False
    assert any(expected_error in error for error in schema_only_result.errors)
    assert any(expected_error in error for error in validation_result.errors)
    assert any(expected_error in error for error in verification_result.errors)


def test_validate_frontmatter_summary_with_source_path_rejects_non_contract_plan_fragment(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = artifact_dir / "01-01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/not-contract",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: must end with '#/contract'" in result.errors


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_contract_ids(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "claim-benchmark:",
            "claim-unknown:",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Unknown claim contract_results entry: claim-unknown" in error for error in result.errors)


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_linked_ids(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "linked_ids: [deliv-figure, test-benchmark, ref-benchmark]",
            "linked_ids: [deliv-figure, test-benchmark, ref-missing]",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        "claim claim-benchmark linked_ids references unknown contract id ref-missing" in error for error in result.errors
    )


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_evidence_bindings(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "reference_id: ref-benchmark",
            "reference_id: ref-missing",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        "claim claim-benchmark evidence references unknown reference_id ref-missing" in error for error in result.errors
    )


def test_validate_frontmatter_summary_with_source_path_accepts_forbidden_proxy_evidence_binding(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "          reference_id: ref-benchmark\n",
            "          reference_id: ref-benchmark\n"
            "          forbidden_proxy_id: fp-benchmark\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_forbidden_proxy_evidence_binding(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "          reference_id: ref-benchmark\n",
            "          reference_id: ref-benchmark\n"
            "          forbidden_proxy_id: fp-missing\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        "claim claim-benchmark evidence references unknown forbidden_proxy_id fp-missing" in error
        for error in result.errors
    )


def test_validate_frontmatter_summary_with_source_path_rejects_blank_optional_links_and_evidence_ids(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (
            (FIXTURES_STAGE4 / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "linked_ids: [deliv-figure, test-benchmark, ref-benchmark]",
                'linked_ids: [deliv-figure, "", test-benchmark, "  ", ref-benchmark]',
                1,
            )
            .replace(
                "reference_id: ref-benchmark",
                'reference_id: ""',
                1,
            )
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("linked_ids.1 must not be blank" in error for error in result.errors)


def test_validate_frontmatter_summary_with_source_path_reports_unresolved_plan_contract_ref(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: could not resolve matching plan contract" in result.errors


def test_validate_frontmatter_summary_does_not_resolve_plan_contract_ref_above_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "GPD").mkdir(parents=True)
    summary_dir = project_root / "artifacts" / "nested"
    summary_dir.mkdir(parents=True)
    summary_path = summary_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    external_phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    external_phase_dir.mkdir(parents=True)
    (external_phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    validation_result = validate_frontmatter(
        summary_path.read_text(encoding="utf-8"),
        "summary",
        source_path=summary_path,
    )
    verification_result = verify_summary(summary_dir, summary_path)

    assert validation_result.valid is False
    assert verification_result.passed is False
    assert "plan_contract_ref: could not resolve matching plan contract" in validation_result.errors
    assert "plan_contract_ref: could not resolve matching plan contract" in verification_result.errors


def test_validate_frontmatter_summary_with_source_path_reports_referenced_plan_contract_schema_errors(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("must_surface: true", 'must_surface: "yes"', 1),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: referenced PLAN contract: references.0.must_surface must be a boolean" in result.errors


def test_validate_frontmatter_summary_with_source_path_reports_referenced_plan_contract_semantic_errors(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace(
            "  acceptance_tests:\n"
            "    - id: test-benchmark\n"
            "      subject: claim-benchmark\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-figure, ref-benchmark]\n",
            "  acceptance_tests: []\n",
            1,
        ),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: referenced PLAN contract: missing acceptance_tests" in result.errors


def test_validate_frontmatter_verification_with_source_path_requires_contract_results(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        "---\n"
        "phase: 01-benchmark\n"
        "verified: 2026-03-13T00:00:00Z\n"
        "status: passed\n"
        "score: 1/1 contract targets verified\n"
        "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract\n"
        "---\n\n"
        "# Verification\n",
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert "contract_results: required for contract-backed plan" in result.errors


def test_validate_frontmatter_verification_with_adjacent_contract_backed_plan_requires_plan_contract_ref(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = artifact_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract\n",
            "",
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
    assert "plan_contract_ref: required for contract-backed plan" in result.errors


def test_validate_frontmatter_verification_with_source_path_accepts_canonical_plan_contract_ref(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(_verification_with_contract_results(), encoding="utf-8")

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_with_source_path_accepts_structured_suggested_contract_checks(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
            1,
        )
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive normalization benchmark comparison\n"
            "    reason: The reported agreement depends on a normalization-sensitive benchmark that is not yet explicit\n"
            "    suggested_subject_kind: acceptance_test\n"
            "    suggested_subject_id: test-benchmark\n"
            "    evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_with_source_path_accepts_partial_results_with_inconclusive_verdict(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
            1,
        ),
        encoding="utf-8",
    )
    verification_path.write_text(
        verification_path.read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: contract.benchmark_recovery\n"
            "    reason: Need a decisive benchmark comparison before this target can pass.\n"
            "    suggested_subject_kind: acceptance_test\n"
            "    suggested_subject_id: test-benchmark\n"
            "    evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_rejects_undocumented_suggested_contract_check_shape(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check_id: contract.benchmark_recovery\n"
            "    reason: Need a decisive benchmark comparison before this target can pass.\n"
            "comparison_verdicts:\n",
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
    assert any("suggested_contract_checks: [0] check is required" in error for error in result.errors)


def test_validate_frontmatter_summary_rejects_plan_contract_ref_that_points_to_different_plan(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("plan: 01\n", "plan: 02\n", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: could not resolve matching plan contract" in result.errors


def test_verify_summary_rejects_unresolved_plan_contract_ref(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: GPD/phases/01-benchmark/01-02-PLAN.md#/contract",
            1,
        ),
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "plan_contract_ref: could not resolve matching plan contract" in result.errors


def test_verify_summary_rejects_non_contract_plan_fragment(tmp_path: Path) -> None:
    plan_path = tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "GPD" / "phases" / "01-benchmark" / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/summary",
            1,
        ),
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "plan_contract_ref: must end with '#/contract'" in result.errors


def test_validate_frontmatter_summary_rejects_contradictory_comparison_verdict(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("verdict: pass", "verdict: fail", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("contradicts passed contract_results status" in error for error in result.errors)


@pytest.mark.parametrize(
    ("status", "completed_actions", "missing_actions", "message"),
    [
        ("completed", "[read]", "[compare]", "status=completed requires missing_actions to be empty"),
        (
            "not_applicable",
            "[read]",
            "[]",
            "status=not_applicable requires completed_actions and missing_actions to be empty",
        ),
        (
            "missing",
            "[read, compare]",
            "[compare]",
            "completed_actions and missing_actions must not overlap: compare",
        ),
    ],
)
def test_validate_frontmatter_summary_rejects_contradictory_reference_action_ledger(
    tmp_path: Path,
    status: str,
    completed_actions: str,
    missing_actions: str,
    message: str,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        _summary_with_reference_usage(
            status=status,
            completed_actions=completed_actions,
            missing_actions=missing_actions,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(message in error for error in result.errors)


def test_validate_frontmatter_verification_with_source_path_requires_suggested_contract_checks_for_partial_decisive_checks(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Decisive benchmark comparison remains open.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Benchmark comparison was attempted but is still open.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
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
    assert (
        "suggested_contract_checks: required when decisive benchmark/cross-method checks remain missing, partial, or incomplete"
        in result.errors
    )


def test_verify_summary_requires_contract_results_for_contract_backed_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(
        "---\nphase: 01-benchmark\nplan: 01\ndepth: full\nprovides: [benchmark comparison]\ncompleted: 2026-03-13\n---\n\n# Summary\n",
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "contract_results: required for contract-backed plan" in result.errors


def test_verify_summary_requires_plan_contract_ref_for_contract_backed_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(
        (
            (FIXTURES_STAGE4 / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace('plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract\n', "")
        ),
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "plan_contract_ref: required for contract-backed plan" in result.errors


def test_verify_summary_rejects_unknown_contract_ids(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "claim-benchmark:",
        "claim-unknown:",
        1,
    )
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "benchmark.png").write_text("placeholder", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "benchmark.py").write_text("print('ok')\n", encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Unknown claim contract_results entry: claim-unknown" in error for error in result.errors)


def test_verify_summary_allows_explicit_incomplete_contract_results_statuses(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "      status: passed\n      summary: Benchmark claim verified against the decisive anchor.\n",
            "      status: partial\n      summary: Benchmark comparison is still in progress.\n",
            1,
        )
        .replace(
            "      status: passed\n      path: figures/benchmark.png\n      summary: Figure produced with uncertainty band and benchmark overlay.\n",
            "      status: not_attempted\n      path: figures/benchmark.png\n      summary: Figure regeneration is queued behind the next run.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Benchmark reproduced within the contracted tolerance.\n",
            "      status: partial\n      summary: Initial comparison run completed but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: rejected\n      notes: Qualitative trend agreement was not accepted without the numerical benchmark check.\n",
            "      status: unresolved\n      notes: Proxy rejection will be finalized after the decisive rerun.\n",
            1,
        )
        .replace(
            "    verdict: pass\n    recommended_action: Keep this benchmark comparison in the paper.\n",
            "    verdict: inconclusive\n    recommended_action: Rerun the benchmark after the normalization fix.\n",
            1,
        )
    )
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "benchmark.png").write_text("placeholder", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "benchmark.py").write_text("print('ok')\n", encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is True


def test_validate_frontmatter_summary_rejects_missing_contract_results_coverage(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "  deliverables:\n"
            "    deliv-figure:\n"
            "      status: passed\n"
            "      path: figures/benchmark.png\n"
            "      summary: Figure produced with uncertainty band and benchmark overlay.\n"
            "      linked_ids: [claim-benchmark, test-benchmark]\n",
            "",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "Missing deliverable contract_results entry: deliv-figure" in result.errors


def test_validate_frontmatter_summary_rejects_mismatched_comparison_verdict_subject_kind(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("subject_kind: claim", "subject_kind: deliverable", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("has subject_kind deliverable but contract id is a claim" in error for error in result.errors)


def test_validate_frontmatter_summary_rejects_non_contract_comparison_verdict_subject_kind(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("subject_kind: claim", "subject_kind: artifact", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("comparison_verdicts:" in error and "acceptance_test' or 'reference'" in error for error in result.errors)


@pytest.mark.parametrize("role", ["supporting", "supplemental"])
def test_validate_frontmatter_summary_allows_non_decisive_comparison_tension_without_contradicting_passed_target(
    tmp_path: Path, role: str
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            f"    subject_role: {role}\n"
            "    reference_id: ref-benchmark\n"
            "    comparison_kind: prior_work\n"
            "    metric: chi2_ndof\n"
            '    threshold: "<= 1.5"\n'
            "    verdict: tension\n"
            "    recommended_action: Reconcile the auxiliary prior-work normalization.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_rejects_missing_subject_role_for_non_decisive_comparison_kind(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            "    comparison_kind: other\n"
            "    metric: chi2_ndof\n"
            '    threshold: "<= 1.5"\n'
            "    verdict: tension\n"
            "    recommended_action: Reconcile the auxiliary prior-work normalization.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("subject_role" in error for error in result.errors)


def test_validate_frontmatter_summary_requires_decisive_role_for_decisive_comparison_coverage(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("subject_role: decisive", "subject_role: supporting", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Missing decisive comparison_verdict for acceptance test test-benchmark" in error for error in result.errors)


@pytest.mark.parametrize("comparison_kind", ["benchmark", "prior_work", "experiment", "cross_method", "baseline"])
def test_validate_frontmatter_summary_rejects_missing_subject_role_for_decisive_comparison_kind(
    tmp_path: Path, comparison_kind: str
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    reference_line = "    reference_id: ref-benchmark\n" if comparison_kind not in {"cross_method"} else ""
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            f"{reference_line}"
            f"    comparison_kind: {comparison_kind}\n"
            "    metric: relative_error\n"
            '    threshold: "<= 0.02"\n'
            "    verdict: pass\n"
            "    recommended_action: Keep this comparison explicit in the record.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("subject_role" in error for error in result.errors)


@pytest.mark.parametrize("comparison_kind", ["benchmark", "prior_work", "experiment", "baseline"])
def test_validate_frontmatter_summary_rejects_unanchored_decisive_external_comparison(
    tmp_path: Path, comparison_kind: str
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            "    subject_role: decisive\n"
            f"    comparison_kind: {comparison_kind}\n"
            "    metric: relative_error\n"
            '    threshold: "<= 0.02"\n'
            "    verdict: pass\n"
            "    recommended_action: Keep this comparison explicit in the record.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        f"must include reference_id or use subject_kind: reference for decisive {comparison_kind} comparisons"
        in error
        for error in result.errors
    )


def test_validate_frontmatter_summary_requires_reference_backed_comparison_to_use_decisive_kind(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("kind: benchmark", "kind: existence", 1)
        .replace("procedure: Compare against the benchmark reference", "procedure: Confirm the artifact exists", 1)
        .replace("pass_condition: Matches reference within tolerance", "pass_condition: Artifact exists", 1),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "comparison_kind: benchmark",
            "comparison_kind: other",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "Missing decisive comparison_verdict for reference ref-benchmark" in result.errors


def test_validate_frontmatter_summary_rejects_prior_work_verdict_for_benchmark_acceptance_test(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("comparison_kind: benchmark", "comparison_kind: prior_work", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Missing decisive comparison_verdict for acceptance test test-benchmark" in error for error in result.errors)


def test_validate_frontmatter_summary_accepts_decisive_cross_method_without_reference_anchor(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("role: benchmark", "role: method", 1)
        .replace("required_actions: [read, compare, cite]", "required_actions: [read, cite]", 1)
        .replace("kind: benchmark", "kind: cross_method", 1)
        .replace("procedure: Compare against the benchmark reference", "procedure: Compare the independent methods", 1)
        .replace("pass_condition: Matches reference within tolerance", "pass_condition: Independent methods agree within tolerance", 1),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "    subject_role: decisive\n"
            "    reference_id: ref-benchmark\n"
            "    comparison_kind: benchmark\n",
            "    subject_role: decisive\n"
            "    comparison_kind: cross_method\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_rejects_contract_results_context_usage(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "  uncertainty_markers:\n",
            "  context_usage:\n"
            "    prior-baseline:\n"
            "      status: consulted\n"
            "      summary: Used prior baseline notes.\n"
            "  uncertainty_markers:\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("contract_results:" in error and "context_usage" in error for error in result.errors)


def test_validate_frontmatter_summary_requires_decisive_verdict_even_when_comparison_not_attempted(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    original = (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("status: passed\n      summary: Benchmark claim verified against the decisive anchor.\n", "status: not_attempted\n      summary: Benchmark claim remains open.\n", 1)
        .replace(
            "status: passed\n      summary: Benchmark reproduced within the contracted tolerance.\n",
            "status: not_attempted\n      summary: Benchmark comparison has not been run yet.\n",
            1,
        )
    )
    frontmatter, body = original.split("---\n\n", 1)
    trimmed_frontmatter = frontmatter.split("\ncomparison_verdicts:\n", 1)[0] + "\n---\n"
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(trimmed_frontmatter + "\n" + body, encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Missing decisive comparison_verdict for acceptance test test-benchmark" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_mismatched_suggested_contract_check_binding(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace("status: passed\nscore: 3/3 contract targets verified\n", "status: gaps_found\nscore: 3/3 contract targets verified\n", 1)
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive benchmark rerun\n"
            "    reason: The benchmark needs a narrower comparison window.\n"
            "    suggested_subject_kind: claim\n"
            "    suggested_subject_id: test-benchmark\n"
            "comparison_verdicts:\n",
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
    assert any("references test-benchmark as claim, but the contract declares it as acceptance_test" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_half_bound_suggested_contract_check(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace("status: passed\nscore: 3/3 contract targets verified\n", "status: gaps_found\nscore: 3/3 contract targets verified\n", 1)
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive benchmark rerun\n"
            "    reason: The benchmark needs a narrower comparison window.\n"
            "    suggested_subject_kind: acceptance_test\n"
            "comparison_verdicts:\n",
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
    assert any("must provide suggested_subject_kind and suggested_subject_id together" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_extra_keys_in_suggested_contract_check(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
            1,
        )
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive normalization benchmark comparison\n"
            "    reason: The reported agreement depends on a normalization-sensitive benchmark that is not yet explicit\n"
            "    suggested_subject_kind: acceptance_test\n"
            "    suggested_subject_id: test-benchmark\n"
            "    evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md\n"
            "    check_id: benchmark-gap\n"
            "comparison_verdicts:\n",
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
    assert any(
        "suggested_contract_checks: [0] check_id: Extra inputs are not permitted" in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_status_with_partial_contract_results(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Claim still needs the decisive rerun.\n",
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
    assert any(
        "status: passed is inconsistent with non-passed contract_results targets: claim claim-benchmark" in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_status_with_suggested_contract_checks(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive normalization benchmark comparison\n"
            "    reason: The decisive check is still pending.\n"
            "    suggested_subject_kind: claim\n"
            "    suggested_subject_id: claim-benchmark\n"
            "    evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n",
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
    assert "status: passed is inconsistent with non-empty suggested_contract_checks" in result.errors


def test_validate_frontmatter_verification_rejects_passed_status_with_unresolved_forbidden_proxy(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace("      status: rejected\n", "      status: unresolved\n", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert "status: passed is inconsistent with unresolved forbidden_proxies: fp-benchmark" in result.errors


def test_validate_frontmatter_verification_rejects_non_canonical_status(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results().replace("status: passed\n", "status: validating\n", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert "status: must be one of passed, gaps_found, expert_needed, human_needed" in result.errors


def test_verify_summary_requires_must_surface_reference_actions(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "completed_actions: [read, compare, cite]",
        "completed_actions: [read]",
        1,
    ).replace(
        "status: completed",
        "status: missing",
        1,
    ).replace(
        "missing_actions: []",
        "missing_actions: [compare, cite]",
        1,
    )
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Reference ref-benchmark missing required_actions in summary" in error for error in result.errors)


def test_verify_summary_requires_decisive_comparison_verdict_when_comparison_was_attempted(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    original = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8")
    frontmatter, body = original.split("---\n\n", 1)
    trimmed_frontmatter = frontmatter.split("\ncomparison_verdicts:\n", 1)[0] + "\n---\n"
    summary_content = trimmed_frontmatter + "\n" + body
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Missing decisive comparison_verdict" in error for error in result.errors)
