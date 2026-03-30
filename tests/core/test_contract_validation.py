"""Tests for executable project-contract validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.contracts import (
    ContractResults,
    ProjectContractParseResult,
    ResearchContract,
    contract_from_data,
    normalize_contract_results_input,
    parse_project_contract_data_strict,
)
from gpd.core.contract_validation import validate_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates"


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


def test_validate_project_contract_accepts_stage0_fixture() -> None:
    contract = _load_contract_fixture()

    result = validate_project_contract(contract)

    assert result.valid is True
    assert result.decisive_target_count > 0
    assert result.guidance_signal_count > 0
    assert result.reference_count > 0


def test_research_contract_rejects_blank_observable_regime_and_units() -> None:
    contract = _load_contract_fixture()
    contract["observables"][0]["regime"] = " "
    contract["observables"][0]["units"] = ""

    with pytest.raises(ValidationError) as exc_info:
        ResearchContract.model_validate(contract)

    message = str(exc_info.value)
    assert "observables.0.regime" in message
    assert "must be a non-empty string" in message
    assert "observables.0.units" in message


def test_validate_project_contract_rejects_blank_observable_regime_and_units() -> None:
    contract = _load_contract_fixture()
    contract["observables"][0]["regime"] = " "
    contract["observables"][0]["units"] = " "

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "observables.0.regime must be a non-empty string" in result.errors
    assert "observables.0.units must be a non-empty string" in result.errors


def test_contract_from_data_rejects_blank_observable_regime_and_units() -> None:
    contract = _load_contract_fixture()
    contract["observables"][0]["regime"] = " "
    contract["observables"][0]["units"] = " "

    assert contract_from_data(contract) is None


def test_contract_from_data_rejects_blank_scalar_to_list_drift() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["references"] = "   "

    assert contract_from_data(contract) is None


def test_parse_project_contract_data_strict_rejects_singleton_list_drift() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert result.errors == ["context_intake.must_read_refs must be a list, not str"]


def test_parse_project_contract_data_strict_rejects_recoverable_nested_extra_keys() -> None:
    contract = _load_contract_fixture()
    contract["scope"]["legacy_notes"] = "nested extra field"

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert result.errors == ["scope.legacy_notes: Extra inputs are not permitted"]


def test_validate_project_contract_rejects_missing_decisive_targets_and_skepticism() -> None:
    contract = _load_contract_fixture()
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
    contract = _load_contract_fixture()
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is True
    assert result.guidance_signal_count == 0
    assert any("no user guidance signals recorded yet" in warning for warning in result.warnings)


def test_validate_project_contract_approved_mode_requires_concrete_anchor_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["scope"]["unresolved_questions"] = ["Need to decide which ground-truth anchor matters most"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_explicit_anchor_unknown_blocker_without_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["anchor unknown; must establish later before planning"]
    contract["scope"]["unresolved_questions"] = ["Anchor unknown; must establish later"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_ground_truth_unclear_aliases_without_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Ground truth still unclear; no smoking gun yet for this setup"]
    contract["scope"]["unresolved_questions"] = ["Anchor is unclear and must establish later before planning"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_question_form_anchor_gap_without_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Which reference should serve as the decisive benchmark anchor?"]
    contract["scope"]["unresolved_questions"] = ["Which benchmark or baseline should we treat as decisive?"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_not_yet_selected_anchor_gap_without_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Benchmark reference not yet selected; still to identify the decisive anchor"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_anchor_unknown_in_weakest_anchors_without_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["uncertainty_markers"]["weakest_anchors"] = [
        "Benchmark reference not yet selected; still to identify the decisive anchor"
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_accepts_prior_output_grounding(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    prior_output = tmp_path / "GPD" / "phases" / "00-baseline" / "00-01-SUMMARY.md"
    prior_output.parent.mkdir(parents=True)
    prior_output.write_text("# Summary\n", encoding="utf-8")
    contract["context_intake"]["must_include_prior_outputs"] = ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is True
    assert result.mode == "approved"


@pytest.mark.parametrize(
    ("reference_kind", "locator"),
    [
        ("paper", "doi:10.1234/example"),
        ("paper", "arXiv:2401.12345"),
        ("paper", "Table 2"),
        ("paper", "Fig. 3"),
        ("dataset", "https://huggingface.co/datasets/org/sample"),
        ("spec", "https://docs.example.org/specs/solver-v2"),
        ("prior_artifact", "https://github.com/org/repo/blob/main/artifacts/report.json"),
    ],
)
def test_validate_project_contract_approved_mode_accepts_concrete_reference_locator_grounding(
    reference_kind: str,
    locator: str,
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": reference_kind,
            "locator": locator,
            "aliases": [],
            "role": "background",
            "why_it_matters": "Concrete locator should ground approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_accepts_project_local_prior_artifact_locator(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    artifact = tmp_path / "artifacts" / "benchmark" / "report.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "prior_artifact",
            "locator": "artifacts/benchmark/report.json",
            "aliases": [],
            "role": "background",
            "why_it_matters": "Concrete prior artifact should ground approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_rejects_placeholder_must_surface_reference_masked_by_background_reference() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-placeholder-anchor",
            "kind": "paper",
            "locator": "TBD",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Placeholder anchor should not ground approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        },
        {
            "id": "ref-background",
            "kind": "paper",
            "locator": "doi:10.1234/example",
            "aliases": [],
            "role": "background",
            "why_it_matters": "Concrete background material should not mask the placeholder anchor.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": False,
            "required_actions": ["read"],
        },
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_accepts_concrete_must_surface_reference_anchor() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "paper",
            "locator": "doi:10.1234/example",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Concrete must_surface anchor should ground approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


@pytest.mark.parametrize("locator", ["Benchmark paper", "reference article", "/tmp/nonexistent.txt", "report.pdf"])
def test_validate_project_contract_approved_mode_rejects_vague_reference_locator_grounding(
    locator: str,
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "paper",
            "locator": locator,
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Vague locators must not satisfy approved grounding.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("user_asserted_anchors", ["Recover known limiting behavior"]),
        ("known_good_baselines", ["Baseline notebook A"]),
    ],
)
def test_validate_project_contract_approved_mode_accepts_substantive_text_grounding(
    field_name: str, value: list[str]
) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []
    contract["context_intake"][field_name] = value
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


@pytest.mark.parametrize("locator", ["TBD", "unknown"])
def test_validate_project_contract_approved_mode_rejects_placeholder_reference_locator_even_for_benchmark_reference(
    locator: str,
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "paper",
            "locator": locator,
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Placeholder locators must not ground approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_accepts_non_reference_grounding_when_must_surface_is_missing(
    tmp_path: Path,
) -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = False
    prior_output = tmp_path / "GPD" / "phases" / "00-baseline" / "00-01-SUMMARY.md"
    prior_output.parent.mkdir(parents=True)
    prior_output.write_text("# Summary\n", encoding="utf-8")
    contract["context_intake"]["must_include_prior_outputs"] = ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is True
    assert result.mode == "approved"
    assert "references must include at least one must_surface=true anchor" in result.warnings


def test_validate_project_contract_approved_mode_rejects_nonexistent_prior_output_grounding(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = ["fake/path"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize("field_name", ["must_include_prior_outputs", "known_good_baselines"])
def test_validate_project_contract_approved_mode_rejects_placeholder_non_reference_grounding(field_name: str) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"][field_name] = ["TBD"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize(
    "field_name",
    ["must_include_prior_outputs", "user_asserted_anchors", "known_good_baselines"],
)
def test_validate_project_contract_approved_mode_rejects_bare_junk_grounding(field_name: str) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []
    contract["context_intake"][field_name] = ["foo"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_placeholder_user_asserted_anchor() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["user_asserted_anchors"] = ["Need grounding before planning"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_placeholder_user_asserted_anchor_even_with_explicit_blocker() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["user_asserted_anchors"] = ["Benchmark TBD"]
    contract["context_intake"]["context_gaps"] = ["Anchor unknown; must establish later before planning"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_placeholder_only_sentence_guidance() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["known_good_baselines"] = ["Need more detail before planning"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_carry_forward_contract_id_as_grounding() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-background",
            "kind": "paper",
            "locator": "Background review article",
            "aliases": [],
            "role": "background",
            "why_it_matters": "Context only; not a grounding anchor.",
            "applies_to": [],
            "carry_forward_to": ["claim-benchmark"],
            "must_surface": False,
            "required_actions": [],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert (
        "reference ref-background carry_forward_to must name workflow scope, not contract id claim-benchmark"
        in result.errors
    )
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_rejects_unknown_must_read_ref() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ["ref-missing"]

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "context_intake.must_read_refs references unknown reference ref-missing" in result.errors


def test_validate_project_contract_rejects_cross_link_inconsistency() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["deliverables"] = ["missing-deliverable"]

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "claim claim-benchmark references unknown deliverable missing-deliverable" in result.errors


def test_validate_project_contract_rejects_duplicate_ids() -> None:
    contract = _load_contract_fixture()
    contract["claims"].append(dict(contract["claims"][0]))

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "duplicate claim id claim-benchmark" in result.errors
    assert result.errors.count("duplicate claim id claim-benchmark") == 1


def test_validate_project_contract_reports_duplicate_acceptance_test_ids_once_with_human_readable_label() -> None:
    contract = _load_contract_fixture()
    contract["acceptance_tests"].append(dict(contract["acceptance_tests"][0]))

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "duplicate acceptance test id test-benchmark" in result.errors
    assert result.errors.count("duplicate acceptance test id test-benchmark") == 1
    assert not any("duplicate acceptance_test id test-benchmark" in error for error in result.errors)


def test_validate_project_contract_rejects_cross_type_id_collisions() -> None:
    contract = _load_contract_fixture()
    contract["deliverables"][0]["id"] = "claim-benchmark"

    result = validate_project_contract(contract)

    assert result.valid is False
    assert (
        "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous"
        in result.errors
    )


def test_validate_project_contract_rejects_unknown_observables_and_evidence() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["observables"] = ["obs-missing"]
    contract["acceptance_tests"][0]["evidence_required"] = ["evidence-missing"]

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "claim claim-benchmark references unknown observable obs-missing" in result.errors
    assert "acceptance test test-benchmark references unknown evidence evidence-missing" in result.errors


def test_validate_project_contract_rejects_must_surface_reference_without_required_actions() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = True
    contract["references"][0]["required_actions"] = []

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "reference ref-benchmark is must_surface but missing required_actions" in result.errors


def test_validate_project_contract_normalizes_reference_required_actions_whitespace_and_duplicates() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["required_actions"] = [" Read ", "compare", "read", "  ", " Cite "]

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract)

    assert parsed.references[0].required_actions == ["read", "compare", "cite"]
    assert result.valid is True


def test_validate_project_contract_accepts_singleton_list_string_drift_at_validation_boundary() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_include_prior_outputs"] = "GPD/phases/00-baseline/00-01-SUMMARY.md"
    contract["references"][0]["role"] = "Benchmark"
    contract["references"][0]["required_actions"] = ["Read", "Compare", "Cite"]

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract, mode="approved")

    assert parsed.context_intake.must_include_prior_outputs == ["GPD/phases/00-baseline/00-01-SUMMARY.md"]
    assert parsed.references[0].role == "benchmark"
    assert parsed.references[0].required_actions == ["read", "compare", "cite"]
    assert result.valid is True
    assert result.errors == []


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda contract: contract["claims"][0].__setitem__("references", "   "),
            "claims.0.references must not be blank",
        ),
        (
            lambda contract: contract["scope"].__setitem__("in_scope", "   "),
            "scope.in_scope must not be blank",
        ),
    ],
)
def test_validate_project_contract_rejects_blank_scalar_to_list_drift(
    mutator,
    expected_error: str,
) -> None:
    contract = _load_contract_fixture()
    mutator(contract)

    result = validate_project_contract(contract)

    assert result.valid is False
    assert expected_error in result.errors


def test_validate_project_contract_rejects_coercive_reference_must_surface_scalar() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = "yes"

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "references.0.must_surface must be a boolean" in result.errors


def test_validate_project_contract_rejects_coercive_schema_version_scalar() -> None:
    contract = _load_contract_fixture()
    contract["schema_version"] = True

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "schema_version must be the integer 1" in result.errors


def test_validate_project_contract_rejects_must_surface_reference_without_applies_to() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = True
    contract["references"][0]["applies_to"] = []

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "reference ref-benchmark is must_surface but missing applies_to" in result.errors


def test_validate_project_contract_rejects_references_without_any_must_surface_anchor() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"][0]["must_surface"] = False
    contract["references"][0]["required_actions"] = ["read", "compare"]
    contract["references"][0]["applies_to"] = ["claim-benchmark"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert "references must include at least one must_surface=true anchor" in result.errors


def test_validate_project_contract_draft_warns_when_reference_grounding_lacks_must_surface_anchor() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = False

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is True
    assert "references must include at least one must_surface=true anchor" in result.warnings


def test_validate_project_contract_rejects_invalid_forbidden_proxy_and_link_bindings() -> None:
    contract = _load_contract_fixture()
    contract["forbidden_proxies"][0]["subject"] = "missing-claim"
    contract["links"][0]["source"] = "missing-source"
    contract["links"][0]["target"] = "missing-target"
    contract["links"][0]["verified_by"] = ["missing-test"]

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "forbidden proxy fp-01 targets unknown subject missing-claim" in result.errors
    assert "link link-01 references unknown source missing-source" in result.errors
    assert "link link-01 references unknown target missing-target" in result.errors
    assert "link link-01 references unknown acceptance test missing-test" in result.errors


def test_validate_project_contract_reports_nested_object_schema_errors() -> None:
    contract = _load_contract_fixture()
    contract["observables"] = ["benchmark observable"]
    contract["acceptance_tests"] = ["test-benchmark"]

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "observables.0 must be an object, not str" in result.errors
    assert "acceptance_tests.0 must be an object, not str" in result.errors


def test_validate_project_contract_propagates_schema_errors() -> None:
    result = validate_project_contract({"scope": {"question": "x"}})

    assert result.valid is False
    assert "scope.in_scope must name at least one project boundary or objective" in result.errors
    assert "project contract must include at least one observable, claim, or deliverable" in result.errors


def test_validate_project_contract_accepts_reference_aliases_list_shape_drift_at_validation_boundary() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["aliases"] = "not-a-list"

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract)

    assert result.valid is True
    assert parsed.references[0].aliases == ["not-a-list"]
    assert result.errors == []


def test_validate_project_contract_accepts_nested_claim_reference_list_shape_drift() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["references"] = "ref-benchmark"

    result = validate_project_contract(contract)

    assert result.valid is True
    assert result.errors == []


def test_validate_project_contract_reports_extra_item_keys_without_dropping_semantic_counts() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["notes"] = "harmless"

    result = validate_project_contract(contract)

    assert result.valid is True
    assert "claims.0.notes: Extra inputs are not permitted" in result.warnings
    assert result.question == "What benchmark must the project recover?"
    assert result.decisive_target_count > 0


def test_validate_project_contract_rejects_top_level_extra_keys() -> None:
    contract = _load_contract_fixture()
    contract["legacy_notes"] = "forwarded from a prior schema revision"

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "legacy_notes: Extra inputs are not permitted" in result.errors


def test_validate_project_contract_ignores_nested_metadata_must_surface_without_false_boolean_error() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["metadata"] = {"must_surface": "yes"}

    result = validate_project_contract(contract)

    assert result.valid is True
    assert "references.0.metadata: Extra inputs are not permitted" in result.warnings
    assert not any(
        "references.0.metadata.must_surface must be a boolean" in issue for issue in result.errors + result.warnings
    )


def test_validate_project_contract_approved_mode_rejects_background_only_reference() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-background",
            "kind": "paper",
            "locator": "Background review article",
            "role": "background",
            "why_it_matters": "General context only",
            "applies_to": [],
            "must_surface": False,
            "required_actions": [],
        }
    ]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_accepts_real_reference_anchor() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_rejects_background_must_read_ref_without_real_anchor() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-background",
            "kind": "paper",
            "locator": "Background review article",
            "role": "background",
            "why_it_matters": "General context only",
            "applies_to": [],
            "required_actions": ["read"],
        }
    ]
    contract["context_intake"]["must_read_refs"] = ["ref-background"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_preserves_requested_mode_for_schema_errors() -> None:
    contract = _load_contract_fixture()
    contract["references"] = ["ref-benchmark"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert result.mode == "approved"
    assert "references.0 must be an object, not str" in result.errors


def test_validate_project_contract_preserves_requested_mode_for_non_object_input() -> None:
    result = validate_project_contract([], mode="approved")

    assert result.valid is False
    assert result.mode == "approved"
    assert result.errors == ["project contract must be a JSON object"]


@pytest.mark.parametrize(
    "field_name",
    ["claims", "deliverables", "acceptance_tests", "references", "forbidden_proxies"],
)
def test_contract_results_rejects_list_inputs_for_mapping_sections(field_name: str) -> None:
    with pytest.raises(ValidationError):
        ContractResults.model_validate({field_name: []})


def test_validate_project_contract_warns_when_optional_sections_are_missing_but_scope_is_still_grounded() -> None:
    contract = _load_contract_fixture()
    contract["acceptance_tests"] = []
    contract["references"] = []
    contract["forbidden_proxies"] = []
    contract["links"] = []
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    for claim in contract.get("claims", []):
        claim["acceptance_tests"] = []
        claim["references"] = []

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is True
    assert "no acceptance_tests recorded yet" in result.warnings
    assert "no references recorded yet" in result.warnings
    assert "no forbidden_proxies recorded yet" in result.warnings


@pytest.mark.parametrize("mode", ["draft", "approved"])
def test_validate_project_contract_rejects_whole_singleton_defaulting(mode: str) -> None:
    for field_name in ("context_intake", "approach_policy", "uncertainty_markers"):
        contract = _load_contract_fixture()
        contract[field_name] = "not-a-dict"

        result = validate_project_contract(contract, mode=mode)

        assert result.valid is False
        assert result.mode == mode
        assert f"{field_name} must be an object, not str" in result.errors


def test_contract_results_strict_mode_requires_explicit_uncertainty_markers() -> None:
    with pytest.raises(ValidationError, match="uncertainty_markers"):
        ContractResults.model_validate(normalize_contract_results_input({"claims": {}}, strict=True))


def test_contract_results_strict_mode_rejects_scalar_uncertainty_marker_lists() -> None:
    payload = {
        "claims": {},
        "deliverables": {},
        "acceptance_tests": {},
        "references": {},
        "forbidden_proxies": {},
        "uncertainty_markers": {
            "weakest_anchors": "anchor-main",
            "unvalidated_assumptions": ["assumption-main"],
            "competing_explanations": ["alternative-main"],
            "disconfirming_observations": "observation-main",
        },
    }

    with pytest.raises(ValidationError) as excinfo:
        ContractResults.model_validate(normalize_contract_results_input(payload, strict=True))

    message = str(excinfo.value)
    assert "uncertainty_markers.weakest_anchors must be a list, not str" in message
    assert "uncertainty_markers.disconfirming_observations must be a list, not str" in message


@pytest.mark.parametrize(
    ("section_name", "entry_payload", "error_fragment"),
    [
        (
            "claims",
            {"status": "passed", "linked_ids": "deliv-main"},
            "claims.claim-main.linked_ids must be a list, not str",
        ),
        (
            "deliverables",
            {"status": "passed", "linked_ids": "claim-main"},
            "deliverables.deliv-main.linked_ids must be a list, not str",
        ),
        (
            "acceptance_tests",
            {"status": "passed", "linked_ids": "ref-main"},
            "acceptance_tests.test-main.linked_ids must be a list, not str",
        ),
        (
            "references",
            {"status": "completed", "completed_actions": "compare"},
            "references.ref-main.completed_actions must be a list, not str",
        ),
        (
            "references",
            {"status": "missing", "missing_actions": "cite"},
            "references.ref-main.missing_actions must be a list, not str",
        ),
    ],
)
def test_contract_results_strict_mode_rejects_scalar_string_list_drift(
    section_name: str,
    entry_payload: dict[str, object],
    error_fragment: str,
) -> None:
    entry_id_by_section = {
        "claims": "claim-main",
        "deliverables": "deliv-main",
        "acceptance_tests": "test-main",
        "references": "ref-main",
    }
    payload = {
        section_name: {entry_id_by_section[section_name]: entry_payload},
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(ValidationError, match=re.escape(error_fragment)):
        ContractResults.model_validate(normalize_contract_results_input(payload, strict=True))


def test_contract_results_non_strict_mode_is_rejected() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "linked_ids": "deliv-main",
            }
        },
        "references": {
            "ref-main": {
                "status": "completed",
                "completed_actions": "compare",
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(ValueError, match=re.escape("normalize_contract_results_input only supports strict=True")):
        normalize_contract_results_input(payload, strict=False)


def test_plan_contract_schema_uses_supported_contract_enum_values() -> None:
    schema_text = (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")

    assert "kind: paper | dataset | prior_artifact | spec | user_anchor | other" in schema_text
    assert "role: definition | benchmark | method | must_consider | background | other" in schema_text
    assert (
        "kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | human_review | other"
        in schema_text
    )
    assert "relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | other" in schema_text
    assert "prior_phase" not in schema_text
    assert "method_anchor" not in schema_text


def test_plan_contract_schema_example_values_validate_against_research_contract_model() -> None:
    contract = {
        "scope": {"question": "What benchmark must this plan recover?"},
        "claims": [
            {
                "id": "claim-main",
                "statement": "Recover the benchmark value within tolerance",
                "deliverables": ["deliv-main"],
                "acceptance_tests": ["test-main"],
                "references": ["ref-main"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-main",
                "kind": "figure",
                "path": "figures/main.png",
                "description": "Main benchmark figure",
            }
        ],
        "references": [
            {
                "id": "ref-main",
                "kind": "paper",
                "locator": "Author et al., Journal, 2024",
                "role": "benchmark",
                "why_it_matters": "Published comparison target",
                "applies_to": ["claim-main"],
                "must_surface": True,
                "required_actions": ["read", "compare", "cite"],
            }
        ],
        "acceptance_tests": [
            {
                "id": "test-main",
                "subject": "claim-main",
                "kind": "benchmark",
                "procedure": "Compare against the benchmark reference",
                "pass_condition": "Matches reference within tolerance",
                "evidence_required": ["deliv-main", "ref-main"],
            }
        ],
        "forbidden_proxies": [
            {
                "id": "fp-main",
                "subject": "claim-main",
                "proxy": "Qualitative trend match without numerical comparison",
                "reason": "Would allow false progress without the decisive benchmark",
            }
        ],
        "links": [
            {
                "id": "link-main",
                "source": "claim-main",
                "target": "deliv-main",
                "relation": "supports",
                "verified_by": ["test-main"],
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["Reference tolerance interpretation"],
            "disconfirming_observations": ["Benchmark agreement disappears after normalization fix"],
        },
    }

    parsed = ResearchContract.model_validate(contract)

    assert parsed.references[0].role == "benchmark"
    assert parsed.acceptance_tests[0].kind == "benchmark"
    assert parsed.links[0].relation == "supports"


def test_state_json_schema_project_contract_example_is_validator_compatible() -> None:
    schema_text = (TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")
    match = re.search(r"### `project_contract`\n\n```json\n(.*?)\n```", schema_text, re.DOTALL)

    assert match is not None
    contract = json.loads(match.group(1))

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract, mode="approved")

    assert parsed.scope.question == "What benchmark must the project recover?"
    assert result.valid is True
