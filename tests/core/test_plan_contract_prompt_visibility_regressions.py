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
    assert "The defaultable semantic fields above do not relax the hard requirements on `context_intake` or `uncertainty_markers`" in plan_schema
    assert "For non-scoping plans, `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` are all required." in plan_schema


def test_planner_prompt_surfaces_default_salvage_and_specific_semantics() -> None:
    planner_prompt = _read_template("planner-subagent-prompt.md")

    assert "The contract still exposes defaultable semantic fields" in planner_prompt
    assert "observables[].kind" in planner_prompt
    assert "deliverables[].kind" in planner_prompt
    assert "acceptance_tests[].kind" in planner_prompt
    assert "references[].kind" in planner_prompt
    assert "references[].role" in planner_prompt
    assert "links[].relation" in planner_prompt
    assert "They default to `other` and may be omitted only when that generic category is actually intended." in planner_prompt
    assert "**Defaulted semantic fields:** `observables[].kind`, `deliverables[].kind`, `acceptance_tests[].kind`, `references[].kind`, `references[].role`, and `links[].relation` all exist in the contract and default to `other`" in planner_prompt


def test_phase_prompt_surfaces_default_salvage_and_hard_plan_requirements() -> None:
    phase_prompt = _read_template("phase-prompt.md")

    assert "The defaultable semantic fields still exist in the contract surface" in phase_prompt
    assert "observables[].kind" in phase_prompt
    assert "deliverables[].kind" in phase_prompt
    assert "acceptance_tests[].kind" in phase_prompt
    assert "references[].kind" in phase_prompt
    assert "references[].role" in phase_prompt
    assert "links[].relation" in phase_prompt
    assert "They default to `other`, but the more specific value remains mandatory when the plan already knows it." in phase_prompt
    assert "The validator is strict here: for ordinary execution plans, the contract must carry non-empty claims, deliverables, acceptance tests, forbidden proxies, and a non-empty `context_intake`" in phase_prompt
    assert "If references are present, at least one must set `must_surface: true`." in phase_prompt
