from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read_verifier_prompt() -> str:
    return (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")


def _read_verification_template() -> str:
    return (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")


def test_verifier_prompt_points_to_canonical_verification_schema_sources() -> None:
    verifier = _read_verifier_prompt()
    verifier_lines = verifier.splitlines()

    assert "`@{GPD_INSTALL_DIR}/templates/verification-report.md` is the canonical `VERIFICATION.md` frontmatter/body surface." in verifier
    assert "`@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` is the canonical source of truth for `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and verification-side `suggested_contract_checks`." in verifier
    assert "Do not invent a verifier-local schema, relax required ledgers, or treat body prose as a substitute for frontmatter consumed by validation and downstream tooling." in verifier
    assert "include a machine-readable `ASSERT_CONVENTION` comment immediately after the YAML frontmatter in `VERIFICATION.md`." in verifier
    assert "Changed phase verification artifacts now fail `gpd pre-commit-check` if the required header is missing or mismatched." in verifier
    assert "@{GPD_INSTALL_DIR}/templates/verification-report.md" in verifier_lines
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in verifier_lines


def test_verifier_prompt_surfaces_validator_enforced_contract_ledger_rules() -> None:
    verifier = _read_verifier_prompt()

    assert "If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is required." in verifier
    assert "`plan_contract_ref` must be a string ending with the exact `#/contract` fragment and it must resolve to the matching PLAN contract on disk." in verifier
    assert "`contract_results` must cover every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the PLAN contract." in verifier
    assert "contract_results.uncertainty_markers" in verifier
    assert "Do not invent `artifact` or other ad hoc subject kinds." in verifier
    assert "Only `subject_role: decisive` satisfies a required decisive comparison or participates in pass/fail consistency checks against `contract_results`" in verifier
    assert "record `verdict: inconclusive` or `verdict: tension` instead of omitting the entry." in verifier
    assert "For reference-backed decisive comparisons, only `comparison_kind: benchmark|prior_work|experiment|baseline|cross_method` satisfies the requirement; `comparison_kind: other` does not." in verifier
    assert "`suggested_contract_checks` entries in `VERIFICATION.md` may only use `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path`." in verifier
    assert "For each suggested check, start from its returned `request_template`, satisfy the listed `required_request_fields`, constrain any bindings to the returned `supported_binding_fields`, and then execute `run_contract_check(request=...)`" in verifier
    assert "required reference actions missing" in verifier
    assert "`suggested_contract_check`" not in verifier


def test_verifier_prompt_frontmatter_example_includes_contract_ledgers() -> None:
    verifier = _read_verifier_prompt()

    assert "plan_contract_ref: GPD/phases/{phase_number}-{phase_name}/{phase_number}-{plan}-PLAN.md#/contract" in verifier
    assert "contract_results:" in verifier
    assert "uncertainty_markers:" in verifier
    assert "comparison_verdicts:    # Required when a decisive comparison was required or attempted" in verifier
    assert "subject_kind: claim|deliverable|acceptance_test|reference" in verifier
    assert "subject_role: decisive|supporting|supplemental|other" in verifier
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" in verifier
    assert "weakest_anchors: [anchor-1]" in verifier
    assert "disconfirming_observations: [observation-1]" in verifier
    assert "<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->" in verifier
    assert "weakest_anchors: []" not in verifier
    assert "disconfirming_observations: []" not in verifier


def test_verifier_prompt_surfaces_missing_parameter_proof_audit_and_stale_review_gate() -> None:
    verifier = _read_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    verification_template = _read_verification_template()

    assert "[] Proof structure" in verifier
    assert (
        "Every named theorem parameter or hypothesis is used or explicitly discharged; no theorem symbol may "
        "disappear without explanation"
    ) in verifier
    assert (
        "If the proof only establishes a narrower subcase than the stated theorem, downgrade the claim and "
        "name the missing hypothesis/parameter coverage"
    ) in verifier
    assert (
        "If the theorem statement or proof artifact changed after the last proof audit, treat the prior proof "
        "audit as stale and rerun before marking the target passed"
    ) in verifier
    assert (
        "Quantified proof claims keep `proof_audit.quantifier_status` explicit; passed quantified claims require `matched`"
    ) in verifier
    assert (
        "`proof_audit.proof_artifact_path` matches a declared `proof_deliverables` path and "
        "`proof_audit.audit_artifact_path` points to the canonical proof-redteam artifact"
    ) in verifier
    assert "A quantified proof-bearing claim must keep `proof_audit.quantifier_status` explicit" in contract_results_schema
    assert "`proof_audit.proof_artifact_path` must match a declared `proof_deliverables` path" in contract_results_schema
    assert "`proof_audit.audit_artifact_path` must point to a proof-redteam artifact" in contract_results_schema

    assert "Proof-backed claims are stricter still" in verification_template
    assert "Quantified proof claims must keep `proof_audit.quantifier_status` explicit" in verification_template
    assert "the declared proof artifact path and the canonical proof-redteam artifact path" in verification_template
    assert "proof artifact, or proof-audit deliverable changed after the last adversarial proof review" in verification_template
    assert "A stale proof audit is never compatible with `status: passed`." in verification_template
