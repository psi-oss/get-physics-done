from __future__ import annotations

import re
from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes
from gpd.core.frontmatter import validate_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _read_verifier_prompt() -> str:
    return (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")


def _read_verification_template() -> str:
    return (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")


def _read_research_verification_template() -> str:
    return (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")


def _read_verify_work_template() -> str:
    return (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")


def _read_expanded_verifier_prompt() -> str:
    return expand_at_includes(_read_verifier_prompt(), REPO_ROOT / "src/gpd", "/runtime/")


def _read_example_frontmatter(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r"```markdown\n(.*?)\n```", content, re.S)
    assert match is not None
    return match.group(1)


def test_verifier_prompt_points_to_canonical_verification_schema_sources() -> None:
    verifier = _read_verifier_prompt()
    expanded_verifier = _read_expanded_verifier_prompt()
    expanded_lines = expanded_verifier.splitlines()

    assert "templates/verification-report.md" in verifier
    assert "templates/contract-results-schema.md" in verifier
    assert "references/shared/canonical-schema-discipline.md" in verifier
    assert (
        "Immediately before writing or validating `VERIFICATION.md`, load the canonical schema references on demand:"
        in verifier
    )
    assert "## Canonical LLM Error References" in verifier
    assert (
        "include a machine-readable `ASSERT_CONVENTION` comment immediately after the YAML frontmatter in `VERIFICATION.md`."
        in verifier
    )
    assert (
        "Changed phase verification artifacts now fail `gpd pre-commit-check` if the required header is missing or mismatched."
        in verifier
    )
    assert "Prefer copy-pasteable GPD commands" not in verifier
    assert "## Data Boundary" not in verifier
    for legacy_alias in ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"):
        assert legacy_alias not in verifier
    assert verifier.count("templates/verification-report.md") == 1
    assert verifier.count("templates/contract-results-schema.md") == 1
    assert verifier.count("references/shared/canonical-schema-discipline.md") == 1
    assert "verifier-profile-checks.md" not in expanded_lines


def test_verifier_prompt_surfaces_validator_enforced_contract_ledger_rules() -> None:
    verifier = _read_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    assert "Do not restate the schema from memory." in verifier
    assert (
        "Treat those files as the source of truth for `plan_contract_ref`, `contract_results`, "
        "`comparison_verdicts`, `suggested_contract_checks`, proof-audit fields"
    ) in verifier
    assert (
        "If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is required." not in verifier
    )
    assert "Schema guard:" in verifier
    assert "project-only IDs go in body/unbound suggestions" in verifier
    assert "No `gpd_return`, `computational_oracle`, or runtime fields in frontmatter" in verifier
    assert "Oracle in body; return after report." in verifier
    assert "Unclear `evidence[]`: use parent `summary` / `notes`." in verifier
    assert "plan_contract_ref: GPD/phases/XX-name/XX-YY-PLAN.md#/contract" in contract_results_schema
    assert (
        "`contract_results` is keyed to `plan_contract_ref`; project-only IDs belong in body" in contract_results_schema
    )
    assert "never `kind`, `path`, `source`, `summary`, `actual_output`, or `command`" in contract_results_schema
    assert (
        "Every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the referenced "
        "PLAN contract must appear in the matching section."
    ) in contract_results_schema
    assert "`uncertainty_markers` must remain explicit in contract-backed outputs" in contract_results_schema
    assert (
        "Only `subject_role: decisive` satisfies a required decisive comparison or participates in pass/fail "
        "consistency checks against `contract_results`."
    ) in contract_results_schema
    assert (
        "When a reference-backed decisive comparison is required, use `comparison_kind: benchmark`, `prior_work`, "
        "`experiment`, `baseline`, or `cross_method`. `comparison_kind: other` does not satisfy that requirement."
    ) in contract_results_schema
    assert (
        "Each `suggested_contract_checks` entry may only use these keys: `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path`."
        in contract_results_schema
    )
    assert (
        "Copy the `check_key` returned by `suggest_contract_checks(contract)` into the frontmatter `check` field"
        in contract_results_schema
    )
    assert (
        "If you bind a `suggested_contract_checks` entry to a known contract target, `suggested_subject_kind` and `suggested_subject_id` must appear together; otherwise omit both."
        in contract_results_schema
    )
    assert "For each suggested check, start from `request_template`" in verifier
    assert "`schema_required_request_fields`" in verifier
    assert "`schema_required_request_anyof_fields`" in verifier
    assert "satisfy one full alternative from `schema_required_request_anyof_fields`" in verifier
    assert "keep `project_dir` as the top-level absolute project root argument" in verifier
    assert "bind only `supported_binding_fields`" in verifier
    assert "Execute `run_contract_check(request=..., project_dir=...)`." in verifier
    assert "required reference actions missing" in verifier
    assert "`suggested_contract_check`" not in verifier


def test_verifier_prompt_keeps_reference_actions_within_the_canonical_enum() -> None:
    verifier = _read_verifier_prompt()

    assert "Verify the required action (`read`, `compare`, `cite`, etc.) was actually completed" in verifier
    assert (
        "Verify the required action (`read`, `compare`, `cite`, `reproduce`, etc.) was actually completed"
        not in verifier
    )


def test_verifier_prompt_loads_conventions_from_state_json_with_degraded_state_md_fallback() -> None:
    verifier = _read_verifier_prompt()

    assert "**Load conventions from `state.json` `convention_lock` first.**" in verifier
    assert "`state.json` is the machine-readable source of truth." in verifier
    assert "use `STATE.md` only as a degraded fallback" in verifier
    assert "Do NOT parse STATE.md for conventions" not in verifier


def test_verifier_prompt_reloads_the_canonical_schema_files_once() -> None:
    verifier = _read_verifier_prompt()

    assert verifier.count("templates/verification-report.md") == 1
    assert verifier.count("templates/contract-results-schema.md") == 1
    assert verifier.count("references/shared/canonical-schema-discipline.md") == 1
    assert "load the canonical schema references on demand" in verifier
    assert "from Step 2" not in verifier


def test_verifier_prompt_surfaces_schema_sources_before_the_verification_writer_section() -> None:
    verifier = _read_verifier_prompt()
    create_verification_section = verifier.index("## Create VERIFICATION.md")

    assert verifier.index("templates/verification-report.md") < create_verification_section
    assert verifier.index("templates/contract-results-schema.md") < create_verification_section
    assert verifier.index("references/shared/canonical-schema-discipline.md") < create_verification_section


def test_verifier_prompt_frontmatter_example_includes_contract_ledgers() -> None:
    verifier = _read_verifier_prompt()
    verification_template = _read_verification_template()

    assert "plan_contract_ref" in verifier
    assert "contract_results" in verifier
    assert "comparison_verdicts" in verifier
    assert "suggested_contract_checks" in verifier
    assert "\nindependently_confirmed:" not in verifier
    assert (
        "<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->"
        in verifier
    )
    assert "filler placeholders" not in verifier
    assert "Use the loaded canonical report template and result-ledger schema" in verifier
    assert "### Validation Stop Rule" in verifier
    assert "max two targeted repairs" in verifier
    assert "`gpd_return.status: blocked` with latest errors" in verifier
    assert "No aliases or empty evidence to pass." in verifier
    assert "### Frontmatter Schema (YAML)" not in verifier
    assert "Verification reports are the decisive readout of the same contract-backed ledger" in verification_template
    assert "Frontmatter is not the return channel: no `gpd_return`, `computational_oracle`" in verification_template
    assert "oracle in body, return after." in verification_template


def test_shipped_verification_examples_roundtrip_through_the_verification_validator() -> None:
    result = validate_frontmatter(_read_example_frontmatter(TEMPLATES_DIR / "research-verification.md"), "verification")

    assert result.valid is True
    assert result.errors == []


def test_verifier_prompt_uses_canonical_include_for_worked_examples() -> None:
    verifier = _read_verifier_prompt()

    assert (
        "<!-- Stub detection patterns extracted to reduce context. Load on demand from `references/verification/examples/verifier-worked-examples.md`. -->"
        in verifier
    )
    assert "## Physics Stub Detection Patterns" not in verifier
    assert "Load on demand from `references/verification/examples/verifier-worked-examples.md`." in verifier
    assert "all artifacts pass levels 1-4" in verifier


def test_verifier_prompt_surfaces_missing_parameter_proof_audit_and_stale_review_gate() -> None:
    verifier = _read_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    research_verification = _read_research_verification_template()
    verification_template = _read_verification_template()

    assert "## Physics Stub Detection Patterns" not in verifier
    assert (
        "<!-- Stub detection patterns extracted to reduce context. Load on demand from `references/verification/examples/verifier-worked-examples.md`. -->"
        in verifier
    )
    assert "proof-audit fields, status vocabularies, ID linkage, and stale-audit handling" in verifier
    assert (
        "Every named theorem parameter or hypothesis is used or explicitly discharged; no theorem symbol may disappear without explanation"
        not in verifier
    )
    assert (
        "For `contract_results`, use the referenced `ProjectContract` (`project_contract.claims[]` / `ContractClaim`) semantics"
        in contract_results_schema
    )
    assert "Do not substitute the staged peer-review Paper `ClaimRecord` rule here" in contract_results_schema
    assert (
        "A quantified proof-bearing claim must keep `proof_audit.quantifier_status` explicit" in contract_results_schema
    )
    assert "unquantified proof-bearing claims do not need a non-empty quantifier list" in contract_results_schema
    assert (
        "`proof_artifact_path`, `proof_artifact_sha256`, `audit_artifact_path`, `audit_artifact_sha256`, `claim_statement_sha256`"
        in contract_results_schema
    )
    assert (
        "`proof_audit.proof_artifact_path` must match a declared `proof_deliverables` path" in contract_results_schema
    )
    assert "`proof_audit.audit_artifact_path` must point to a proof-redteam artifact" in contract_results_schema
    assert (
        "every declared proof-specific acceptance test in `claims[].acceptance_tests[]` passing"
        in contract_results_schema
    )
    assert "Verification reports are the decisive readout of the same contract-backed ledger" in verification_template
    assert "## Canonical Report Surface" in verification_template
    assert "machine-readable surface limited to schema-owned ledgers" in verification_template
    assert "status: passed` is strict" in verification_template
    assert "every required decisive comparison is decisive" in verification_template
    assert "record structured `suggested_contract_checks` instead of padding prose" in verification_template
    assert "Proof-backed claims follow the proof-audit rules in the canonical schema" in verification_template
    assert "completed_actions: []" not in verification_template
    assert "missing_actions: [read]" not in verification_template
    assert "phase: 01-benchmark" in research_verification
    assert 'summary: "[what the adversarial proof review concluded]"' in research_verification
    assert (
        'recommended_action: "collect one more benchmark point before marking the claim as passed"'
        in research_verification
    )
    assert "all artifacts pass levels 1-4" in verifier
    assert "all artifacts pass levels 1-3" not in verifier


def test_research_verification_template_uses_concrete_example_values() -> None:
    research_verification = _read_research_verification_template()

    assert "phase: 01-benchmark" in research_verification
    assert 'name: "benchmark comparison"' in research_verification
    assert 'reference_ids: ["reference-main"]' in research_verification
    assert 'comparison_reference_id: "reference-main"' in research_verification
    assert 'expected: "The benchmark comparison should land within the 1% tolerance."' in research_verification
    assert "The benchmark evidence is close but not yet decisive." in research_verification
    assert "The contract still needs a named benchmark check for the main claim." in research_verification
    assert "source:" in research_verification


def test_verify_work_template_keeps_session_overlay_after_verifier_output() -> None:
    verify_work = _read_verify_work_template()

    assert (
        "Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true."
        in verify_work
    )
    assert (
        "Stable knowledge docs that appear there are reviewed background synthesis: use them to clarify definitions, "
        "assumptions, and caveats only when they agree with stronger sources, and never as decisive evidence on their own."
        in verify_work
    )
    assert "Human-readable headings in the verifier output are presentation only;" in verify_work
    assert "route on the canonical verification frontmatter and `gpd_return.status`" in verify_work
    assert "Schema finalization is bounded" in verify_work
    assert "after two schema-only repair failures" in verify_work
    assert "Do not patch canonical verification frontmatter in this wrapper." in verify_work
    assert "The verification overlay is written only after authoritative verifier output is available" in verify_work
    assert "canonical verifier report content remains owned by `gpd-verifier`" in verify_work
    assert "Every spawned agent is a one-shot delegation" in verify_work
    assert "research_mode=balanced" not in verify_work
