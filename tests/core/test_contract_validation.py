"""Tests for executable project-contract validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from gpd.contracts import ResearchContract
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


def test_validate_project_contract_approved_mode_requires_anchor_signal_or_explicit_anchor_unknown() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["scope"]["unresolved_questions"] = ["Need to decide which ground-truth anchor matters most"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_accepts_explicit_anchor_unknown_blocker() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["anchor unknown; must establish later before planning"]
    contract["scope"]["unresolved_questions"] = ["Anchor unknown; must establish later"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_accepts_ground_truth_unclear_aliases() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Ground truth still unclear; no smoking gun yet for this setup"]
    contract["scope"]["unresolved_questions"] = ["Anchor is unclear and must establish later before planning"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_accepts_question_form_anchor_gap() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Which reference should serve as the decisive benchmark anchor?"]
    contract["scope"]["unresolved_questions"] = ["Which benchmark or baseline should we treat as decisive?"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_accepts_not_yet_selected_anchor_gap() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Benchmark reference not yet selected; still to identify the decisive anchor"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_accepts_prior_output_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = [".gpd/phases/00-baseline/00-01-SUMMARY.md"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


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


def test_validate_project_contract_rejects_must_surface_reference_without_applies_to() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = True
    contract["references"][0]["applies_to"] = []

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "reference ref-benchmark is must_surface but missing applies_to" in result.errors


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


def test_validate_project_contract_salvages_schema_drift_and_preserves_semantic_feedback() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["aliases"] = "not-a-list"

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "references.0.aliases: Input should be a valid list" in result.errors
    assert result.question == "What benchmark must the project recover?"
    assert result.decisive_target_count > 0
    assert result.reference_count == 1


def test_validate_project_contract_reports_extra_item_keys_without_dropping_semantic_counts() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["notes"] = "harmless"

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "claims.0.notes: Extra inputs are not permitted" in result.errors
    assert result.question == "What benchmark must the project recover?"
    assert result.decisive_target_count > 0


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


def test_validate_project_contract_warns_when_optional_sections_are_missing_but_scope_is_still_grounded() -> None:
    contract = _load_contract_fixture()
    contract["acceptance_tests"] = []
    contract["references"] = []
    contract["forbidden_proxies"] = []
    contract["links"] = []
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [".gpd/phases/00-baseline/00-01-SUMMARY.md"],
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
