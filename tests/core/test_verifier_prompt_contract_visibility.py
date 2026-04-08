from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

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


def test_verifier_prompt_points_to_canonical_verification_schema_sources() -> None:
    verifier = _read_verifier_prompt()
    expanded_verifier = _read_expanded_verifier_prompt()
    verifier_lines = verifier.splitlines()
    expanded_lines = expanded_verifier.splitlines()

    assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" in verifier_lines
    assert "@{GPD_INSTALL_DIR}/references/verification/meta/verifier-profile-checks.md" in verifier_lines
    assert "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md" in verifier_lines
    assert "Immediately before writing frontmatter, reload those canonical schema files and obey those ledger rules literally." in verifier
    assert "## Data Boundary" not in verifier
    assert "## Canonical LLM Error References" in verifier
    assert "`@{GPD_INSTALL_DIR}/references/verification/errors/llm-physics-errors.md` -- index and entry point" in verifier
    assert "`@{GPD_INSTALL_DIR}/references/verification/errors/llm-errors-traceability.md` -- compact detection matrix" in verifier
    assert "Load only the split file(s) needed for the current physics context." in verifier
    assert "include a machine-readable `ASSERT_CONVENTION` comment immediately after the YAML frontmatter in `VERIFICATION.md`." in verifier
    assert "Changed phase verification artifacts now fail `gpd pre-commit-check` if the required header is missing or mismatched." in verifier
    assert "## Data Boundary" in expanded_verifier
    assert "ask the user before any install attempt" in expanded_verifier
    assert "Prefer copy-pasteable GPD commands" in expanded_verifier
    assert "# Verifier Profile-Specific Checks" in expanded_verifier
    assert "[] Proof structure" in expanded_verifier
    assert (
        "Use the explicitly loaded schema, template, and contract/reference files that define an output shape or "
        "validation gate as the authority."
    ) in expanded_verifier
    for legacy_alias in ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"):
        assert legacy_alias not in verifier
    assert "@{GPD_INSTALL_DIR}/templates/verification-report.md" in verifier_lines
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in verifier_lines
    assert verifier_lines.count("@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md") == 1
    assert "@{GPD_INSTALL_DIR}/references/verification/meta/verifier-profile-checks.md" not in expanded_lines


def test_verifier_prompt_surfaces_validator_enforced_contract_ledger_rules() -> None:
    verifier = _read_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    assert "If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is required." in verifier
    assert "`plan_contract_ref` must be a string ending with the exact `#/contract` fragment and it must resolve to the matching PLAN contract on disk." in verifier
    assert "`contract_results` must cover every declared claim, deliverable, acceptance test, reference, and forbidden proxy ID from the PLAN contract." in verifier
    assert "contract_results.uncertainty_markers" in verifier
    assert "Do not invent `artifact` or other ad hoc subject kinds." in verifier
    assert "Only `subject_role: decisive` satisfies a required decisive comparison or participates in pass/fail consistency checks against `contract_results`" in verifier
    assert "record `verdict: inconclusive` or `verdict: tension` instead of omitting the entry." in verifier
    assert "For reference-backed decisive comparisons, only `comparison_kind: benchmark|prior_work|experiment|baseline|cross_method` satisfies the requirement; `comparison_kind: other` does not." in verifier
    assert "`suggested_contract_checks` entries in `VERIFICATION.md` may only use `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path`." in verifier
    assert "When the gap comes from `suggest_contract_checks(contract)`, `check` must copy the returned `check_key`." in verifier
    assert "If you bind a `suggested_contract_checks` entry to a known contract target, `suggested_subject_kind` and `suggested_subject_id` must appear together; otherwise omit both." in contract_results_schema
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
    assert "Verify the required action (`read`, `compare`, `cite`, `reproduce`, etc.) was actually completed" not in verifier


def test_verifier_prompt_loads_conventions_from_state_json_with_degraded_state_md_fallback() -> None:
    verifier = _read_verifier_prompt()

    assert "**Load conventions from `state.json` `convention_lock` first.**" in verifier
    assert "`state.json` is the machine-readable source of truth." in verifier
    assert "use `STATE.md` only as a degraded fallback" in verifier
    assert "Do NOT parse STATE.md for conventions" not in verifier


def test_verifier_prompt_reloads_the_canonical_schema_files_once() -> None:
    verifier = _read_verifier_prompt()

    assert verifier.count("@{GPD_INSTALL_DIR}/templates/verification-report.md") == 1
    assert verifier.count("@{GPD_INSTALL_DIR}/templates/contract-results-schema.md") == 1
    assert verifier.count("@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md") == 1
    assert "reload those canonical schema files and obey those ledger rules literally." in verifier
    assert "from Step 2" not in verifier


def test_verifier_prompt_frontmatter_example_includes_contract_ledgers() -> None:
    verifier = _read_verifier_prompt()

    assert "plan_contract_ref" in verifier
    assert "contract_results" in verifier
    assert "comparison_verdicts" in verifier
    assert "suggested_contract_checks" in verifier
    assert "\nindependently_confirmed:" not in verifier
    assert "<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->" in verifier
    assert "filler placeholders" not in verifier


def test_verifier_prompt_uses_canonical_include_for_worked_examples() -> None:
    verifier = _read_verifier_prompt()

    assert "@{GPD_INSTALL_DIR}/references/verification/examples/verifier-worked-examples.md" in verifier
    assert "<!-- [included: verifier-worked-examples.md] -->" not in verifier
    assert "<!-- [end included] -->" not in verifier
    assert "result = 0  # placeholder" not in verifier
    assert '"energy": "TODO", "status": "not computed"' not in verifier
    assert "phase: 01-benchmark" in verifier
    assert "score: 3/5 contract targets verified" in verifier


def test_verifier_prompt_surfaces_missing_parameter_proof_audit_and_stale_review_gate() -> None:
    verifier = _read_verifier_prompt()
    expanded_verifier = _read_expanded_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    research_verification = _read_research_verification_template()
    verification_template = _read_verification_template()

    assert "## Physics Stub Detection Patterns" not in verifier
    assert "## Physics Stub Detection Patterns" in expanded_verifier
    assert "## 5.15 Anomalies/Topological Properties — Executable Template" in expanded_verifier
    assert "[] Proof structure" in expanded_verifier
    assert (
        "Every named theorem parameter or hypothesis is used or explicitly discharged; no theorem symbol may "
        "disappear without explanation"
    ) in expanded_verifier
    assert (
        "If the proof only establishes a narrower subcase than the stated theorem, downgrade the claim and "
        "name the missing hypothesis/parameter coverage"
    ) in expanded_verifier
    assert (
        "If the theorem statement or proof artifact changed after the last proof audit, treat the prior proof "
        "audit as stale and rerun before marking the target passed"
    ) in expanded_verifier
    assert (
        "Quantified proof claims keep `proof_audit.quantifier_status` explicit; passed quantified claims require `matched`"
    ) in expanded_verifier
    assert (
        "`proof_audit.proof_artifact_path` matches a declared `proof_deliverables` path and "
        "`proof_audit.audit_artifact_path` points to the canonical proof-redteam artifact"
    ) in expanded_verifier
    assert "A quantified proof-bearing claim must keep `proof_audit.quantifier_status` explicit" in contract_results_schema
    assert "`claim_kind` is `theorem|lemma|corollary|proposition|claim`" in contract_results_schema
    assert "`proof_artifact_path`, `proof_artifact_sha256`, `audit_artifact_path`, `audit_artifact_sha256`, `claim_statement_sha256`" in contract_results_schema
    assert "`proof_audit.proof_artifact_path` must match a declared `proof_deliverables` path" in contract_results_schema
    assert "`proof_audit.audit_artifact_path` must point to a proof-redteam artifact" in contract_results_schema
    assert "every declared proof-specific acceptance test in `claims[].acceptance_tests[]` passing" in contract_results_schema
    assert "Verification reports are the decisive readout of the same contract-backed ledger" in verification_template
    assert "## Canonical Report Surface" in verification_template
    assert "machine-readable surface limited to the schema-owned ledgers" in verification_template
    assert "status: passed` is strict" in verification_template
    assert "every required decisive comparison is decisive" in verification_template
    assert "record structured `suggested_contract_checks` instead of padding prose" in verification_template
    assert "Proof-backed claims follow the proof-audit rules in the canonical schema" in verification_template
    assert "completed_actions: []" not in verification_template
    assert "missing_actions: [read]" not in verification_template
    assert "phase: 01-benchmark" in research_verification
    assert 'summary: "[what the adversarial proof review concluded]"' in research_verification
    assert 'recommended_action: "collect one more benchmark point before marking the claim as passed"' in research_verification
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
    assert 'source:' in research_verification


def test_verify_work_template_sets_balanced_default_and_concrete_examples() -> None:
    verify_work = _read_verify_work_template()

    assert "- `research_mode=balanced` (default): Keep the full contract-critical floor and the balanced review cadence." in verify_work
    assert (
        "Stable knowledge docs that appear there are reviewed background synthesis: use them to clarify definitions, "
        "assumptions, and caveats only when they agree with stronger sources, and never as decisive evidence on their own."
        in verify_work
    )
    assert "plan_contract_ref: GPD/phases/01-benchmark/01-plan-PLAN.md#/contract" in verify_work
    assert 'name: "benchmark comparison"' in verify_work
    assert 'reference_ids: ["reference-main"]' in verify_work
    assert 'comparison_reference_id: "reference-main"' in verify_work
    assert "Evaluated the benchmark at the configured test points." in verify_work
    assert "Independent arithmetic gives a relative error of 0.006." in verify_work
