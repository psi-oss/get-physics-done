"""Focused regression tests for approved-mode anchor-gap phrasing."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.contract_validation import validate_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
WORKFLOW_SPEC = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "workflows" / "new-project.md"
STATE_SCHEMA_SPEC = (
    Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates" / "state-json-schema.md"
)


def _load_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _remove_incidental_grounding(contract: dict[str, object]) -> None:
    contract["references"] = []
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    contract["scope"]["unresolved_questions"] = []
    for claim in contract.get("claims", []):
        claim["references"] = []
    for test in contract.get("acceptance_tests", []):
        test["evidence_required"] = [item for item in test.get("evidence_required", []) if item != "ref-benchmark"]


def test_approved_mode_rejects_need_grounding_phrase_without_other_anchor_tokens() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Need grounding before planning"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_approved_mode_does_not_treat_reference_frame_questions_as_anchor_unknown() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["What reference frame should we use for the analysis?"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_approved_mode_does_not_treat_generic_benchmark_parameter_questions_as_anchor_unknown() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["scope"]["unresolved_questions"] = ["What benchmark tolerance should we use?"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_approved_mode_rejects_target_not_yet_chosen_phrase_in_weakest_anchors() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["uncertainty_markers"]["weakest_anchors"] = ["Target not yet chosen"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_approved_mode_rejects_comparison_source_still_undecided_phrase() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Comparison source still undecided before planning"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_approved_mode_does_not_treat_placeholder_user_asserted_anchor_as_grounding() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["context_intake"]["user_asserted_anchors"] = ["Benchmark TBD"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_approved_mode_still_rejects_generic_open_gap_without_anchor_unknown_phrase() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Need more detail before planning"]
    contract["uncertainty_markers"]["weakest_anchors"] = ["Open question"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_specs_surface_anchor_gap_phrases_for_runtime_visibility() -> None:
    workflow_text = WORKFLOW_SPEC.read_text(encoding="utf-8")
    state_schema_text = STATE_SCHEMA_SPEC.read_text(encoding="utf-8")

    assert "need grounding" in workflow_text
    assert "target not yet chosen" in workflow_text
    assert "Need grounding before the decisive anchor is chosen." in state_schema_text
    assert "Decisive target not yet chosen before planning can proceed." in state_schema_text
