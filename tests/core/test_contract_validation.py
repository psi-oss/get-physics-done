"""Tests for executable project-contract validation."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.contract_validation import validate_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def test_validate_project_contract_accepts_stage0_fixture() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))

    result = validate_project_contract(contract)

    assert result.valid is True
    assert result.decisive_target_count > 0
    assert result.guidance_signal_count > 0
    assert result.reference_count > 0


def test_validate_project_contract_rejects_missing_decisive_targets_and_skepticism() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["observables"] = []
    contract["claims"] = []
    contract["deliverables"] = []
    contract["uncertainty_markers"]["weakest_anchors"] = []
    contract["uncertainty_markers"]["disconfirming_observations"] = []

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "project contract must include at least one observable, claim, or deliverable" in result.errors
    assert "uncertainty_markers.weakest_anchors must identify what is least certain" in result.errors
    assert (
        "uncertainty_markers.disconfirming_observations must identify what would force a rethink"
        in result.errors
    )


def test_validate_project_contract_warns_when_user_guidance_signals_are_missing() -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    result = validate_project_contract(contract)

    assert result.valid is True
    assert result.guidance_signal_count == 0
    assert any("no user guidance signals recorded yet" in warning for warning in result.warnings)


def test_validate_project_contract_propagates_schema_errors() -> None:
    result = validate_project_contract({"scope": {"question": "x"}})

    assert result.valid is False
    assert "scope.in_scope must name at least one project boundary or objective" in result.errors
    assert "project contract must include at least one observable, claim, or deliverable" in result.errors
