"""Fast contract-validation stability regressions."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from gpd.contracts import ResearchContract, collect_plan_contract_integrity_errors, parse_project_contract_data_strict
from gpd.core.contract_validation import parse_project_contract_data_salvage, validate_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates"


def _load_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _strip_reference_dependencies(contract: dict[str, object]) -> None:
    contract["references"] = []
    contract["context_intake"]["must_read_refs"] = []
    for claim in contract["claims"]:
        claim["references"] = []
    for acceptance_test in contract["acceptance_tests"]:
        acceptance_test["evidence_required"] = [
            evidence_id
            for evidence_id in acceptance_test["evidence_required"]
            if not str(evidence_id).startswith("ref-")
        ]


def test_fast_contract_validation_salvage_normalizes_literal_case_drift() -> None:
    contract = _load_contract_fixture()
    contract["references"][0]["role"] = "Benchmark"
    contract["references"][0]["required_actions"] = ["Read", "Compare"]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.references[0].role == "benchmark"
    assert result.contract.references[0].required_actions == ["read", "compare"]
    assert "references.0.role must use exact canonical value: benchmark" in result.recoverable_errors
    assert "references.0.required_actions.0 must use exact canonical value: read" in result.recoverable_errors


def test_fast_contract_validation_salvage_normalizes_link_relation_case_drift() -> None:
    contract = _load_contract_fixture()
    contract["links"][0]["relation"] = "Supports"

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.links[0].relation == "supports"
    assert "links.0.relation must use exact canonical value: supports" in result.recoverable_errors


def test_fast_contract_validation_salvage_normalizes_blank_list_members_without_losing_siblings() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", " "]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.context_intake.must_read_refs == ["ref-benchmark"]
    assert any(
        "context_intake.must_read_refs.1" in error and "must not be blank" in error
        for error in result.recoverable_errors
    )


def test_fast_contract_validation_salvage_surfaces_blank_list_normalization_finding() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = " "

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.context_intake.must_read_refs == []
    assert "context_intake.must_read_refs was normalized from blank string to empty list" in result.recoverable_errors


def test_fast_contract_validation_strict_rejects_blank_string_list_field_without_salvage() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = " "

    result = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "context_intake.must_read_refs must not be blank" in result.blocking_errors
    assert result.recoverable_errors == []


def test_fast_contract_validation_salvage_reports_missing_schema_version_directly() -> None:
    contract = _load_contract_fixture()
    del contract["schema_version"]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is None
    assert result.blocking_errors == ["schema_version is required"]
    assert result.recoverable_errors == []


def test_fast_contract_validation_salvage_reports_non_integer_schema_versions_directly() -> None:
    for schema_version in ("1", 1.0, True):
        contract = _load_contract_fixture()
        contract["schema_version"] = schema_version

        result = parse_project_contract_data_salvage(contract)

        assert result.contract is not None
        assert result.blocking_errors == ["schema_version must be the integer 1"]
        assert result.recoverable_errors == []


def test_fast_contract_validation_salvage_reports_wrong_integer_schema_version_directly() -> None:
    contract = _load_contract_fixture()
    contract["schema_version"] = 2

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.blocking_errors == ["schema_version: Input should be 1"]
    assert result.recoverable_errors == []


def test_fast_contract_validation_strict_rejects_nonblank_mapping_string_list_field_without_salvage() -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = {}
    contract["approach_policy"]["allowed_fit_families"] = "power-law"

    result = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "approach_policy.allowed_fit_families must be a list, not str" in result.blocking_errors
    assert result.recoverable_errors == []


def test_fast_contract_validation_strict_rejects_top_level_scalar_string_list_field_without_salvage() -> None:
    contract = _load_contract_fixture()
    contract["references"] = "ref-benchmark"

    result = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "references must be a list, not str" in result.blocking_errors
    assert result.recoverable_errors == []


def test_fast_contract_validation_salvage_preserves_top_level_scalar_string_list_field_as_blocking() -> None:
    contract = _load_contract_fixture()
    contract["references"] = "ref-benchmark"

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.references == []
    assert "references must be a list, not str" in result.blocking_errors
    assert result.recoverable_errors == []


def test_fast_contract_validation_strict_rejects_nested_collection_string_list_field_without_salvage() -> None:
    contract = _load_contract_fixture()
    contract["deliverables"][0]["must_contain"] = "caption"

    result = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "deliverables.0.must_contain must be a list, not str" in result.blocking_errors
    assert result.recoverable_errors == []


def test_fast_contract_validation_salvage_surfaces_nested_scalar_string_list_field_as_recoverable() -> None:
    contract = _load_contract_fixture()
    contract["deliverables"][0]["must_contain"] = "caption"

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.blocking_errors == []
    assert "deliverables.0.must_contain must be a list, not str" in result.recoverable_errors


def test_fast_contract_validation_salvage_is_stable_and_does_not_mutate_authored_input() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", " "]
    contract["references"][0]["role"] = "Benchmark"
    original = deepcopy(contract)

    first = parse_project_contract_data_salvage(contract)
    second = parse_project_contract_data_salvage(contract)

    assert contract == original
    assert first.contract is not None
    assert second.contract is not None
    assert first.contract.model_dump(mode="json") == second.contract.model_dump(mode="json")
    assert first.blocking_errors == second.blocking_errors
    assert first.recoverable_errors == second.recoverable_errors


def test_fast_contract_validation_strict_is_stable_and_does_not_mutate_authored_input() -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = {"allowed_fit_families": "power-law"}
    original = deepcopy(contract)

    first = parse_project_contract_data_strict(contract)
    second = parse_project_contract_data_strict(contract)

    assert contract == original
    assert first.contract is None
    assert second.contract is None
    assert first.blocking_errors == second.blocking_errors
    assert first.recoverable_errors == second.recoverable_errors == []


def test_fast_contract_validation_strict_rejects_exact_literal_case_drift_without_salvage() -> None:
    contract = _load_contract_fixture()
    contract["observables"][0]["kind"] = "Scalar"
    contract["acceptance_tests"][0]["automation"] = "Automated"

    result = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert "observables.0.kind must use exact canonical value: scalar" in result.blocking_errors
    assert "acceptance_tests.0.automation must use exact canonical value: automated" in result.blocking_errors
    assert result.recoverable_errors == []


def test_fast_contract_validation_salvage_isolates_blank_string_list_field_recovery() -> None:
    contract = _load_contract_fixture()
    contract["context_intake"]["must_read_refs"] = " "
    contract["context_intake"]["must_include_prior_outputs"] = ["phase-01-summary"]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.context_intake.must_read_refs == []
    assert result.contract.context_intake.must_include_prior_outputs == ["phase-01-summary"]
    assert result.blocking_errors == []
    assert result.recoverable_errors == [
        "context_intake.must_read_refs was normalized from blank string to empty list",
        "context_intake.must_read_refs must not be blank",
    ]


def test_fast_contract_validation_salvage_normalizes_blank_nested_proof_lists() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [{"symbol": "alpha", "aliases": ""}]
    contract["claims"][0]["hypotheses"] = [{"id": "hyp-alpha", "text": "alpha >= 0", "symbols": ""}]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.claims[0].parameters[0].aliases == []
    assert result.contract.claims[0].hypotheses[0].symbols == []
    assert "claims.0.parameters.0.aliases was normalized from blank string to empty list" in result.recoverable_errors
    assert "claims.0.hypotheses.0.symbols was normalized from blank string to empty list" in result.recoverable_errors
    assert result.blocking_errors == []


def test_fast_contract_validation_salvage_reports_unknown_approach_policy_key() -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = {"legacy_guardrail": ["do not use proxy fit"]}

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.approach_policy.model_dump() == {
        "formulations": [],
        "allowed_estimator_families": [],
        "forbidden_estimator_families": [],
        "allowed_fit_families": [],
        "forbidden_fit_families": [],
        "stop_and_rethink_conditions": [],
    }
    assert any(
        error.startswith("approach_policy.legacy_guardrail: Extra inputs are not permitted")
        for error in result.recoverable_errors
    )


def test_fast_contract_validation_strict_rejects_unknown_approach_policy_key() -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = {"legacy_guardrail": ["do not use proxy fit"]}

    result = parse_project_contract_data_strict(contract)

    assert result.contract is None
    assert any(
        error.startswith("approach_policy.legacy_guardrail: Extra inputs are not permitted")
        for error in result.blocking_errors
    )


def test_fast_contract_validation_salvage_reports_invalid_approach_policy_member_drop() -> None:
    contract = _load_contract_fixture()
    contract["approach_policy"] = {
        "formulations": [7],
        "allowed_fit_families": ["benchmark-fit"],
    }

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.approach_policy.formulations == []
    assert result.contract.approach_policy.allowed_fit_families == ["benchmark-fit"]
    assert "approach_policy.formulations.0: Input should be a valid string" in result.recoverable_errors


def test_fast_contract_validation_salvage_preserves_nested_collection_siblings() -> None:
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


def test_fast_contract_validation_nested_optional_proof_field_truncation_is_blocking() -> None:
    contract = _load_contract_fixture()
    contract["claims"][0]["parameters"] = [
        {"symbol": "alpha", "domain_or_type": ["nonnegative real"], "aliases": ["alpha"]},
    ]

    result = parse_project_contract_data_salvage(contract)

    assert result.contract is not None
    assert result.contract.claims[0].parameters[0].domain_or_type is None
    assert result.recoverable_errors == []
    assert result.blocking_errors == ["claims.0.parameters.0.domain_or_type: Input should be a valid string"]


def test_fast_contract_validation_strict_entrypoint_rejects_missing_context_intake() -> None:
    contract = _load_contract_fixture()
    del contract["context_intake"]

    validation = validate_project_contract(contract, mode="approved")

    assert validation.valid is False
    assert "context_intake is required" in validation.errors


def test_fast_contract_validation_rootless_path_like_anchor_does_not_count_as_approved_grounding() -> None:
    contract = _load_contract_fixture()
    _strip_reference_dependencies(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = ["GPD/phases/01-setup/01-01-SUMMARY.md"]
    contract["context_intake"]["known_good_baselines"] = []

    validation = validate_project_contract(contract, mode="approved")
    integrity_errors = collect_plan_contract_integrity_errors(ResearchContract.model_validate(contract))

    assert validation.valid is False
    assert (
        "approved project contract requires at least one concrete anchor/reference/prior-output/baseline; "
        "explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own"
        in validation.errors
    )
    assert (
        "context_intake.user_asserted_anchors entry requires a resolved project_root to verify artifact grounding: "
        "GPD/phases/01-setup/01-01-SUMMARY.md" in validation.warnings
    )
    assert "missing references or explicit grounding context" in integrity_errors


def test_fast_contract_validation_accepts_existing_project_local_baseline_with_project_root(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    _strip_reference_dependencies(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = ["GPD/phases/01-setup/01-01-SUMMARY.md"]

    grounded_artifact = tmp_path / "GPD" / "phases" / "01-setup" / "01-01-SUMMARY.md"
    grounded_artifact.parent.mkdir(parents=True, exist_ok=True)
    grounded_artifact.write_text("summary\n", encoding="utf-8")

    validation = validate_project_contract(contract, mode="approved", project_root=tmp_path)
    integrity_errors = collect_plan_contract_integrity_errors(
        ResearchContract.model_validate(contract),
        project_root=tmp_path,
    )

    assert validation.valid is True
    assert not any("known_good_baselines" in warning for warning in validation.warnings)
    assert "missing references or explicit grounding context" not in integrity_errors


def test_fast_contract_validation_rootless_prior_output_does_not_count_as_approved_grounding() -> None:
    contract = _load_contract_fixture()
    _strip_reference_dependencies(contract)
    contract["context_intake"]["must_include_prior_outputs"] = ["./RESULTS.md"]
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []

    validation = validate_project_contract(contract, mode="approved")

    assert validation.valid is False
    assert (
        "approved project contract requires at least one concrete anchor/reference/prior-output/baseline; "
        "explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own"
        in validation.errors
    )


def test_fast_contract_validation_context_gaps_and_crucial_inputs_do_not_satisfy_hard_grounding() -> None:
    contract = _load_contract_fixture()
    _strip_reference_dependencies(contract)
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []
    contract["context_intake"]["context_gaps"] = ["Need decisive anchor selection before approval"]
    contract["context_intake"]["crucial_inputs"] = ["Use benchmark table from the confirmed paper once selected"]

    validation = validate_project_contract(contract, mode="approved")

    assert validation.valid is False
    assert any("approved project contract requires at least one concrete anchor" in error for error in validation.errors)


def test_fast_contract_validation_accepts_existing_project_local_prior_output_with_project_root(tmp_path: Path) -> None:
    contract = _load_contract_fixture()
    _strip_reference_dependencies(contract)
    contract["context_intake"]["must_include_prior_outputs"] = ["./RESULTS.md"]
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []
    (tmp_path / "RESULTS.md").write_text("result\n", encoding="utf-8")

    validation = validate_project_contract(contract, mode="approved", project_root=tmp_path)

    assert validation.valid is True
    assert not any("must_include_prior_outputs" in warning for warning in validation.warnings)


def test_fast_contract_validation_schema_docs_describe_recoverable_vs_strict_repair_behavior() -> None:
    project_schema = (TEMPLATES_DIR / "project-contract-schema.md").read_text(encoding="utf-8")
    plan_schema = (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")

    assert "Salvage/repair flows may drop unknown keys while surfacing recoverable findings" in project_schema
    assert (
        "Salvage/repair may normalize some list-shape drift, blank items, or case drift with explicit findings"
        in project_schema
    )
    assert "Salvage/repair flows may drop unknown keys while surfacing recoverable findings" in plan_schema
    assert "preserve uncertainty and workflow visibility, but they do not satisfy hard grounding on their own" in plan_schema
