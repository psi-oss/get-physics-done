from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def test_plan_contract_schema_surfaces_defaultable_semantic_fields_and_hard_constraints() -> None:
    plan_schema = _read_template("plan-contract-schema.md")

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

    assert "Use `@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md` as the canonical contract source." in planner_prompt
    assert "Keep this prompt for scope selection, mode flags, and return conventions only." in planner_prompt
    assert "**Project Contract Gate:** {project_contract_gate}" in planner_prompt
    assert "**Project Contract Load Info:** {project_contract_load_info}" in planner_prompt
    assert "**Project Contract Validation:** {project_contract_validation}" in planner_prompt
    assert "Planning requires an approved `project_contract`." in planner_prompt
    assert "If `project_contract_gate.authoritative` is false, keep the contract visible as diagnostics, not approved planning scope." in planner_prompt
    assert (
        "If `project_contract_load_info.status` starts with `blocked` or `project_contract_validation.valid` is false, "
        "return `## CHECKPOINT REACHED` instead of guessing."
    ) in planner_prompt
    assert "Keep `project_contract` as the structured grounding ledger." in planner_prompt
    assert (
        "Use `effective_reference_intake` and `active_reference_context` only as readable projections "
        "of the same anchors, not as substitutes."
    ) in planner_prompt
    assert "Treat `approach_policy` as execution policy only." in planner_prompt
    assert "It does not substitute for grounding." in planner_prompt
    assert (
        "For proof-bearing work, use an explicit non-`other` `claim_kind` and keep hypotheses, quantified variables, and named parameters explicit enough to audit."
    ) in planner_prompt
    assert "The contract still exposes defaultable semantic fields" not in planner_prompt
    assert "Stale proof review gate" not in planner_prompt


def test_planner_and_checker_examples_surface_concrete_contract_anchors() -> None:
    planner_prompt = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")
    checker_prompt = (REPO_ROOT / "src/gpd/agents/gpd-plan-checker.md").read_text(encoding="utf-8")

    assert "in_scope: [\"Recover the benchmark curve within tolerance\"]" in planner_prompt
    assert "claim_kind: theorem" in planner_prompt
    assert 'proof_deliverables: ["deliv-proof-vac-pol"]' in planner_prompt
    assert "GPD/phases/01-vacuum-polarization/01-01-SUMMARY.md" in planner_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-and-tensor-convention" in planner_prompt
    assert "schema_version: 1" in checker_prompt
    assert "in_scope: [\"Recover the benchmark value within tolerance\"]" in checker_prompt
    assert "claim_kind: theorem" in checker_prompt
    assert "proof_deliverables: [deliv-proof-main]" in checker_prompt
    assert "Treat `effective_reference_intake` and `active_reference_context` only as readable projections" in checker_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md" in checker_prompt
    assert "GPD/phases/00-baseline/00-01-SUMMARY.md#gauge-unit-and-notation-conventions" in checker_prompt


def test_phase_prompt_surfaces_default_salvage_and_hard_plan_requirements() -> None:
    phase_prompt = _read_template("phase-prompt.md")

    assert "Quick contract rules:" in phase_prompt
    assert "Put machine-checkable prerequisites in `tool_requirements`; keep human-only setup in `researcher_setup`." in phase_prompt
    assert phase_prompt.count("Quick contract rules:") == 1
    assert "Gap-closure plans still use `type: execute`; mark verification-repair plans with `gap_closure: true`" in phase_prompt
    assert "mark verification-repair plans with `gap_closure: true`" in phase_prompt
    assert "type: execute | tdd" in phase_prompt
    assert "# gap_closure: true # Optional. Use only for verification repair plans." in phase_prompt
    assert "The validator accepts a closed tool vocabulary today: `wolfram` and `command`" in phase_prompt
    assert "For `tool: command`, a non-empty `command` field is mandatory" in phase_prompt
    assert "`required` defaults to `true` when omitted" in phase_prompt
    assert "The defaultable semantic fields still exist in the contract surface" in phase_prompt
    assert "`scope.in_scope` must be populated in the executor-facing contract examples, and project-scoping plans must keep it non-empty." in phase_prompt
    assert "Proof-bearing claims must use an explicit non-`other` `claim_kind`, and the body must keep hypotheses, parameters, and conclusions auditable." in phase_prompt
    assert "observables[].kind" in phase_prompt
    assert "deliverables[].kind" in phase_prompt
    assert "acceptance_tests[].kind" in phase_prompt
    assert "references[].kind" in phase_prompt
    assert "references[].role" in phase_prompt
    assert "links[].relation" in phase_prompt
    assert "They default to `other`, but the more specific value remains mandatory when the plan already knows it." in phase_prompt
    assert "For non-scoping plans, keep the contract concretely grounded rather than placeholder-only." in phase_prompt
    assert "Treat `approach_policy` as execution policy only; it does not satisfy grounding on its own." in phase_prompt
    assert "If grounding already exists elsewhere, a missing `must_surface: true` reference is a warning, not a blocker." in phase_prompt
    assert "`must_surface` uses YAML booleans." in phase_prompt
    assert "When `must_surface` is `true`, keep `required_actions[]` and `applies_to[]` non-empty." in phase_prompt
    assert "`carry_forward_to[]` is free-text workflow scope only and must not be overloaded with contract IDs." in phase_prompt
    assert "`uncertainty_markers` must stay a YAML object, not a string or list." in phase_prompt
    assert phase_prompt.count("Quick contract rules:") == 1


def test_planner_prompt_stays_compact_while_preserving_canonical_contract_wiring() -> None:
    planner_prompt = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")

    assert planner_prompt.count("contract:\n  schema_version: 1") >= 2
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


def test_proof_obligation_planning_surfaces_require_claim_audit_and_stale_review_gate() -> None:
    plan_schema = _read_template("plan-contract-schema.md")
    planner_prompt = _read_template("planner-subagent-prompt.md")
    phase_prompt = _read_template("phase-prompt.md")

    assert "kind: scalar|curve|map|classification|proof_obligation|other" in plan_schema
    assert (
        "When `kind: proof_obligation`, make `definition` name the theorem/result plus the hypotheses or "
        "parameter regime the proof must cover."
    ) in plan_schema

    assert "For proof-bearing work, use an explicit non-`other` `claim_kind` and keep hypotheses, quantified variables, and named parameters explicit enough to audit." in planner_prompt
    assert "**Proof claim audit:**" not in planner_prompt
    assert "**Stale proof review gate:**" not in planner_prompt

    assert "For `observables[].kind: proof_obligation`, name the theorem or claim plus the hypotheses/parameter regime explicitly" in phase_prompt
    assert "silently specialized parameters" in phase_prompt
    assert "If a proof or theorem statement changes after a proof audit, treat that audit as stale" in phase_prompt
    assert "before `status: passed` is possible for the affected target." in phase_prompt


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
