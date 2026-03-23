from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"


def _read_verifier_prompt() -> str:
    return (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")


def test_verifier_prompt_points_to_canonical_verification_schema_sources() -> None:
    verifier = _read_verifier_prompt()
    verifier_lines = verifier.splitlines()

    assert "`@{GPD_INSTALL_DIR}/templates/verification-report.md` is the canonical `VERIFICATION.md` frontmatter/body surface." in verifier
    assert "`@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` is the canonical source of truth for `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and verification-side `suggested_contract_checks`." in verifier
    assert "Do not invent a verifier-local schema, relax required ledgers, or treat body prose as a substitute for frontmatter consumed by validation and downstream tooling." in verifier
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

    assert "plan_contract_ref: .gpd/phases/{phase_number}-{phase_name}/{phase_number}-{plan}-PLAN.md#/contract" in verifier
    assert "contract_results:" in verifier
    assert "uncertainty_markers:" in verifier
    assert "comparison_verdicts:    # Required when a decisive comparison was required or attempted" in verifier
    assert "subject_kind: claim|deliverable|acceptance_test|reference" in verifier
    assert "subject_role: decisive|supporting|supplemental|other" in verifier
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" in verifier
