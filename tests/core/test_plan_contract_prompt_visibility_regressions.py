from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _expanded_template(name: str) -> str:
    return expand_at_includes(_read_template(name), REPO_ROOT / "src/gpd/specs", "/runtime/")


def test_plan_contract_schema_surfaces_defaultable_semantic_fields_and_hard_constraints() -> None:
    plan_schema = _expanded_template("plan-contract-schema.md")

    assert "observables[].kind" in plan_schema
    assert "deliverables[].kind" in plan_schema
    assert "acceptance_tests[].kind" in plan_schema
    assert "references[].kind" in plan_schema
    assert "references[].role" in plan_schema
    assert "links[].relation" in plan_schema
    assert "their default is `other`" in plan_schema
    assert "in_scope: [\"Recover the benchmark curve within tolerance\"]" in plan_schema
    assert "`scope.in_scope` is required and must name at least one project boundary or objective." in plan_schema
    assert "`context_intake`, `approach_policy`, and `uncertainty_markers` are object-valued sections, not strings or lists." in plan_schema
    assert "`approach_policy` is execution policy only; it can constrain planning, but it does not by itself satisfy the hard grounding/anchor requirement." in plan_schema
    assert "required and must be the integer `1`" in plan_schema
    assert "`must_surface` is a boolean scalar. Use the YAML literals `true` and `false`;" in plan_schema
    assert "The defaultable semantic fields above do not relax the hard requirements on `context_intake` or `uncertainty_markers`" in plan_schema
    assert "`contract.context_intake` is required and must be a non-empty object, not a string or list." in plan_schema
    assert "Use concrete anchors in `must_read_refs[]`" in plan_schema
    assert "`approach_policy` does not count as grounding on its own; use `context_intake`, preserved scoping inputs, or `references[]` for actual anchors." in plan_schema
    assert "Proof-bearing claims must use an explicit non-`other` `claim_kind`" in plan_schema
    assert (
        "`source` and `target` may only reference declared observable, claim, deliverable, acceptance-test, "
        "reference, forbidden-proxy, or link IDs."
    ) in plan_schema
    assert (
        "`references[]` are mandatory only when the contract does not already expose enough grounding through `context_intake` or preserved scoping inputs."
        in plan_schema
    )
    assert (
        "If `references[]` is non-empty and the contract does not already carry concrete grounding elsewhere, at least one reference must set `must_surface: true`."
        in plan_schema
    )
    assert "When concrete grounding already exists, a missing `must_surface: true` reference is a warning, not a blocker." in plan_schema
    assert "For non-scoping plans, `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` are all required." in plan_schema


def test_planner_prompt_surfaces_default_salvage_and_specific_semantics() -> None:
    planner_prompt = _read_template("planner-subagent-prompt.md")

    assert planner_prompt.count("## Standard Planning Template") == 1
    assert planner_prompt.count("## Revision Template") == 1
    assert planner_prompt.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    assert "**Project Contract Gate:** {project_contract_gate}" in planner_prompt
    assert "**Project Contract Load Info:** {project_contract_load_info}" in planner_prompt
    assert "**Project Contract Validation:** {project_contract_validation}" in planner_prompt
    for token in (
        "project_contract_gate.authoritative",
        "project_contract_load_info.status",
        "project_contract_validation.valid",
        "project_contract",
        "effective_reference_intake",
        "active_reference_context",
        "approach_policy",
        "scope.in_scope",
        "contract.context_intake",
        "claim_kind",
    ):
        assert token in planner_prompt
    assert "Do not silently branch or widen scope." in planner_prompt
    assert "`tool_requirements` pass `gpd validate plan-preflight <PLAN.md>`" in planner_prompt
    assert "Proof-bearing plans keep proof artifacts and sibling `*-PROOF-REDTEAM.md` audits explicit" in planner_prompt
    assert "The contract still exposes defaultable semantic fields" not in planner_prompt
    assert "Stale proof review gate" not in planner_prompt


def test_planner_and_checker_examples_surface_concrete_contract_anchors() -> None:
    planner_prompt = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")
    checker_prompt = (REPO_ROOT / "src/gpd/agents/gpd-plan-checker.md").read_text(encoding="utf-8")

    assert "in_scope: [\"Recover the benchmark curve within tolerance\"]" in planner_prompt
    assert "claim_kind: theorem" in planner_prompt
    assert 'parameters -> symbol "q"' in planner_prompt
    assert "hypotheses -> hyp-gauge" in planner_prompt
    assert "conclusion_clauses -> concl-transverse" in planner_prompt
    assert "GPD/phases/01-vacuum-polarization/01-01-SUMMARY.md" in planner_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-and-tensor-convention" in planner_prompt
    assert "schema_version: 1" in checker_prompt
    assert "in_scope: [\"Recover the benchmark value within tolerance\"]" in checker_prompt
    assert "claim_kind: theorem" in checker_prompt
    assert "parameters:" in checker_prompt
    assert "- symbol: k" in checker_prompt
    assert "domain_or_type: \"dimensionless\"" in checker_prompt
    assert "aliases: [kappa]" in checker_prompt
    assert "required_in_proof: true" in checker_prompt
    assert "hypotheses:" in checker_prompt
    assert "- id: hyp-normalization" in checker_prompt
    assert "text: \"Reference normalization and tolerance convention match Ref-01\"" in checker_prompt
    assert "symbols: [k]" in checker_prompt
    assert "category: assumption" in checker_prompt
    assert "conclusion_clauses:" in checker_prompt
    assert "- id: concl-benchmark" in checker_prompt
    assert "text: \"Benchmark agreement stays within tolerance at every approved sample\"" in checker_prompt
    assert "proof_deliverables: [deliv-proof-main]" in checker_prompt
    assert "parameters: [k]" not in checker_prompt
    assert "hypotheses: [\"Reference normalization and tolerance convention match Ref-01\"]" not in checker_prompt
    assert (
        "conclusion_clauses: [\"Benchmark agreement stays within tolerance at every approved sample\"]" not in checker_prompt
    )
    assert (
        "Treat stable knowledge docs surfaced through the shared reference context as reviewed background syntheses only."
        in checker_prompt
    )
    assert (
        "They may refine assumptions or method choice when they agree with stronger sources, but they do not override "
        "`convention_lock`, `project_contract`, the PLAN `contract`, `contract_results`, `comparison_verdicts`, "
        "proof-review artifacts, or direct benchmark/result evidence."
        in checker_prompt
    )
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md" in checker_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-unit-and-notation-conventions" in checker_prompt


def test_plan_checker_prompt_surfaces_direct_schema_visibility_and_read_only_authority() -> None:
    checker_prompt = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")

    assert checker_prompt.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") >= 2
    assert "{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" in checker_prompt
    assert "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" not in checker_prompt
    assert "This is a one-shot handoff. If user input is needed, return `status: checkpoint`; do not wait inside the same run." in checker_prompt
    assert "artifact_write_authority: read_only" in checker_prompt
    assert "file_write" not in checker_prompt
    assert "approved_plans: [list of plan IDs that passed]" in checker_prompt
    assert "blocked_plans: [list of plan IDs needing revision or escalation]" in checker_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md" in checker_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-unit-and-notation-conventions" in checker_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-and-tensor-convention" in checker_prompt
    assert "GPD/phases/01-vacuum-polarization/01-01-SUMMARY.md" in checker_prompt


def test_phase_prompt_surfaces_default_salvage_and_hard_plan_requirements() -> None:
    phase_prompt = _read_template("phase-prompt.md")

    assert phase_prompt.count("Quick contract rules:") == 1
    assert phase_prompt.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    for token in (
        "tool_requirements",
        "researcher_setup",
        "type: execute",
        "gap_closure: true",
        "scope.in_scope",
        "claim_kind",
        "observables[].kind",
        "deliverables[].kind",
        "acceptance_tests[].kind",
        "references[].kind",
        "references[].role",
        "links[].relation",
        "must_surface",
        "required_actions[]",
        "applies_to[]",
        "carry_forward_to[]",
        "uncertainty_markers",
    ):
        assert token in phase_prompt


def test_contract_schema_docs_make_lowercase_closed_vocab_rule_model_visible() -> None:
    plan_schema = _expanded_template("plan-contract-schema.md")
    project_schema = _expanded_template("project-contract-schema.md")
    state_schema = _expanded_template("state-json-schema.md")

    expected = "Case drift such as `Theorem`, `Benchmark`, or `Read` fails strict validation."

    assert expected in plan_schema
    assert expected in project_schema
    assert expected in state_schema


def test_planner_prompt_stays_compact_while_preserving_canonical_contract_wiring() -> None:
    planner_prompt = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")
    planner_role = planner_prompt.partition("</role>")[0]

    assert 'parameters -> symbol "q"' in planner_prompt
    assert "hypotheses -> hyp-gauge" in planner_prompt
    assert "conclusion_clauses -> concl-transverse" in planner_prompt
    assert 'parameters: ["q"]' not in planner_prompt
    assert 'hypotheses: ["Gauge-fixing and regularization conventions match the approved anchor"]' not in planner_prompt
    assert 'conclusion_clauses: ["q_mu Pi^{mu nu} = 0"]' not in planner_prompt
    assert "15-20%" not in planner_prompt
    assert "Context %" not in planner_prompt
    assert "No plan-checker" not in planner_prompt
    assert "The system starts broad and narrows automatically." not in planner_prompt
    assert "approach_validated: true" not in planner_prompt
    assert planner_prompt.count("| **YOLO** |") == 1
    assert "<worked_examples>" not in planner_prompt
    assert "<goal_backward>" not in planner_prompt
    assert "Worked Examples: Complete PLAN.md Files" not in planner_prompt
    assert "Goal-Backward Methodology for Physics" not in planner_prompt
    assert "tool_requirements[].id" in planner_prompt
    assert "must be unique within the list" in planner_prompt
    assert "in_scope: [\"Recover the benchmark curve within tolerance\"]" in planner_prompt
    assert "claim_kind: theorem" in planner_prompt
    assert 'proof_deliverables: ["deliv-proof-vac-pol"]' in planner_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-and-tensor-convention" in planner_prompt
    assert "GPD/phases/01-vacuum-polarization/01-01-SUMMARY.md" in planner_prompt
    assert "@{GPD_INSTALL_DIR}/workflows/execute-plan.md" not in planner_role
    assert "@{GPD_INSTALL_DIR}/templates/summary.md" not in planner_role
    assert "@{GPD_INSTALL_DIR}/references/protocols/order-of-limits.md" not in planner_role


def test_proof_obligation_planning_surfaces_require_claim_audit_and_stale_review_gate() -> None:
    plan_schema = _read_template("plan-contract-schema.md")
    planner_prompt = _read_template("planner-subagent-prompt.md")
    phase_prompt = _read_template("phase-prompt.md")

    assert "kind: scalar|curve|map|classification|proof_obligation|other" in plan_schema
    assert (
        "When `kind: proof_obligation`, make `definition` name the theorem/result plus the hypotheses or "
        "parameter regime the proof must cover."
    ) in plan_schema

    assert (
        "For proof-bearing work, use an explicit non-`other` `claim_kind` with auditable hypotheses, quantified "
        "variables, and named parameters."
    ) in planner_prompt
    assert "**Proof claim audit:**" not in planner_prompt
    assert "**Stale proof review gate:**" not in planner_prompt

    assert (
        "For proof-bearing work, use an explicit non-`other` `claim_kind`, keep hypotheses, parameters, and "
        "conclusions auditable, and name `observables[].kind: proof_obligation` items with the theorem or claim "
        "plus the hypotheses or parameter regime they cover."
    ) in phase_prompt
    assert "If a proof or theorem statement changes after a proof audit, treat that audit as stale before `status: passed` is possible for the affected target." in phase_prompt


def test_planner_gap_closure_example_keeps_execute_type_and_required_contract_block() -> None:
    planner_prompt = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")

    assert "Gap-closure plans keep `type: execute`; the repair marker is `gap_closure: true`" in planner_prompt
    assert "| `gap_closure`      | No       | `true` only for verification repair plans |" in planner_prompt
    assert "gap_closure: true # Flag for tracking" in planner_prompt
    assert "schema_version: 1" in planner_prompt
    assert "contract:" in planner_prompt
    assert "question: \"[Which failed verification or gap does this plan repair?]\"" in planner_prompt
    assert "in_scope: [\"Repair the failed verification for the published benchmark comparison\"]" in planner_prompt
    assert "must_include_prior_outputs: [\"GPD/phases/XX-name/XX-NN-SUMMARY.md\"]" in planner_prompt
