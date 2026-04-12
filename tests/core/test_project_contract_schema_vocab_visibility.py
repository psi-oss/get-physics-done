"""Parity checks for model-visible project-contract vocabularies."""

from __future__ import annotations

from pathlib import Path

from gpd.contracts import (
    CONTRACT_ACCEPTANCE_AUTOMATION_VALUES,
    CONTRACT_ACCEPTANCE_TEST_KIND_VALUES,
    CONTRACT_CLAIM_KIND_VALUES,
    CONTRACT_DELIVERABLE_KIND_VALUES,
    CONTRACT_LINK_RELATION_VALUES,
    CONTRACT_OBSERVABLE_KIND_VALUES,
    CONTRACT_REFERENCE_ACTION_VALUES,
    CONTRACT_REFERENCE_KIND_VALUES,
    CONTRACT_REFERENCE_ROLE_VALUES,
    ResearchContract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONTRACT_SCHEMA = REPO_ROOT / "src/gpd/specs/templates/project-contract-schema.md"
STATE_JSON_SCHEMA = REPO_ROOT / "src/gpd/specs/templates/state-json-schema.md"
GROUNDING_LINKAGE = REPO_ROOT / "src/gpd/specs/templates/project-contract-grounding-linkage.md"
EXECUTE_PLAN_WORKFLOW = REPO_ROOT / "src/gpd/specs/workflows/execute-plan.md"
EXECUTE_PHASE_WORKFLOW = REPO_ROOT / "src/gpd/specs/workflows/execute-phase.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _vocab_line(field: str, values: tuple[str, ...]) -> str:
    return f"- `{field}: {' | '.join(values)}`"


def test_project_contract_schema_docs_surface_the_closed_contract_vocabularies() -> None:
    expected_lines = (
        _vocab_line("claims[].claim_kind", CONTRACT_CLAIM_KIND_VALUES),
        _vocab_line("observables[].kind", CONTRACT_OBSERVABLE_KIND_VALUES),
        _vocab_line("deliverables[].kind", CONTRACT_DELIVERABLE_KIND_VALUES),
        _vocab_line("acceptance_tests[].kind", CONTRACT_ACCEPTANCE_TEST_KIND_VALUES),
        _vocab_line("acceptance_tests[].automation", CONTRACT_ACCEPTANCE_AUTOMATION_VALUES),
        _vocab_line("references[].kind", CONTRACT_REFERENCE_KIND_VALUES),
        _vocab_line("references[].role", CONTRACT_REFERENCE_ROLE_VALUES),
        _vocab_line("required_actions[]", CONTRACT_REFERENCE_ACTION_VALUES),
        _vocab_line("links[].relation", CONTRACT_LINK_RELATION_VALUES),
    )

    for schema_path in (PROJECT_CONTRACT_SCHEMA, STATE_JSON_SCHEMA):
        assert "@{GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md" in _read(schema_path)

    contract_schema_text = _read(PROJECT_CONTRACT_SCHEMA)
    for line in expected_lines:
        assert line in contract_schema_text, f"{PROJECT_CONTRACT_SCHEMA.name} is missing: {line}"


def test_state_schema_docs_name_pydantic_authority_and_state_md_import_surface() -> None:
    text = _read(STATE_JSON_SCHEMA)

    assert "canonical machine-readable state authority is the `ResearchState` Pydantic model" in text
    assert "Source of truth: `ResearchState` and related Pydantic models in `gpd.core.state`" in text
    assert "STATE.md is a rendered, human-editable import surface only" in text
    assert "not the canonical state authority" in text
    assert "This file is the authoritative machine-readable state" not in text


def test_project_contract_schema_example_surfaces_research_contract_required_keys_and_proof_rules() -> None:
    text = _read(PROJECT_CONTRACT_SCHEMA)

    for top_level_key in ResearchContract.model_fields:
        assert f'"{top_level_key}"' in text

    for required_nested_key in (
        '"context_intake"',
        '"must_read_refs"',
        '"must_include_prior_outputs"',
        '"user_asserted_anchors"',
        '"known_good_baselines"',
        '"context_gaps"',
        '"crucial_inputs"',
        '"parameters"',
        '"domain_or_type"',
        '"aliases"',
        '"required_in_proof"',
        '"hypotheses"',
        '"symbols"',
        '"category"',
        '"quantifiers"',
        '"conclusion_clauses"',
        '"proof_deliverables"',
        "claim_to_proof_alignment",
    ):
        assert required_nested_key in text

    for proof_rule in (
        "proof-bearing claims must keep `parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, and `proof_deliverables` visible",
        "Do not collapse proof obligations into a generic claim statement",
        "include an acceptance test with `kind: claim_to_proof_alignment`",
    ):
        assert proof_rule in text


def test_new_project_surfaces_compact_hard_schema_capsule_before_drafting() -> None:
    schema_text = _read(PROJECT_CONTRACT_SCHEMA)
    workflow_text = _read(REPO_ROOT / "src/gpd/specs/workflows/new-project.md")
    command_text = _read(REPO_ROOT / "src/gpd/commands/new-project.md")

    assert "Hard-schema capsule:" in schema_text
    for required_fragment in (
        "`schema_version`, `scope`, `context_intake`, and `uncertainty_markers`",
        "bool fields use literal `true`/`false` only",
        "list fields stay lists",
        "object arrays stay objects",
        "proof-bearing claims must surface `parameters`, `hypotheses`, `quantifiers`, `conclusion_clauses`, `proof_deliverables`",
        "`claim_to_proof_alignment` acceptance test",
    ):
        assert required_fragment in schema_text

    for visible_text in (workflow_text, command_text):
        assert "drafting or repairing" in visible_text
        assert "compact hard-schema capsule" in visible_text

    workflow_prefix = workflow_text[: workflow_text.index("<auto_mode>")]
    assert "<hard_schema_visibility_guard>" in workflow_prefix


def test_project_contract_schema_surfaces_validator_enforced_reference_gates() -> None:
    text = _read(PROJECT_CONTRACT_SCHEMA)

    assert "Project contracts must include at least one observable, claim, or deliverable." in text
    assert (
        "If `references[]` is present before approval and grounding is not already concrete, at least one reference must set `must_surface: true`."
        in text
    )
    assert "Every `must_surface: true` reference needs a concrete `locator` and concrete `applies_to[]` coverage" in text
    assert "Project-local paths in `locator` or `applies_to[]` evidence must resolve when `project_root` is available." in text


def test_project_contract_grounding_linkage_mentions_project_root_guard_and_cross_section_rule() -> None:
    text = _read(GROUNDING_LINKAGE)

    assert "project_root guard" in text
    assert "Cross-section unique ID rule" in text


def test_execute_plan_workflow_surfaces_hard_schema_before_process() -> None:
    text = _read(EXECUTE_PLAN_WORKFLOW)

    assert "<hard_schema_visibility_guard>" in text
    assert "<process>" in text
    assert text.index("<hard_schema_visibility_guard>") < text.index("<process>")
    assert "contract-results-schema.md" in text


def test_execute_phase_workflow_surfaces_hard_schema_before_process() -> None:
    text = _read(EXECUTE_PHASE_WORKFLOW)

    assert "<hard_schema_visibility_guard>" in text
    assert "<process>" in text
    assert text.index("<hard_schema_visibility_guard>") < text.index("<process>")
    assert "contract-results-schema.md" in text
    assert "delegating to a subagent" in text
