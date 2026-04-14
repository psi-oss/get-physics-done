"""Focused smoke coverage for project-contract validation invariants."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.contracts import ResearchContract, collect_plan_contract_integrity_errors
from gpd.core.contract_validation import validate_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _remove_incidental_grounding(contract: dict[str, object]) -> None:
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    for claim in contract.get("claims", []):
        claim["references"] = []
    for target in contract.get("acceptance_tests", []):
        target["evidence_required"] = [item for item in target.get("evidence_required", []) if item != "ref-benchmark"]


def test_validate_project_contract_smoke_rejects_coercive_schema_version_scalar() -> None:
    contract = _load_contract_fixture()
    contract["schema_version"] = True

    result = validate_project_contract(contract)

    assert result.valid is False
    assert result.errors == ["schema_version must be the integer 1"]
    assert result.warnings == []


def test_validate_project_contract_smoke_rejects_coercive_reference_must_surface_scalar() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = "yes"

    result = validate_project_contract(contract)

    assert result.valid is True
    expected_warning = "references.0.must_surface: must be a boolean (coerced from 'yes')"
    assert result.errors == []
    assert expected_warning in result.warnings

def test_validate_project_contract_smoke_approved_rejects_coercive_reference_must_surface_scalar() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = "yes"

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    expected_error = "references.0.must_surface: must be a boolean (coerced from 'yes')"
    assert result.errors == [expected_error]
    assert result.warnings == []
    assert not any("unknown reference" in issue for issue in result.errors + result.warnings)
    assert not any(
        "must include at least one must_surface=true anchor" in issue for issue in result.errors + result.warnings
    )


def test_validate_project_contract_smoke_rejects_rootless_project_local_must_surface_reference_without_project_root() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "prior_artifact",
            "locator": "GPD/phases/03-missing-energy/03-01-SUMMARY.md",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Local artifact anchors need a project root to prove they are real.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []

    integrity_errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract))
    result = validate_project_contract(contract, mode="approved")

    assert "references must include at least one must_surface=true anchor" in integrity_errors
    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize("field_name", ["context_intake", "uncertainty_markers"])
def test_validate_project_contract_smoke_rejects_missing_required_sections(field_name: str) -> None:
    contract = _load_contract_fixture()
    contract.pop(field_name)

    result = validate_project_contract(contract)

    assert result.valid is False
    assert any(error.startswith(field_name) for error in result.errors)


@pytest.mark.parametrize(
    ("field_name", "value", "expected_error"),
    [
        ("context_intake", "oops", "context_intake must be an object, not str"),
        ("approach_policy", "oops", "approach_policy must be an object, not str"),
        ("uncertainty_markers", "oops", "uncertainty_markers must be an object, not str"),
    ],
)
def test_validate_project_contract_smoke_rejects_object_sections_as_scalars(
    field_name: str,
    value: object,
    expected_error: str,
) -> None:
    contract = _load_contract_fixture()
    contract[field_name] = value

    result = validate_project_contract(contract)

    assert result.valid is False
    assert expected_error in result.errors
