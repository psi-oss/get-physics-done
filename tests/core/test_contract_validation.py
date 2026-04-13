"""Tests for executable project-contract validation."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.contracts import (
    PROOF_AUDIT_REVIEWER,
    ComparisonVerdict,
    ContractApproachPolicy,
    ContractClaim,
    ContractProofParameter,
    ContractResults,
    ProjectContractParseResult,
    ResearchContract,
    SuggestedContractCheck,
    claim_requires_proof_audit,
    collect_plan_contract_integrity_errors,
    contract_from_data,
    contract_from_data_salvage,
    normalize_contract_results_input,
    parse_comparison_verdicts_data_strict,
    parse_contract_results_data_artifact,
    parse_contract_results_data_strict,
    parse_project_contract_data_salvage,
    parse_project_contract_data_strict,
)
from gpd.core.contract_validation import (
    is_authoritative_project_contract_schema_finding,
    is_repair_relevant_project_contract_schema_finding,
    split_project_contract_schema_findings,
    validate_project_contract,
)
from gpd.core.referee_policy import RefereeDecisionInput
from gpd.mcp.paper.models import ReviewFinding, ReviewIssue, ReviewIssueSeverity, ReviewRecommendation, ReviewStageKind

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


def test_project_contract_schema_finding_helpers_keep_authoritative_and_blocking_classes_distinct() -> None:
    assert is_authoritative_project_contract_schema_finding("schema_version must be the integer 1") is True
    assert is_authoritative_project_contract_schema_finding("references.0.must_surface must be a boolean") is True
    assert (
        is_authoritative_project_contract_schema_finding("schema_version: Input should be 1 [type=literal_error]")
        is True
    )
    assert (
        is_authoritative_project_contract_schema_finding(
            "references.0.must_surface: Input should be a valid boolean, unable to interpret input"
        )
        is True
    )
    assert (
        is_authoritative_project_contract_schema_finding("references.0.must_surface: boolean wording changed upstream")
        is False
    )


def test_split_project_contract_schema_findings_separates_case_drift_from_blocking_errors() -> None:
    findings = [
        "legacy_notes: Extra inputs are not permitted",
        "observables.0.kind must use exact canonical value: other",
        "schema_version must be the integer 1",
    ]

    recoverable, blocking = split_project_contract_schema_findings(findings, allow_case_drift_recovery=False)

    assert recoverable == ["legacy_notes: Extra inputs are not permitted"]
    assert blocking == [
        "observables.0.kind must use exact canonical value: other",
        "schema_version must be the integer 1",
    ]

    recoverable, blocking = split_project_contract_schema_findings(findings, allow_case_drift_recovery=True)

    assert recoverable == [
        "legacy_notes: Extra inputs are not permitted",
        "observables.0.kind must use exact canonical value: other",
    ]
    assert blocking == ["schema_version must be the integer 1"]


def test_split_project_contract_schema_findings_blocks_nested_collection_item_truncation() -> None:
    findings = [
        "claims.0.parameters.0.domain_or_type: Input should be a valid string",
        "claims.0.parameters.0.aliases.1: Input should be a valid string",
    ]

    recoverable, blocking = split_project_contract_schema_findings(findings, allow_case_drift_recovery=True)

    assert recoverable == []
    assert blocking == findings


def test_project_contract_schema_finding_helpers_keep_repair_relevance_stable_for_equivalent_messages() -> None:
    assert is_repair_relevant_project_contract_schema_finding("legacy_notes: Extra inputs are not permitted") is True
    assert (
        is_repair_relevant_project_contract_schema_finding(
            "legacy_notes: Extra inputs are not permitted [type=extra_forbidden]"
        )
        is True
    )
    assert (
        is_repair_relevant_project_contract_schema_finding("observables.0.kind must use exact canonical value: other")
        is False
    )
    assert (
        is_repair_relevant_project_contract_schema_finding(
            "references.0.must_surface: Input should be a valid boolean, unable to interpret input"
        )
        is False
    )


@pytest.mark.parametrize(
    ("claim_payload", "expected"),
    [
        (
            {"id": "claim-generic", "statement": "The theorem appears in the benchmark discussion."},
            False,
        ),
        (
            {"id": "claim-proof", "statement": "For all x > 0, F(x) >= 0."},
            True,
        ),
    ],
)
def test_claim_requires_proof_audit_ignores_generic_theorem_words_and_keeps_explicit_quantifiers(
    claim_payload: dict[str, object],
    expected: bool,
) -> None:
    claim = ContractClaim.model_validate(claim_payload)

    assert claim_requires_proof_audit(claim, {}) is expected


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


def test_contract_from_data_rejects_singleton_list_drift_by_default() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    assert contract_from_data(contract) is None


def test_contract_from_data_salvage_accepts_recoverable_list_drift() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    parsed = contract_from_data_salvage(contract)

    assert parsed is not None
    assert parsed.context_intake.must_read_refs == ["ref-benchmark"]


def test_contract_from_data_salvage_rejects_non_object_approach_policy() -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = []

    parsed = parse_project_contract_data_salvage(contract)

    assert parsed.contract is not None
    assert parsed.contract.approach_policy == ContractApproachPolicy()
    assert parsed.blocking_errors == ["approach_policy must be an object, not list"]
    assert parsed.recoverable_errors == []
    assert contract_from_data_salvage(contract) is None


@pytest.mark.parametrize(
    ("field_name", "expected_error"),
    [
        ("schema_version", "schema_version is required"),
        ("scope", "scope is required"),
        ("context_intake", "context_intake is required"),
        ("uncertainty_markers", "uncertainty_markers is required"),
    ],
)
def test_contract_from_data_salvage_rejects_missing_required_sections(field_name: str, expected_error: str) -> None:
    contract = _load_contract_fixture()
    contract.pop(field_name)

    parsed = parse_project_contract_data_salvage(contract)

    assert parsed.contract is None
    assert expected_error in parsed.blocking_errors
    assert contract_from_data_salvage(contract) is None


def test_validate_project_contract_approved_mode_rejects_unknown_proof_deliverables() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["proof_deliverables"] = ["deliv-missing"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert "claim claim-benchmark references unknown proof deliverable deliv-missing" in result.errors


def test_validate_project_contract_draft_mode_rejects_unknown_proof_deliverables() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["proof_deliverables"] = ["deliv-missing"]

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert "claim claim-benchmark references unknown proof deliverable deliv-missing" in result.errors


def test_contract_from_data_salvage_rejects_missing_uncertainty_marker_subfields() -> None:
    contract = _load_contract_fixture()
    contract["uncertainty_markers"] = {}

    parsed = parse_project_contract_data_salvage(contract)

    assert parsed.contract is None
    assert parsed.blocking_errors == [
        "uncertainty_markers.weakest_anchors is required",
        "uncertainty_markers.disconfirming_observations is required",
    ]
    assert contract_from_data_salvage(contract) is None


def test_parse_project_contract_data_strict_rejects_nested_proof_list_scalar_drift() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {
            "symbol": "r_0",
            "aliases": "r0",
            "required_in_proof": True,
        }
    ]
    contract["claims"][0]["hypotheses"] = [
        {
            "id": "hyp-r0",
            "text": "r_0 >= 0",
            "symbols": "r_0",
            "required_in_proof": True,
        }
    ]

    parsed = parse_project_contract_data_strict(contract)

    assert parsed.contract is None
    assert "claims.0.parameters.0.aliases must be a list, not str" in parsed.errors
    assert "claims.0.hypotheses.0.symbols must be a list, not str" in parsed.errors


def test_parse_project_contract_data_strict_rejects_blank_nested_proof_list_scalar_drift_without_mutation() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {
            "symbol": "r_0",
            "aliases": "   ",
            "required_in_proof": True,
        }
    ]
    contract["claims"][0]["hypotheses"] = [
        {
            "id": "hyp-r0",
            "text": "r_0 >= 0",
            "symbols": "   ",
            "required_in_proof": True,
        }
    ]

    parsed = parse_project_contract_data_strict(contract)

    assert parsed.contract is None
    assert "claims.0.parameters.0.aliases must be a list, not str" in parsed.errors
    assert "claims.0.hypotheses.0.symbols must be a list, not str" in parsed.errors
    assert contract["claims"][0]["parameters"][0]["aliases"] == "   "
    assert contract["claims"][0]["hypotheses"][0]["symbols"] == "   "


def test_parse_contract_results_data_strict_rejects_evidence_scalar_and_case_drift() -> None:
    with pytest.raises(ValidationError):
        ContractResults.model_validate(
            normalize_contract_results_input(
                {
                    "claims": {
                        "claim-main": {
                            "status": "Passed",
                            "evidence": [
                                {
                                    "confidence": "High",
                                    "covered_hypothesis_ids": "hyp-main",
                                }
                            ],
                        }
                    },
                    "uncertainty_markers": {
                        "weakest_anchors": ["anchor-1"],
                        "unvalidated_assumptions": [],
                        "competing_explanations": [],
                        "disconfirming_observations": ["obs-1"],
                    },
                },
            )
        )

    with pytest.raises(ValueError, match=r"claims\.claim-main\.status must use exact literal 'passed'"):
        parse_contract_results_data_strict(
            {
                "claims": {
                    "claim-main": {
                        "status": "Passed",
                        "evidence": [
                            {
                                "confidence": "High",
                                "covered_hypothesis_ids": "hyp-main",
                            }
                        ],
                    }
                },
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "unvalidated_assumptions": [],
                    "competing_explanations": [],
                    "disconfirming_observations": ["obs-1"],
                },
            }
        )


def test_parse_contract_results_data_artifact_accepts_case_drift_and_string_list_drift() -> None:
    parsed = parse_contract_results_data_artifact(
        {
            "claims": {
                "claim-main": {
                    "status": "Passed",
                    "evidence": [
                        {
                            "confidence": "High",
                            "covered_hypothesis_ids": "hyp-main",
                        }
                    ],
                }
            },
            "references": {
                "ref-main": {
                    "status": "Completed",
                    "completed_actions": "Read",
                    "missing_actions": [],
                }
            },
            "uncertainty_markers": {
                "weakest_anchors": ["anchor-1"],
                "unvalidated_assumptions": [],
                "competing_explanations": [],
                "disconfirming_observations": ["obs-1"],
            },
        }
    )

    assert parsed.claims["claim-main"].status == "passed"
    assert parsed.claims["claim-main"].evidence[0].confidence == "high"
    assert parsed.claims["claim-main"].evidence[0].covered_hypothesis_ids == ["hyp-main"]
    assert parsed.references["ref-main"].status == "completed"
    assert parsed.references["ref-main"].completed_actions == ["read"]


def test_parse_contract_results_data_artifact_accepts_linked_ids_and_uncertainty_singletons() -> None:
    parsed = parse_contract_results_data_artifact(
        {
            "claims": {
                "claim-main": {
                    "status": "Passed",
                    "linked_ids": "deliv-main",
                }
            },
            "uncertainty_markers": {
                "weakest_anchors": "anchor-1",
                "unvalidated_assumptions": "assumption-1",
                "competing_explanations": "alternative-1",
                "disconfirming_observations": "obs-1",
            },
        }
    )

    assert parsed.claims["claim-main"].status == "passed"
    assert parsed.claims["claim-main"].linked_ids == ["deliv-main"]
    assert parsed.uncertainty_markers.weakest_anchors == ["anchor-1"]
    assert parsed.uncertainty_markers.unvalidated_assumptions == ["assumption-1"]
    assert parsed.uncertainty_markers.competing_explanations == ["alternative-1"]
    assert parsed.uncertainty_markers.disconfirming_observations == ["obs-1"]


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {
                "claims": {
                    "claim-main": {
                        "evidence": [],
                    }
                },
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "unvalidated_assumptions": [],
                    "competing_explanations": [],
                    "disconfirming_observations": ["obs-1"],
                },
            },
            "claims.claim-main.status must be explicit in contract-backed contract_results",
        ),
        (
            {
                "claims": {
                    "claim-main": {
                        "status": "passed",
                        "proof_audit": {
                            "reviewed_at": "2025-01-01T00:00:00",
                            "reviewer": "gpd-check-proof",
                        },
                    }
                },
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "unvalidated_assumptions": [],
                    "competing_explanations": [],
                    "disconfirming_observations": ["obs-1"],
                },
            },
            "claims.claim-main.proof_audit.completeness must be explicit in contract-backed contract_results",
        ),
        (
            {
                "claims": {
                    "claim-main": {
                        "status": "passed",
                        "evidence": [],
                    }
                }
            },
            "uncertainty_markers must be explicit in contract-backed contract_results",
        ),
    ],
)
def test_parse_contract_results_data_artifact_rejects_missing_explicit_blockers(
    payload: dict[str, object],
    expected_error: str,
) -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_contract_results_data_artifact(payload)

    assert expected_error in str(exc_info.value)


def test_parse_contract_results_data_artifact_rejects_blank_and_duplicate_list_members() -> None:
    with pytest.raises(ValueError, match=r"claims\.claim-main\.linked_ids\.2 is a duplicate"):
        parse_contract_results_data_artifact(
            {
                "claims": {
                    "claim-main": {
                        "status": "passed",
                        "linked_ids": ["deliv-main", " ", "deliv-main"],
                        "proof_audit": {
                            "completeness": "complete",
                            "covered_hypothesis_ids": ["hyp-main", " ", "hyp-main"],
                        },
                        "evidence": [
                            {
                                "confidence": "high",
                                "covered_hypothesis_ids": ["hyp-main", " ", "hyp-main"],
                            }
                        ],
                    }
                },
                "references": {
                    "ref-main": {
                        "status": "completed",
                        "completed_actions": ["read", " ", "read"],
                        "missing_actions": [],
                    }
                },
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1", " ", "anchor-1"],
                    "unvalidated_assumptions": [],
                    "competing_explanations": [],
                    "disconfirming_observations": ["obs-1"],
                },
            }
        )


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {
                "claims": {"claim-main": {"status": "failed"}},
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "disconfirming_observations": ["obs-1"],
                },
            },
            "claims.claim-main.status=failed requires summary, notes, or evidence explaining the gap",
        ),
        (
            {
                "deliverables": {"deliv-main": {"status": "blocked"}},
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "disconfirming_observations": ["obs-1"],
                },
            },
            "deliverables.deliv-main.status=blocked requires summary, notes, or evidence explaining the gap",
        ),
        (
            {
                "references": {
                    "ref-main": {
                        "status": "missing",
                        "missing_actions": ["cite"],
                    }
                },
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "disconfirming_observations": ["obs-1"],
                },
            },
            "references.ref-main.status=missing requires summary or evidence explaining what is missing",
        ),
        (
            {
                "forbidden_proxies": {"fp-main": {"status": "unresolved"}},
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-1"],
                    "disconfirming_observations": ["obs-1"],
                },
            },
            "forbidden_proxies.fp-main.status=unresolved requires notes or evidence explaining the proxy issue",
        ),
    ],
)
def test_parse_contract_results_data_artifact_rejects_underspecified_incomplete_statuses(
    payload: dict[str, object],
    expected_error: str,
) -> None:
    with pytest.raises(ValueError, match=re.escape(expected_error)):
        parse_contract_results_data_artifact(payload)


def test_parse_project_contract_data_salvage_reports_recoverable_findings() -> None:
    contract = _load_contract_fixture()
    contract["scope"]["legacy_notes"] = "nested extra field"

    result: ProjectContractParseResult = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.blocking_errors == []
    assert "scope.legacy_notes: Extra inputs are not permitted" in result.recoverable_errors
    assert result.errors == result.recoverable_errors


def test_parse_project_contract_data_salvage_reports_literal_case_drift_as_recoverable_findings() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["role"] = "Benchmark"
    contract["references"][0]["required_actions"] = ["Read", "Compare", "Cite"]

    result: ProjectContractParseResult = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.references[0].role == "benchmark"
    assert result.contract.references[0].required_actions == ["read", "compare", "cite"]
    assert "references.0.role must use exact canonical value: benchmark" in result.recoverable_errors
    assert "references.0.required_actions.0 must use exact canonical value: read" in result.recoverable_errors


def test_parse_comparison_verdicts_data_strict_rejects_case_drift() -> None:
    with pytest.raises(ValueError, match=r"\[0\] subject_kind: Value error, must use exact literal 'claim'"):
        parse_comparison_verdicts_data_strict(
            [
                {
                    "subject_id": "claim-main",
                    "subject_kind": "Claim",
                    "subject_role": "Decisive",
                    "comparison_kind": "Benchmark",
                    "verdict": "Pass",
                }
            ]
        )


def test_suggested_contract_check_requires_kind_and_id_together_at_model_boundary() -> None:
    with pytest.raises(ValidationError, match="suggested_subject_kind and suggested_subject_id must appear together"):
        SuggestedContractCheck.model_validate(
            {
                "check": "Add decisive benchmark rerun",
                "reason": "Need the tighter benchmark gate.",
                "suggested_subject_kind": "acceptance_test",
            }
        )

    with pytest.raises(ValidationError, match="suggested_subject_kind and suggested_subject_id must appear together"):
        SuggestedContractCheck.model_validate(
            {
                "check": "Add decisive benchmark rerun",
                "reason": "Need the tighter benchmark gate.",
                "suggested_subject_id": "test-benchmark",
            }
        )


def test_comparison_verdict_requires_reference_binding_for_decisive_external_comparisons_at_model_boundary() -> None:
    with pytest.raises(
        ValidationError,
        match=r"must include reference_id or use subject_kind: reference for decisive benchmark comparisons",
    ):
        ComparisonVerdict.model_validate(
            {
                "subject_id": "claim-main",
                "subject_kind": "claim",
                "subject_role": "decisive",
                "comparison_kind": "benchmark",
                "verdict": "pass",
            }
        )

    verdict = ComparisonVerdict.model_validate(
        {
            "subject_id": "ref-benchmark",
            "subject_kind": "reference",
            "subject_role": "decisive",
            "comparison_kind": "benchmark",
            "verdict": "pass",
        }
    )

    assert verdict.reference_id is None


def test_parse_project_contract_data_salvage_preserves_blocking_errors_for_missing_required_collection_item_field() -> (
    None
):
    contract = _load_contract_fixture()
    del contract["claims"][0]["statement"]

    result: ProjectContractParseResult = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert "claims.0.statement is required" in result.blocking_errors
    assert contract_from_data_salvage(contract) is None


def test_parse_project_contract_data_salvage_treats_singleton_shape_drift_as_blocking() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"] = "not-a-dict"

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is None
    assert result.blocking_errors == ["context_intake must be an object, not str"]
    assert result.recoverable_errors == []


@pytest.mark.parametrize(
    ("collection_name", "expected_error"),
    [
        ("claims", "claims.0.statement"),
        ("references", "references.0.must_surface"),
        ("acceptance_tests", "acceptance_tests.0.kind"),
    ],
)
def test_parse_project_contract_data_salvage_preserves_valid_siblings_when_one_collection_member_is_invalid(
    collection_name: str,
    expected_error: str,
) -> None:
    contract = _load_contract_fixture()
    sibling_id: str
    if collection_name == "claims":
        sibling = copy.deepcopy(contract["claims"][0])
        sibling_id = "claim-sibling"
        sibling["id"] = sibling_id
        contract["claims"].append(sibling)
        contract["claims"][0].pop("statement")
    elif collection_name == "references":
        sibling = copy.deepcopy(contract["references"][0])
        sibling_id = "ref-sibling"
        sibling["id"] = sibling_id
        contract["references"].append(sibling)
        contract["references"][0]["must_surface"] = "yes"
    elif collection_name == "acceptance_tests":
        sibling = copy.deepcopy(contract["acceptance_tests"][0])
        sibling_id = "test-sibling"
        sibling["id"] = sibling_id
        contract["acceptance_tests"].append(sibling)
        contract["acceptance_tests"][0]["kind"] = "Robot"
    else:
        raise AssertionError(f"unexpected collection: {collection_name}")

    result: ProjectContractParseResult = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert any(item.id == sibling_id for item in getattr(result.contract, collection_name))
    if collection_name == "references":
        assert result.blocking_errors == ["references.0.must_surface must be a boolean"]
    else:
        assert any(expected_error in error for error in result.blocking_errors)
    assert contract_from_data_salvage(contract) is None


def test_parse_project_contract_data_salvage_preserves_blocking_errors_for_wrong_collection_type() -> None:
    contract = _load_contract_fixture()
    contract["claims"] = {"claim-1": contract["claims"][0]}

    result: ProjectContractParseResult = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert "claims must be a list, not dict" in result.blocking_errors


def test_contract_from_data_salvage_rejects_blocking_salvage_errors() -> None:
    contract = _load_contract_fixture()
    contract["claims"] = {"claim-1": contract["claims"][0]}

    assert contract_from_data_salvage(contract) is None


def test_parse_project_contract_data_salvage_preserves_contract_with_top_level_extra_keys() -> None:
    contract = _load_contract_fixture()
    contract["legacy_notes"] = "forwarded from a prior schema revision"

    result: ProjectContractParseResult = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.blocking_errors == []
    assert result.recoverable_errors == ["legacy_notes: Extra inputs are not permitted"]
    assert "legacy_notes" not in result.contract.model_dump()


def test_parse_project_contract_data_strict_rejects_singleton_list_drift() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert result.errors == ["context_intake.must_read_refs must be a list, not str"]


def test_parse_project_contract_data_strict_rejects_blank_list_members() -> None:
    contract = _load_contract_fixture()
    contract["scope"]["in_scope"] = ["benchmarking", " "]

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "scope.in_scope.1 must not be blank" in result.errors


def test_parse_project_contract_data_strict_rejects_duplicate_list_members() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", "ref-benchmark"]

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "context_intake.must_read_refs.1 is a duplicate" in result.errors


def test_parse_project_contract_data_strict_rejects_literal_case_drift() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["role"] = "Benchmark"
    contract["references"][0]["required_actions"] = ["Read", "Compare", "Cite"]

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "references.0.role must use exact canonical value: benchmark" in result.errors
    assert "references.0.required_actions.0 must use exact canonical value: read" in result.errors


def test_parse_project_contract_data_strict_rejects_nested_proof_list_member_drift() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {"symbol": "r_0", "domain_or_type": "nonnegative real", "aliases": ["r0", " "]}
    ]
    contract["claims"][0]["hypotheses"] = [{"id": "hyp-r0", "text": "r_0 >= 0", "symbols": ["r_0", "r_0"]}]

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "claims.0.parameters.0.aliases.1 must not be blank" in result.errors
    assert "claims.0.hypotheses.0.symbols.1 is a duplicate" in result.errors


def test_parse_project_contract_data_strict_rejects_recoverable_nested_extra_keys() -> None:
    contract = _load_contract_fixture()
    contract["scope"]["legacy_notes"] = "nested extra field"

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert result.errors == ["scope.legacy_notes: Extra inputs are not permitted"]


def test_parse_project_contract_data_strict_rejects_missing_schema_version() -> None:
    contract = _load_contract_fixture()
    contract.pop("schema_version")

    result: ProjectContractParseResult = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert result.errors == ["schema_version is required"]


def test_contract_from_data_rejects_literal_case_drift_by_default() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["role"] = "Benchmark"

    assert contract_from_data(contract) is None


def test_contract_proof_parameter_round_trips_without_domain_or_type() -> None:
    parameter = ContractProofParameter.model_validate({"symbol": "r_0"})

    assert parameter.domain_or_type is None
    assert ContractProofParameter.model_validate(parameter.model_dump()) == parameter


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
    assert "uncertainty_markers.disconfirming_observations must identify what would force a rethink" in result.errors


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

    assert result.valid is False
    assert result.guidance_signal_count == 0
    assert "context_intake must not be empty" in result.errors


def test_validate_project_contract_rejects_placeholder_only_anchor_guidance() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": ["TBD"],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert result.guidance_signal_count == 0
    assert "context_intake must not be empty" in result.errors
    assert (
        "context_intake.user_asserted_anchors entry is not concrete enough to preserve as durable guidance: TBD"
        in result.warnings
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("user_asserted_anchors", "Nature benchmark"),
        ("known_good_baselines", "Baseline notebook A"),
    ],
)
def test_validate_project_contract_warns_for_non_concrete_anchor_guidance(
    field_name: str,
    value: str,
) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"][field_name] = [value]

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert result.guidance_signal_count == 0
    assert "context_intake must not be empty" in result.errors
    assert (
        f"context_intake.{field_name} entry is not concrete enough to preserve as durable guidance: {value}"
        in result.warnings
    )


def test_validate_project_contract_rejects_missing_prior_output_only_guidance(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": ["missing/path.md"],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    result = validate_project_contract(contract, mode="draft", project_root=tmp_path)

    assert result.valid is False
    assert result.guidance_signal_count == 0
    assert "context_intake must not be empty" in result.errors
    assert (
        "context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact: missing/path.md"
        in result.warnings
    )


def test_validate_project_contract_rejects_bare_filename_prior_output_without_explicit_path() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = ["RESULTS.md"]

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert result.guidance_signal_count == 0
    assert "context_intake must not be empty" in result.errors
    assert (
        "context_intake.must_include_prior_outputs entry is not an explicit project artifact path: RESULTS.md"
        in result.warnings
    )


def test_validate_project_contract_accepts_explicit_relative_prior_output_path_without_project_root() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = ["./RESULTS.md"]

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is True
    assert result.guidance_signal_count == 1
    assert "context_intake must not be empty" not in result.errors


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


def test_validate_project_contract_approved_mode_rejects_context_gaps_only_grounding() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["context_gaps"] = ["Need a benchmark anchor before approval."]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("explicit missing-anchor notes preserve uncertainty" in error for error in result.errors)


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
    contract["context_intake"]["context_gaps"] = [
        "Benchmark reference not yet selected; still to identify the decisive anchor"
    ]
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
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

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
        ("paper", "https://doi.org/10.1234/unknown-example"),
        ("other", "Einstein, Annalen der Physik, 1905"),
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
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"
    assert result.guidance_signal_count == 1
    assert result.guidance_signal_count == 1


@pytest.mark.parametrize(
    ("reference_kind", "locator"), [("paper", "Table 2"), ("paper", "Fig. 3"), ("paper", "Section 4")]
)
def test_validate_project_contract_approved_mode_rejects_bare_reference_locator_grounding(
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
            "role": "benchmark",
            "why_it_matters": "Bare section/table/figure locators must not ground approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("user_asserted_anchors", "Nature benchmark"), ("known_good_baselines", "Science benchmark")],
)
def test_validate_project_contract_approved_mode_rejects_journal_only_text_grounding(
    field_name: str,
    value: str,
) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []
    contract["context_intake"][field_name] = [value]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize(
    ("reference_kind", "locator"),
    [
        ("dataset", "https://huggingface.co/datasets/org/sample"),
        ("spec", "https://docs.example.org/specs/solver-v2"),
        ("prior_artifact", "https://github.com/org/repo/blob/main/artifacts/report.json"),
    ],
)
def test_validate_project_contract_approved_mode_accepts_external_nonpaper_urls(
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
            "role": "benchmark",
            "why_it_matters": "Concrete external nonpaper URLs should satisfy approved grounding.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"
    assert result.guidance_signal_count == 1
    assert result.guidance_signal_count == 1


@pytest.mark.parametrize("reference_kind", ["dataset", "spec", "prior_artifact"])
def test_validate_project_contract_approved_mode_rejects_root_only_external_nonpaper_urls(
    reference_kind: str,
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": reference_kind,
            "locator": "https://example.org/",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Root-only URLs should not satisfy approved grounding.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["context_gaps"] = ["Need a concrete must-surface anchor before approval."]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


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
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_approved_mode_rejects_project_local_prior_artifact_locator_without_project_root(
    tmp_path: Path,
) -> None:
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
            "why_it_matters": "Concrete prior artifact should not count without a resolved project root.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_rejects_missing_project_local_prior_artifact_locator(
    tmp_path: Path,
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "prior_artifact",
            "locator": "artifacts/benchmark/missing-report.json",
            "aliases": [],
            "role": "background",
            "why_it_matters": "Missing prior artifacts should not count as approved grounding.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


def test_validate_project_contract_approved_mode_warns_for_invalid_must_surface_reference_when_other_concrete_grounding_exists() -> (
    None
):
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
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

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
    contract["context_intake"]["context_gaps"] = ["Need a concrete must-surface anchor before approval."]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_draft_mode_warns_for_invalid_grounding_entries_with_concrete_anchor_present(
    tmp_path: Path,
) -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_include_prior_outputs"] = ["fake/path"]
    contract["context_intake"]["user_asserted_anchors"] = ["TBD"]
    contract["references"].append(
        {
            "id": "ref-placeholder",
            "kind": "paper",
            "locator": "TBD",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Placeholder must-surface anchor should still be surfaced as a warning.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    )

    result = validate_project_contract(contract, mode="draft", project_root=tmp_path)

    assert result.valid is True
    assert (
        "context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact: fake/path"
        in result.warnings
    )
    assert (
        "context_intake.user_asserted_anchors entry is not concrete enough to preserve as durable guidance: TBD"
        in result.warnings
    )
    assert (
        "reference ref-placeholder is must_surface but locator is not concrete enough to ground validation"
        in result.warnings
    )


def test_validate_project_contract_approved_mode_warns_for_invalid_must_surface_locator_with_global_non_reference_grounding(
    tmp_path: Path,
) -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_include_prior_outputs"] = ["fake/path"]
    contract["context_intake"]["user_asserted_anchors"] = ["TBD"]
    contract["references"].append(
        {
            "id": "ref-placeholder",
            "kind": "paper",
            "locator": "TBD",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Placeholder must-surface anchor should be blocked in approved mode.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    )

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert result.valid is True
    assert (
        "reference ref-placeholder is must_surface but locator is not concrete enough to ground validation"
        in result.warnings
    )
    assert (
        "reference ref-placeholder is must_surface but locator is not concrete enough to ground validation"
        not in result.errors
    )


def test_validate_project_contract_approved_mode_blocks_placeholder_must_surface_for_ungrounded_target() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["observables"].append(
        {
            "id": "obs-second",
            "name": "secondary observable",
            "kind": "scalar",
            "definition": "Second decisive observable",
        }
    )
    contract["claims"].append(
        {
            "id": "claim-second",
            "statement": "Recover the second benchmark value within tolerance",
            "observables": ["obs-second"],
            "deliverables": ["deliv-second"],
            "acceptance_tests": ["test-second"],
            "references": ["ref-second"],
        }
    )
    contract["deliverables"].append(
        {
            "id": "deliv-second",
            "kind": "figure",
            "path": "figures/second-benchmark.png",
            "description": "Second benchmark comparison figure",
            "must_contain": ["second baseline curve"],
        }
    )
    contract["acceptance_tests"].append(
        {
            "id": "test-second",
            "subject": "claim-second",
            "kind": "benchmark",
            "procedure": "Compare against the second benchmark reference",
            "pass_condition": "Matches the second reference within tolerance",
            "evidence_required": ["deliv-second", "ref-second"],
            "automation": "hybrid",
        }
    )
    contract["references"] = [
        {
            "id": "ref-benchmark",
            "kind": "paper",
            "locator": "doi:10.1234/example",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Concrete anchor for the first claim only.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        },
        {
            "id": "ref-second",
            "kind": "paper",
            "locator": "TBD",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Placeholder anchor for the second claim must still block approval.",
            "applies_to": ["claim-second"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        },
    ]
    contract["forbidden_proxies"].append(
        {
            "id": "fp-second",
            "subject": "claim-second",
            "proxy": "qualitative agreement without the second benchmark comparison",
            "reason": "Would miss the decisive second target.",
        }
    )

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert "reference ref-second is must_surface but locator is not concrete enough to ground validation" in result.errors
    assert "reference ref-second is must_surface but locator is not concrete enough to ground validation" not in result.warnings


@pytest.mark.parametrize(
    "locator",
    ["Benchmark paper", "reference article", "/tmp/nonexistent.txt", "report.pdf", "https://example.com/paper"],
)
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
    contract["context_intake"]["context_gaps"] = ["Need a concrete must-surface anchor before approval."]

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
def test_validate_project_contract_approved_mode_rejects_generic_text_grounding(
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

    assert result.valid is False
    assert result.mode == "approved"
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("user_asserted_anchors", ["arXiv:2401.12345"]),
        ("known_good_baselines", ["doi:10.1234/example"]),
        ("known_good_baselines", ["https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.123.4567"]),
    ],
)
def test_validate_project_contract_approved_mode_accepts_short_concrete_locator_grounding(
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


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("user_asserted_anchors", ["../tmp/off-repo-anchor.md"]),
        ("known_good_baselines", ["/tmp/off-repo-anchor.md"]),
    ],
)
def test_validate_project_contract_approved_mode_rejects_out_of_tree_path_like_grounding_without_project_root(
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

    assert result.valid is False
    assert result.mode == "approved"
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.org/missing-data-benchmark.csv",
    ],
)
def test_validate_project_contract_approved_mode_accepts_placeholder_word_locators_in_non_reference_grounding(
    value: str,
) -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = [value]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"
    assert result.guidance_signal_count == 1


def test_validate_project_contract_approved_mode_rejects_rootless_project_local_baseline_locator() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = ["GPD/phases/03-missing-energy/03-01-SUMMARY.md"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert result.mode == "approved"
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)
    assert any(
        "context_intake.known_good_baselines entry requires a resolved project_root to verify artifact grounding"
        in warning
        for warning in result.warnings
    )


def test_referee_decision_input_rejects_string_booleans() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RefereeDecisionInput(
            manuscript_path="paper/curvature_flow_bounds.tex",
            target_journal="prl",
            final_recommendation=ReviewRecommendation.major_revision,
            central_claims_supported="yes",
            claim_scope_proportionate_to_evidence="no",
            physical_assumptions_justified="yes",
            proof_audit_coverage_complete="yes",
            theorem_proof_alignment_adequate="no",
            unsupported_claims_are_central="yes",
            reframing_possible_without_new_results="no",
        )

    message = str(exc_info.value)
    assert "central_claims_supported" in message
    assert "proof_audit_coverage_complete" in message
    assert "theorem_proof_alignment_adequate" in message


def test_review_finding_rejects_string_blocking_flag() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ReviewFinding(
            issue_id="REF-001",
            claim_ids=[],
            severity=ReviewIssueSeverity.major,
            summary="Needs follow-up.",
            blocking="yes",
        )

    assert "blocking" in str(exc_info.value)


def test_review_issue_rejects_string_blocking_flag() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ReviewIssue(
            issue_id="REF-001",
            opened_by_stage=ReviewStageKind.math,
            severity=ReviewIssueSeverity.major,
            blocking="no",
            summary="Needs follow-up.",
        )

    assert "blocking" in str(exc_info.value)


def test_validate_project_contract_approved_mode_rejects_repeated_generic_paper_phrase() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["known_good_baselines"] = ["paper paper paper"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in result.errors)


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


def test_validate_project_contract_approved_mode_rejects_unresolved_prior_output_without_project_root() -> None:
    contract = _load_contract_fixture()
    contract["references"] = []
    _remove_incidental_grounding(contract)
    contract["context_intake"]["must_include_prior_outputs"] = ["./RESULTS.md"]
    contract["scope"]["unresolved_questions"] = []

    result = validate_project_contract(contract, mode="approved")

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


def test_validate_project_contract_approved_mode_rejects_placeholder_user_asserted_anchor_even_with_explicit_blocker() -> (
    None
):
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


def test_validate_project_contract_requires_theorem_inventory_for_proof_bearing_claims() -> None:
    contract = {
        "schema_version": 1,
        "scope": {"question": "Can the theorem be proved as stated?", "in_scope": ["Prove the theorem as stated."]},
        "context_intake": {"must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"]},
        "observables": [
            {
                "id": "obs-proof",
                "name": "proof obligation",
                "kind": "proof_obligation",
                "definition": "Prove the theorem for every named parameter",
            }
        ],
        "claims": [
            {
                "id": "claim-proof",
                "statement": "For all r_0 >= 0, F(r_0) >= 0.",
                "claim_kind": "theorem",
                "observables": ["obs-proof"],
                "deliverables": ["deliv-proof"],
                "acceptance_tests": ["test-proof-align"],
                "proof_deliverables": ["deliv-proof"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-proof",
                "kind": "derivation",
                "path": "derivations/theorem-proof.tex",
                "description": "Detailed theorem proof",
            }
        ],
        "acceptance_tests": [
            {
                "id": "test-proof-align",
                "subject": "claim-proof",
                "kind": "claim_to_proof_alignment",
                "procedure": "Audit the theorem against the proof",
                "pass_condition": "No theorem parameter or hypothesis is silently dropped",
            }
        ],
        "forbidden_proxies": [
            {
                "id": "fp-proof",
                "subject": "claim-proof",
                "proxy": "Centered subcase only",
                "reason": "Would silently specialize away r_0",
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["The theorem inventory is still incomplete."],
            "disconfirming_observations": ["A proof that drops r_0 invalidates the claim."],
        },
    }

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "claim claim-proof missing parameters for proof-bearing claim" in result.errors
    assert "claim claim-proof missing hypotheses for proof-bearing claim" in result.errors
    assert "claim claim-proof missing conclusion_clauses for proof-bearing claim" in result.errors


def test_validate_project_contract_normalizes_reference_required_actions_whitespace_and_duplicates() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["required_actions"] = [" Read ", "compare", "read", "  ", " Cite "]

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract)

    assert parsed.references[0].required_actions == ["read", "compare", "cite"]
    assert result.valid is True
    assert "references.0.required_actions.3 must not be blank" in result.warnings


def test_validate_project_contract_salvages_singleton_list_string_drift_at_validation_boundary() -> None:
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
    assert "context_intake.must_include_prior_outputs must be a list, not str" in result.warnings


@pytest.mark.parametrize(
    ("mutator", "expected_valid", "expected_error", "expected_warning"),
    [
        (
            lambda contract: contract["claims"][0].__setitem__("references", "   "),
            True,
            None,
            "claims.0.references must not be blank",
        ),
        (
            lambda contract: contract["scope"].__setitem__("in_scope", "   "),
            False,
            "scope.in_scope must name at least one project boundary or objective",
            "scope.in_scope must not be blank",
        ),
    ],
)
def test_validate_project_contract_rejects_blank_scalar_to_list_drift(
    mutator,
    expected_valid: bool,
    expected_error: str | None,
    expected_warning: str,
) -> None:
    contract = _load_contract_fixture()
    mutator(contract)

    result = validate_project_contract(contract)

    assert result.valid is expected_valid
    assert expected_warning in result.warnings
    if expected_error is None:
        assert result.errors == []
    else:
        assert expected_error in result.errors


@pytest.mark.parametrize(
    ("mutator", "expected_path"),
    [
        (
            lambda contract: contract["context_intake"].__setitem__("must_read_refs", ""),
            "context_intake.must_read_refs",
        ),
        (
            lambda contract: contract["references"][0].__setitem__("required_actions", ""),
            "references.0.required_actions",
        ),
        (
            lambda contract: contract["scope"].__setitem__("in_scope", ""),
            "scope.in_scope",
        ),
    ],
)
def test_parse_project_contract_data_salvage_normalizes_blank_string_list_corruption(
    mutator,
    expected_path: str,
) -> None:
    contract = _load_contract_fixture()
    mutator(contract)

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.blocking_errors == []
    assert any(expected_path in error and "must not be blank" in error for error in result.recoverable_errors)

    if expected_path == "context_intake.must_read_refs":
        assert result.contract.context_intake.must_read_refs == []
    elif expected_path == "references.0.required_actions":
        assert result.contract.references[0].required_actions == []
    else:
        assert result.contract.scope.in_scope == []


def test_parse_project_contract_data_salvage_preserves_valid_sibling_when_list_member_is_invalid() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", 7]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.context_intake.must_read_refs == ["ref-benchmark"]
    assert any("context_intake.must_read_refs.1" in error for error in result.recoverable_errors)


def test_parse_project_contract_data_salvage_preserves_nested_proof_list_siblings() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {"symbol": "alpha", "domain_or_type": "nonnegative real", "aliases": ["alpha", 7]},
        {"symbol": "beta", "domain_or_type": "nonnegative real", "aliases": ["beta"]},
    ]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert [parameter.symbol for parameter in result.contract.claims[0].parameters] == ["alpha", "beta"]
    assert result.contract.claims[0].parameters[0].aliases == ["alpha"]
    assert result.recoverable_errors == []
    assert result.blocking_errors == ["claims.0.parameters.0.aliases.1: Input should be a valid string"]


def test_validate_project_contract_rejects_coercive_reference_must_surface_scalar() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["must_surface"] = "yes"

    result = validate_project_contract(contract)

    assert result.valid is False
    assert result.errors == ["references.0.must_surface must be a boolean"]


def test_validate_project_contract_rejects_coercive_schema_version_scalar() -> None:
    contract = _load_contract_fixture()
    contract["schema_version"] = True

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "schema_version must be the integer 1" in result.errors


def test_validate_project_contract_stops_after_blocking_salvage_errors() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0].pop("statement")
    contract["references"] = []

    result = validate_project_contract(contract)

    assert result.valid is False
    assert result.errors == ["claims.0.statement is required"]
    assert result.warnings == []


def test_validate_project_contract_rejects_missing_schema_version() -> None:
    contract = _load_contract_fixture()
    contract.pop("schema_version")

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "schema_version is required" in result.errors


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
    contract = _load_contract_fixture()
    contract["scope"]["in_scope"] = []

    result = validate_project_contract(contract)

    assert result.valid is False
    assert "scope.in_scope must name at least one project boundary or objective" in result.errors


def test_validate_project_contract_rejects_reference_aliases_list_shape_drift_at_validation_boundary() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["aliases"] = "not-a-list"

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract)

    assert result.valid is True
    assert parsed.references[0].aliases == ["not-a-list"]
    assert "references.0.aliases must be a list, not str" in result.warnings


def test_validate_project_contract_rejects_nested_claim_reference_list_shape_drift() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["references"] = "ref-benchmark"

    result = validate_project_contract(contract)

    assert result.valid is True
    assert "claims.0.references must be a list, not str" in result.warnings


def test_validate_project_contract_rejects_extra_item_keys_without_dropping_semantic_counts() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["notes"] = "harmless"

    result = validate_project_contract(contract)

    assert result.valid is True
    assert "claims.0.notes: Extra inputs are not permitted" in result.warnings


def test_validate_project_contract_rejects_top_level_extra_keys() -> None:
    contract = _load_contract_fixture()
    contract["legacy_notes"] = "forwarded from a prior schema revision"

    result = validate_project_contract(contract)

    assert result.valid is True
    assert "legacy_notes: Extra inputs are not permitted" in result.warnings


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
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


def test_validate_project_contract_draft_mode_counts_concrete_must_read_ref_as_guidance() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark"]

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is True
    assert result.guidance_signal_count == 1
    assert "context_intake must not be empty" not in result.errors


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


def test_validate_project_contract_draft_mode_does_not_treat_background_must_read_ref_as_durable_guidance() -> None:
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

    result = validate_project_contract(contract, mode="draft")

    assert result.valid is False
    assert result.guidance_signal_count == 0
    assert "context_intake must not be empty" in result.errors


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


def test_validate_project_contract_revalidates_typed_research_contract_instances() -> None:
    contract = ResearchContract.model_validate(_load_contract_fixture())
    object.__setattr__(contract, "context_intake", "not-a-dict")

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert result.mode == "approved"
    assert result.warnings == []
    assert result.errors == ["context_intake must be an object, not str"]


def test_validate_project_contract_preserves_recoverable_warnings_when_normalization_fails() -> None:
    contract = _load_contract_fixture()
    contract.pop("context_intake")
    contract["legacy_notes"] = "forwarded from a prior schema revision"

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is False
    assert result.mode == "approved"
    assert "context_intake is required" in result.errors
    assert "legacy_notes: Extra inputs are not permitted" in result.warnings


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


@pytest.mark.parametrize(
    ("field_name", "expected_valid", "expected_warning", "expected_errors"),
    [
        ("context_intake", False, None, ["context_intake must be an object, not str"]),
        ("approach_policy", False, None, ["approach_policy must be an object, not str"]),
        ("uncertainty_markers", False, None, ["uncertainty_markers must be an object, not str"]),
    ],
)
@pytest.mark.parametrize("mode", ["draft", "approved"])
def test_validate_project_contract_rejects_wrong_type_for_singleton_sections(
    mode: str,
    field_name: str,
    expected_valid: bool,
    expected_warning: str | None,
    expected_errors: list[str],
) -> None:
    contract = _load_contract_fixture()
    contract[field_name] = "not-a-dict"

    result = validate_project_contract(contract, mode=mode)

    assert result.valid is expected_valid
    assert result.mode == mode
    if expected_warning is None:
        assert result.warnings == []
    else:
        assert expected_warning in result.warnings
    assert result.errors == expected_errors


def test_validate_project_contract_rejects_missing_uncertainty_marker_subfields() -> None:
    contract = _load_contract_fixture()
    contract["uncertainty_markers"] = {}

    result = validate_project_contract(contract)

    assert result.valid is False
    assert result.errors == [
        "uncertainty_markers.weakest_anchors is required",
        "uncertainty_markers.disconfirming_observations is required",
    ]


def test_contract_results_strict_mode_requires_explicit_uncertainty_markers() -> None:
    with pytest.raises(ValidationError, match="uncertainty_markers"):
        ContractResults.model_validate(normalize_contract_results_input({"claims": {}}))


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
        ContractResults.model_validate(normalize_contract_results_input(payload))

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
        ContractResults.model_validate(normalize_contract_results_input(payload))


def test_contract_results_strict_mode_rejects_proof_audit_without_explicit_completeness() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "proof_audit": {
                    "covered_hypothesis_ids": [],
                    "missing_hypothesis_ids": [],
                },
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(
        ValidationError,
        match=re.escape(
            "claims.claim-main.proof_audit.completeness must be explicit in contract-backed contract_results"
        ),
    ):
        ContractResults.model_validate(normalize_contract_results_input(payload))


def test_contract_results_strict_mode_rejects_noncanonical_proof_audit_reviewer() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "proof_audit": {
                    "completeness": "incomplete",
                    "reviewer": "someone-else",
                },
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(ValidationError, match=re.escape(f"reviewer must be {PROOF_AUDIT_REVIEWER}")):
        ContractResults.model_validate(normalize_contract_results_input(payload))


def test_contract_results_strict_mode_rejects_scalar_proof_audit_string_lists() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "proof_audit": {
                    "completeness": "incomplete",
                    "covered_parameter_symbols": "r_0",
                },
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(
        ValidationError,
        match=re.escape("claims.claim-main.proof_audit.covered_parameter_symbols must be a list, not str"),
    ):
        ContractResults.model_validate(normalize_contract_results_input(payload))


def test_contract_results_strict_mode_rejects_duplicate_linked_ids_and_actions() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "linked_ids": ["deliv-main", "deliv-main"],
            }
        },
        "references": {
            "ref-main": {
                "status": "completed",
                "completed_actions": ["Read", "read"],
                "missing_actions": [],
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(ValidationError) as excinfo:
        parse_contract_results_data_strict(payload)

    message = str(excinfo.value)
    assert "claims.claim-main.linked_ids" in message
    assert "references.ref-main.completed_actions.0 must use exact literal 'read'" in message
    assert "references.ref-main.completed_actions.1 is a duplicate" in message


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {
                "claims": {"claim-main": {"status": "failed"}},
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-main"],
                    "disconfirming_observations": ["observation-main"],
                },
            },
            "claims.claim-main.status=failed requires summary, notes, or evidence explaining the gap",
        ),
        (
            {
                "references": {
                    "ref-main": {
                        "status": "missing",
                        "missing_actions": ["cite"],
                    }
                },
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-main"],
                    "disconfirming_observations": ["observation-main"],
                },
            },
            "references.ref-main.status=missing requires summary or evidence explaining what is missing",
        ),
        (
            {
                "forbidden_proxies": {"fp-main": {"status": "unresolved"}},
                "uncertainty_markers": {
                    "weakest_anchors": ["anchor-main"],
                    "disconfirming_observations": ["observation-main"],
                },
            },
            "forbidden_proxies.fp-main.status=unresolved requires notes or evidence explaining the proxy issue",
        ),
    ],
)
def test_contract_results_strict_mode_rejects_underspecified_incomplete_statuses(
    payload: dict[str, object],
    expected_error: str,
) -> None:
    with pytest.raises(ValidationError, match=re.escape(expected_error)):
        ContractResults.model_validate(normalize_contract_results_input(payload))


def test_contract_results_strict_mode_rejects_proof_audit_blank_and_duplicate_list_members() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "proof_audit": {
                    "completeness": "incomplete",
                    "covered_parameter_symbols": ["r_0", " ", "r_0"],
                },
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(ValidationError) as excinfo:
        parse_contract_results_data_strict(payload)

    message = str(excinfo.value)
    assert "claims.claim-main.proof_audit.covered_parameter_symbols" in message
    assert "covered_parameter_symbols.1 must not be blank" in message
    assert "covered_parameter_symbols.2 is a duplicate" in message


def test_research_contract_rejects_string_required_in_proof_booleans() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {"symbol": "r_0", "domain_or_type": "nonnegative real", "required_in_proof": "yes"}
    ]
    contract["claims"][0]["hypotheses"] = [{"id": "hyp-r0", "text": "r_0 >= 0", "required_in_proof": "no"}]

    with pytest.raises(ValidationError) as excinfo:
        ResearchContract.model_validate(contract)

    message = str(excinfo.value)
    assert "claims.0.parameters.0.required_in_proof" in message
    assert "claims.0.hypotheses.0.required_in_proof" in message
    assert "must be a boolean" in message


def test_contract_results_strict_mode_rejects_string_stale_proof_audit_boolean() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "proof_audit": {
                    "completeness": "complete",
                    "reviewed_at": "2026-04-02T12:00:00Z",
                    "reviewer": "gpd-check-proof",
                    "proof_artifact_path": "derivations/theorem-proof.tex",
                    "proof_artifact_sha256": "0" * 64,
                    "audit_artifact_path": "01-01-PROOF-REDTEAM.md",
                    "audit_artifact_sha256": "1" * 64,
                    "claim_statement_sha256": "2" * 64,
                    "covered_hypothesis_ids": [],
                    "missing_hypothesis_ids": [],
                    "covered_parameter_symbols": [],
                    "missing_parameter_symbols": [],
                    "uncovered_quantifiers": [],
                    "uncovered_conclusion_clause_ids": [],
                    "quantifier_status": "matched",
                    "scope_status": "matched",
                    "counterexample_status": "none_found",
                    "stale": "yes",
                },
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    with pytest.raises(ValidationError) as excinfo:
        ContractResults.model_validate(normalize_contract_results_input(payload))

    message = str(excinfo.value)
    assert "claims.claim-main.proof_audit.stale" in message
    assert "must be a boolean" in message


def test_parse_contract_results_data_strict_matches_contract_results_model_validation() -> None:
    payload = {
        "claims": {
            "claim-main": {
                "status": "passed",
                "linked_ids": ["deliv-main"],
            }
        },
        "references": {
            "ref-main": {
                "status": "completed",
                "completed_actions": ["read", "compare"],
                "missing_actions": [],
            }
        },
        "uncertainty_markers": {
            "weakest_anchors": ["anchor-main"],
            "disconfirming_observations": ["observation-main"],
        },
    }

    parsed = parse_contract_results_data_strict(payload)
    baseline = ContractResults.model_validate(normalize_contract_results_input(payload))

    assert parsed.model_dump() == baseline.model_dump()


def test_parse_contract_results_data_strict_rejects_non_mapping_input() -> None:
    with pytest.raises(ValueError, match="contract_results must be an object"):
        parse_contract_results_data_strict("not-a-dict")


def test_plan_contract_schema_uses_supported_contract_enum_values() -> None:
    schema_text = (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")

    assert "kind: paper | dataset | prior_artifact | spec | user_anchor | other" in schema_text
    assert "role: definition | benchmark | method | must_consider | background | other" in schema_text
    assert (
        "kind: existence | schema | benchmark | consistency | cross_method | limiting_case | symmetry | dimensional_analysis | convergence | oracle | proxy | reproducibility | proof_hypothesis_coverage | proof_parameter_coverage | proof_quantifier_domain | claim_to_proof_alignment | lemma_dependency_closure | counterexample_search | human_review | other"
        in schema_text
    )
    assert (
        "relation: supports | computes | visualizes | benchmarks | depends_on | evaluated_by | proves | uses_hypothesis | depends_on_lemma | other"
        in schema_text
    )
    assert "prior_phase" not in schema_text
    assert "method_anchor" not in schema_text


def test_collect_plan_contract_integrity_errors_requires_proof_specific_acceptance_tests() -> None:
    contract = ResearchContract.model_validate(
        {
            "scope": {"question": "Prove the r_0 theorem"},
            "context_intake": {
                "must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"],
            },
            "observables": [
                {
                    "id": "obs-proof",
                    "name": "r_0 theorem obligation",
                    "kind": "proof_obligation",
                    "definition": "Prove the theorem for all r_0 >= 0 and x > 0",
                }
            ],
            "claims": [
                {
                    "id": "claim-proof",
                    "statement": "For all x > 0 and r_0 >= 0, F(x, r_0) >= 0.",
                    "claim_kind": "theorem",
                    "observables": ["obs-proof"],
                    "deliverables": ["deliv-proof"],
                    "acceptance_tests": ["test-existence"],
                    "parameters": [{"symbol": "r_0", "domain_or_type": "nonnegative real"}],
                    "hypotheses": [{"id": "hyp-r0", "text": "r_0 >= 0", "symbols": ["r_0"]}],
                    "conclusion_clauses": [{"id": "concl-main", "text": "F(x, r_0) >= 0"}],
                    "proof_deliverables": ["deliv-proof"],
                }
            ],
            "deliverables": [
                {
                    "id": "deliv-proof",
                    "kind": "derivation",
                    "path": "derivations/theorem-proof.tex",
                    "description": "Detailed proof artifact",
                }
            ],
            "acceptance_tests": [
                {
                    "id": "test-existence",
                    "subject": "claim-proof",
                    "kind": "existence",
                    "procedure": "Check that the proof file exists",
                    "pass_condition": "The proof file is present",
                }
            ],
            "forbidden_proxies": [
                {
                    "id": "fp-proof",
                    "subject": "claim-proof",
                    "proxy": "Numerical spot checks instead of a proof",
                    "reason": "Would miss dropped parameters or assumptions",
                }
            ],
            "uncertainty_markers": {
                "weakest_anchors": ["The proof audit still needs full coverage"],
                "disconfirming_observations": ["A counterexample at r_0 > 0 invalidates the theorem"],
            },
        }
    )

    errors = collect_plan_contract_integrity_errors(contract)

    assert "claim claim-proof missing proof-specific acceptance_tests" in errors


def test_collect_plan_contract_integrity_errors_requires_theorem_inventory_for_proof_bearing_claims() -> None:
    contract = ResearchContract.model_validate(
        {
            "scope": {"question": "Can the theorem be proved as stated?"},
            "context_intake": {"must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"]},
            "observables": [
                {
                    "id": "obs-proof",
                    "name": "proof obligation",
                    "kind": "proof_obligation",
                    "definition": "Prove the theorem for every named parameter",
                }
            ],
            "claims": [
                {
                    "id": "claim-proof",
                    "statement": "For all r_0 >= 0, F(r_0) >= 0.",
                    "claim_kind": "theorem",
                    "observables": ["obs-proof"],
                    "deliverables": ["deliv-proof"],
                    "acceptance_tests": ["test-proof-align"],
                    "proof_deliverables": ["deliv-proof"],
                }
            ],
            "deliverables": [
                {
                    "id": "deliv-proof",
                    "kind": "derivation",
                    "path": "derivations/theorem-proof.tex",
                    "description": "Detailed theorem proof",
                }
            ],
            "acceptance_tests": [
                {
                    "id": "test-proof-align",
                    "subject": "claim-proof",
                    "kind": "claim_to_proof_alignment",
                    "procedure": "Audit the theorem against the proof",
                    "pass_condition": "No theorem parameter or hypothesis is silently dropped",
                }
            ],
            "forbidden_proxies": [
                {
                    "id": "fp-proof",
                    "subject": "claim-proof",
                    "proxy": "Centered subcase only",
                    "reason": "Would silently specialize away r_0",
                }
            ],
            "uncertainty_markers": {
                "weakest_anchors": ["The theorem inventory is still incomplete."],
                "disconfirming_observations": ["A proof that drops r_0 invalidates the claim."],
            },
        }
    )

    errors = collect_plan_contract_integrity_errors(contract)

    assert "claim claim-proof missing parameters for proof-bearing claim" in errors
    assert "claim claim-proof missing hypotheses for proof-bearing claim" in errors
    assert "claim claim-proof missing conclusion_clauses for proof-bearing claim" in errors


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        ("context_intake.must_include_prior_outputs", ["TBD"]),
        ("context_intake.must_include_prior_outputs", ["./RESULTS.md"]),
        ("context_intake.user_asserted_anchors", ["Nature benchmark"]),
        ("context_intake.known_good_baselines", ["Science benchmark"]),
        ("context_intake.crucial_inputs", ["Check the user's finite-volume cutoff choice before proceeding"]),
        (
            "approach_policy.stop_and_rethink_conditions",
            ["Benchmark normalization shifts outside tolerance"],
        ),
    ],
)
def test_collect_plan_contract_integrity_errors_requires_concrete_grounding_not_carry_forward_fields(
    field_path: str,
    value: list[str],
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = []
    section_name, nested_field_name = field_path.split(".", 1)
    if section_name == "context_intake":
        contract[section_name][nested_field_name] = value
    else:
        contract[section_name] = {nested_field_name: value}

    errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract))

    assert "missing references or explicit grounding context" in errors


@pytest.mark.parametrize("locator", [
    "TBD",
    "Section 4",
    "12345",
    "data/1304.4926",
    "1334.4926",
    "1300.4926",
    "hep-th/0600123",
    "hep-th/0613123",
    "data/2401001",
    "results/0612001",
    "output/0301001",
    "logs/0501001",
])
def test_collect_plan_contract_integrity_errors_rejects_placeholder_must_surface_reference_locators(
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
            "why_it_matters": "Placeholder locator should not satisfy the hard anchor requirement.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read"],
        }
    ]
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract))

    assert "references must include at least one must_surface=true anchor" in errors


@pytest.mark.parametrize(
    ("reference_kind", "locator"),
    [
        ("paper", "Author et al., Journal, 2024"),
        ("other", "Einstein, Annalen der Physik, 1905"),
        ("spec", "https://example.org/missing-data-benchmark.csv"),
        ("paper", "1304.4926"),
        ("paper", "1905.08255v2"),
        ("paper", "hep-th/0603001"),
        ("paper", "gr-qc/9711053v1"),
        ("paper", "math.DG/0211159"),
        ("paper", "cs.SE/0303020"),
        ("paper", "q-bio.PE/0501001"),
        ("paper", "hep-th/0601001"),
        ("paper", "hep-th/0612001"),
        ("paper", "math/0301234"),
        ("paper", "physics/0601001"),
        ("paper", "cs/0303020"),
        ("paper", "nlin/0101001"),
        ("paper", "stat/0501001"),
        ("paper", "10.1103/PhysRevD.100.026003"),
        ("paper", "10.1007/JHEP12(2020)155"),
    ],
)
def test_collect_plan_contract_integrity_errors_accepts_concrete_must_surface_reference_locator(
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
            "role": "benchmark",
            "why_it_matters": "Concrete locator should satisfy the hard anchor requirement.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract))

    assert errors == []


def test_collect_plan_contract_integrity_errors_rejects_rootless_project_local_must_surface_reference_locator() -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "prior_artifact",
            "locator": "GPD/phases/03-missing-energy/03-01-SUMMARY.md",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Local artifacts should not count as anchors until resolved against a project root.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract))

    assert "references must include at least one must_surface=true anchor" in errors


def test_collect_plan_contract_integrity_errors_accepts_project_local_must_surface_reference_locator_with_project_root(
    tmp_path: Path,
) -> None:
    contract = _load_contract_fixture()
    _remove_incidental_grounding(contract)
    artifact = tmp_path / "GPD" / "phases" / "03-missing-energy" / "03-01-SUMMARY.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("summary", encoding="utf-8")
    contract["references"] = [
        {
            "id": "ref-anchor",
            "kind": "prior_artifact",
            "locator": "GPD/phases/03-missing-energy/03-01-SUMMARY.md",
            "aliases": [],
            "role": "benchmark",
            "why_it_matters": "Resolved local artifact should satisfy the hard anchor requirement.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    errors = collect_plan_contract_integrity_errors(
        ResearchContract.model_validate(contract),
        project_root=tmp_path,
    )

    assert errors == []


def test_collect_plan_contract_integrity_errors_accepts_non_reference_grounding_without_must_surface_anchor(
    tmp_path: Path,
) -> None:
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
            "must_surface": False,
        }
    ]
    contract["context_intake"]["must_include_prior_outputs"] = ["GPD/phases/01-setup/01-01-SUMMARY.md"]
    prior_output = contract["context_intake"]["must_include_prior_outputs"][0]
    grounded_output = tmp_path / prior_output
    grounded_output.parent.mkdir(parents=True, exist_ok=True)
    grounded_output.write_text("summary\n", encoding="utf-8")

    result = validate_project_contract(contract, mode="approved", project_root=tmp_path)
    errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract), project_root=tmp_path)

    assert result.valid is True
    assert any("must_surface=true anchor" in warning for warning in result.warnings)
    assert errors == []


@pytest.mark.parametrize(
    ("reference_kind", "locator"),
    [
        ("paper", "Author et al., Journal, 2024"),
        ("other", "Einstein, Annalen der Physik, 1905"),
        ("paper", "hep-th/0603001"),
        ("paper", "10.1103/PhysRevD.100.026003"),
        ("paper", "math/0301234"),
    ],
)
def test_validate_project_contract_approved_mode_accepts_concrete_must_surface_reference_locator(
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
            "role": "benchmark",
            "why_it_matters": "Concrete locator should satisfy the hard anchor requirement.",
            "applies_to": ["claim-benchmark"],
            "carry_forward_to": [],
            "must_surface": True,
            "required_actions": ["read", "compare"],
        }
    ]
    contract["scope"]["unresolved_questions"] = []
    contract["context_intake"]["must_read_refs"] = ["ref-anchor"]

    result = validate_project_contract(contract, mode="approved")

    assert result.valid is True
    assert result.mode == "approved"


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


def test_research_contract_accepts_structured_theorem_claim_fields() -> None:
    contract = {
        "scope": {"question": "Prove the full r_0 theorem without silently dropping parameters"},
        "context_intake": {
            "must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"],
        },
        "observables": [
            {
                "id": "obs-proof",
                "name": "Theorem proof obligation",
                "kind": "proof_obligation",
                "definition": "Establish the theorem for all r_0 >= 0 and x > 0",
            }
        ],
        "claims": [
            {
                "id": "claim-proof",
                "statement": "For all x > 0 and r_0 >= 0, F(x, r_0) >= 0.",
                "claim_kind": "theorem",
                "observables": ["obs-proof"],
                "deliverables": ["deliv-proof"],
                "acceptance_tests": ["test-proof-alignment", "test-counterexample"],
                "parameters": [
                    {"symbol": "r_0", "domain_or_type": "nonnegative real", "aliases": ["r0"]},
                    {"symbol": "x", "domain_or_type": "positive real"},
                ],
                "hypotheses": [
                    {"id": "hyp-r0", "text": "r_0 >= 0", "symbols": ["r_0"]},
                    {"id": "hyp-x", "text": "x > 0", "symbols": ["x"]},
                ],
                "quantifiers": ["for all x > 0", "for all r_0 >= 0"],
                "conclusion_clauses": [{"id": "concl-main", "text": "F(x, r_0) >= 0"}],
                "proof_deliverables": ["deliv-proof"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-proof",
                "kind": "derivation",
                "path": "derivations/theorem-proof.tex",
                "description": "Detailed theorem proof artifact",
            }
        ],
        "acceptance_tests": [
            {
                "id": "test-proof-alignment",
                "subject": "claim-proof",
                "kind": "claim_to_proof_alignment",
                "procedure": "Red-team the theorem statement against the proof body",
                "pass_condition": "Every hypothesis, parameter, and conclusion clause is accounted for",
            },
            {
                "id": "test-counterexample",
                "subject": "claim-proof",
                "kind": "counterexample_search",
                "procedure": "Search for counterexamples over the stated parameter regime",
                "pass_condition": "No counterexample is found over the stated domain",
            },
        ],
        "forbidden_proxies": [
            {
                "id": "fp-proof",
                "subject": "claim-proof",
                "proxy": "Proving only the r_0 = 0 subcase and claiming the full theorem",
                "reason": "Would silently drop a named theorem parameter",
            }
        ],
        "links": [
            {
                "id": "link-proof",
                "source": "deliv-proof",
                "target": "claim-proof",
                "relation": "proves",
                "verified_by": ["test-proof-alignment"],
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["Counterexample search coverage is only as strong as the explored regime"],
            "disconfirming_observations": ["A valid counterexample at r_0 > 0 invalidates the theorem"],
        },
    }

    parsed = ResearchContract.model_validate(contract)

    assert parsed.claims[0].claim_kind == "theorem"
    assert parsed.claims[0].parameters[0].symbol == "r_0"
    assert parsed.claims[0].hypotheses[0].id == "hyp-r0"
    assert parsed.acceptance_tests[0].kind == "claim_to_proof_alignment"
    assert parsed.links[0].relation == "proves"


@pytest.mark.parametrize("schema_name", ("project-contract-schema.md", "state-json-schema.md"))
def test_project_contract_schema_examples_are_validator_compatible(schema_name: str) -> None:
    schema_text = (TEMPLATES_DIR / schema_name).read_text(encoding="utf-8")
    match = re.search(r"##+ `project_contract`\n\n```json\n(.*?)\n```", schema_text, re.DOTALL)

    assert match is not None
    contract = json.loads(match.group(1))

    parsed = ResearchContract.model_validate(contract)
    result = validate_project_contract(contract, mode="approved")

    assert parsed.scope.question == "What benchmark must the project recover?"
    assert result.valid is True
