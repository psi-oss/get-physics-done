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
        text = _read(schema_path)
        assert "@{GPD_INSTALL_DIR}/templates/project-contract-grounding-linkage.md" in text
        for line in expected_lines:
            assert line in text, f"{schema_path.name} is missing: {line}"


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
