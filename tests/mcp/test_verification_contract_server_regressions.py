from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_project_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _derived_template_contract() -> dict[str, object]:
    contract = copy.deepcopy(_load_project_contract_fixture())
    contract["observables"][0]["regime"] = "large-k"
    contract["approach_policy"] = {
        "allowed_fit_families": ["power_law"],
        "forbidden_fit_families": ["polynomial"],
        "allowed_estimator_families": ["bootstrap"],
        "forbidden_estimator_families": ["jackknife"],
    }
    contract["acceptance_tests"].extend(
        [
            {
                "id": "test-limit",
                "subject": "claim-benchmark",
                "kind": "limiting_case",
                "procedure": "Evaluate the large-k limit against the asymptotic target.",
                "pass_condition": "Recovers the contracted large-k scaling",
                "evidence_required": ["deliv-figure"],
                "automation": "automated",
            },
            {
                "id": "test-fit",
                "subject": "claim-benchmark",
                "kind": "other",
                "procedure": "Compare fit residuals across the approved ansatz families.",
                "pass_condition": "Selected fit stays inside the allowed family",
                "evidence_required": ["deliv-figure"],
                "automation": "hybrid",
            },
            {
                "id": "test-estimator",
                "subject": "claim-benchmark",
                "kind": "other",
                "procedure": "Bootstrap estimator diagnostics must resolve bias and variance.",
                "pass_condition": "Bootstrap estimator remains calibrated",
                "evidence_required": ["deliv-figure"],
                "automation": "hybrid",
            },
        ]
    )
    return contract


def _assert_contract_tools_reject(contract: dict[str, object], expected_error: str) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    suggest_result = suggest_contract_checks(contract)

    expected = {"error": f"Invalid contract payload: {expected_error}", "schema_version": 1}
    assert run_result == expected
    assert suggest_result == expected


@pytest.mark.parametrize(
    ("schema_version", "expected_error"),
    [
        (2, "Invalid contract payload: schema_version must be 1"),
        ("1", "Invalid contract payload: schema_version must be the integer 1"),
        (True, "Invalid contract payload: schema_version must be the integer 1"),
    ],
)
def test_contract_tools_reject_invalid_schema_versions(schema_version: object, expected_error: str) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["schema_version"] = schema_version
    contract["context_intake"] = "not-a-dict"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    suggest_result = suggest_contract_checks(contract)

    assert run_result == {"error": expected_error, "schema_version": 1}
    assert suggest_result == {"error": expected_error, "schema_version": 1}


def test_contract_tools_reject_coercive_contract_scalars() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["must_surface"] = "yes"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    suggest_result = suggest_contract_checks(contract)

    expected = {
        "error": "Invalid contract payload: references.0.must_surface must be a boolean",
        "schema_version": 1,
    }
    assert run_result == expected
    assert suggest_result == expected


def test_suggest_contract_checks_derives_request_templates_from_contract() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_derived_template_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    benchmark = checks["contract.benchmark_reproduction"]["request_template"]
    assert benchmark["binding"]["claim_ids"] == ["claim-benchmark"]
    assert benchmark["binding"]["acceptance_test_ids"] == ["test-benchmark"]
    assert benchmark["binding"]["reference_ids"] == ["ref-benchmark"]
    assert benchmark["metadata"]["source_reference_id"] == "ref-benchmark"

    limit = checks["contract.limit_recovery"]["request_template"]
    assert limit["binding"]["claim_ids"] == ["claim-benchmark"]
    assert limit["binding"]["acceptance_test_ids"] == ["test-limit"]
    assert limit["binding"]["observable_ids"] == ["obs-benchmark"]
    assert limit["metadata"]["regime_label"] == "large-k"
    assert limit["metadata"]["expected_behavior"] == "Recovers the contracted large-k scaling"

    direct_proxy = checks["contract.direct_proxy_consistency"]["request_template"]
    assert direct_proxy["binding"]["claim_ids"] == ["claim-benchmark"]
    assert direct_proxy["binding"]["forbidden_proxy_ids"] == ["fp-01"]

    fit = checks["contract.fit_family_mismatch"]["request_template"]
    assert fit["binding"]["claim_ids"] == ["claim-benchmark"]
    assert fit["binding"]["acceptance_test_ids"] == ["test-fit"]
    assert fit["binding"]["observable_ids"] == ["obs-benchmark"]
    assert fit["metadata"]["declared_family"] == "power_law"
    assert fit["metadata"]["allowed_families"] == ["power_law"]
    assert fit["metadata"]["forbidden_families"] == ["polynomial"]

    estimator = checks["contract.estimator_family_mismatch"]["request_template"]
    assert estimator["binding"]["claim_ids"] == ["claim-benchmark"]
    assert estimator["binding"]["acceptance_test_ids"] == ["test-estimator"]
    assert estimator["binding"]["observable_ids"] == ["obs-benchmark"]
    assert estimator["metadata"]["declared_family"] == "bootstrap"
    assert estimator["metadata"]["allowed_families"] == ["bootstrap"]
    assert estimator["metadata"]["forbidden_families"] == ["jackknife"]
    assert checks["contract.benchmark_reproduction"]["supported_binding_fields"] == [
        "binding.claim_id",
        "binding.claim_ids",
        "binding.deliverable_id",
        "binding.deliverable_ids",
        "binding.acceptance_test_id",
        "binding.acceptance_test_ids",
        "binding.reference_id",
        "binding.reference_ids",
    ]


def test_suggest_contract_checks_surfaces_salvage_warnings() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"

    result = suggest_contract_checks(contract)

    assert "error" not in result
    assert result["contract_salvaged"] is True
    assert result["contract_salvage_findings"] == ["references.0.notes: Extra inputs are not permitted"]
    assert any("salvaged before check suggestion" in warning for warning in result["contract_warnings"])
    assert any(entry["check_key"] == "contract.benchmark_reproduction" for entry in result["suggested_checks"])


@pytest.mark.parametrize("payload", ["not-a-dict", ["claim-benchmark"], 3])
def test_suggest_contract_checks_rejects_non_mapping_payloads(payload: object) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(payload)  # type: ignore[arg-type]

    assert result == {"error": "contract must be an object", "schema_version": 1}


@pytest.mark.parametrize("active_checks", ["5.16", 5, {"5.16": True}])
def test_suggest_contract_checks_rejects_non_list_active_checks(active_checks: object) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_derived_template_contract(), active_checks=active_checks)  # type: ignore[arg-type]

    assert result == {"error": "active_checks must be a list of strings", "schema_version": 1}


@pytest.mark.parametrize("payload", ["not-a-dict", ["claim-benchmark"], 3])
def test_run_contract_check_rejects_non_mapping_payloads(payload: object) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(payload)  # type: ignore[arg-type]

    assert result == {"error": "request must be an object", "schema_version": 1}


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": ["claim-benchmark", None]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "binding.claim_ids[1] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"reference_ids": ["ref-benchmark", "   "]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "binding.reference_ids[1] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"allowed_families": ["power_law", 5]},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            "metadata.allowed_families[1] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.estimator_family_mismatch",
                "metadata": {"forbidden_families": ["", "jackknife"]},
                "observed": {
                    "selected_family": "bootstrap",
                    "bias_checked": True,
                    "calibration_checked": True,
                },
            },
            "metadata.forbidden_families[0] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": {"primary": "claim-benchmark"}},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "binding.claim_ids must be a string or list of strings",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"allowed_families": "power_law"},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            "metadata.allowed_families must be a list of strings",
        ),
    ],
)
def test_run_contract_check_rejects_malformed_binding_and_metadata_list_members(
    request_payload: dict[str, object], expected_error: str
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(request_payload)

    assert result == {"error": expected_error, "schema_version": 1}


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": True, "threshold_value": 0.02},
            },
            "observed.metric_value must be a number",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": False},
            },
            "observed.threshold_value must be a number",
        ),
        (
            {
                "check_key": "contract.direct_proxy_consistency",
                "observed": {"proxy_only": "true"},
            },
            "observed.proxy_only must be a boolean",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "power_law"},
                "observed": {"selected_family": "power_law", "competing_family_checked": "false"},
            },
            "observed.competing_family_checked must be a boolean",
        ),
        (
            {
                "check_key": "contract.estimator_family_mismatch",
                "metadata": {"declared_family": "bootstrap"},
                "observed": {
                    "selected_family": "bootstrap",
                    "bias_checked": "true",
                    "calibration_checked": True,
                },
            },
            "observed.bias_checked must be a boolean",
        ),
    ],
)
def test_run_contract_check_rejects_coercive_numeric_and_boolean_fields(
    request_payload: dict[str, object],
    expected_error: str,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(request_payload)

    assert result == {"error": expected_error, "schema_version": 1}


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.limit_recovery",
                "metadata": {"expected_behavior": 5},
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            },
            "metadata.expected_behavior must be a string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": 5},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "metadata.source_reference_id must be a string",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": 5},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            "metadata.declared_family must be a string",
        ),
        (
            {
                "check_key": "contract.limit_recovery",
                "metadata": {"regime_label": "large-k", "expected_behavior": "matches"},
                "observed": {"limit_passed": True, "observed_limit": 9},
            },
            "observed.observed_limit must be a string",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "power_law"},
                "observed": {"selected_family": 9, "competing_family_checked": True},
            },
            "observed.selected_family must be a string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
                "artifact_content": {"text": "benchmark"},
            },
            "artifact_content must be a string",
        ),
    ],
)
def test_run_contract_check_rejects_non_string_request_fields(
    request_payload: dict[str, object],
    expected_error: str,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(request_payload)

    assert result == {"error": expected_error, "schema_version": 1}


def test_contract_tools_reject_blocking_salvage_schema_drift() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["acceptance_tests"] = "not-a-list"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    suggest_result = suggest_contract_checks(contract)

    expected = {
        "error": "Invalid contract payload: acceptance_tests must be a list, not str",
        "schema_version": 1,
    }
    assert run_result == expected
    assert suggest_result == expected


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda contract: contract["claims"].append(dict(contract["claims"][0])),
            "duplicate claim id claim-benchmark",
        ),
        (
            lambda contract: contract["deliverables"][0].__setitem__("id", "claim-benchmark"),
            "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous",
        ),
        (
            lambda contract: contract["references"][0].__setitem__("carry_forward_to", ["claim-benchmark"]),
            "reference ref-benchmark carry_forward_to must name workflow scope, not contract id claim-benchmark",
        ),
    ],
)
def test_contract_tools_reject_shared_contract_integrity_errors(
    mutator,
    expected_error: str,
) -> None:
    contract = _load_project_contract_fixture()

    mutator(contract)

    _assert_contract_tools_reject(contract, expected_error)


def test_contract_tools_reject_shared_integrity_errors_after_salvage() -> None:
    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"
    contract["deliverables"][0]["id"] = "claim-benchmark"

    _assert_contract_tools_reject(
        contract,
        "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous",
    )


def test_verification_server_success_responses_keep_stable_envelope_equality() -> None:
    from gpd.mcp.servers.verification_server import get_checklist, run_contract_check, suggest_contract_checks

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    run_expected = dict(run_result)
    run_expected.pop("schema_version")
    assert run_result == run_expected

    suggest_result = suggest_contract_checks(_derived_template_contract())
    suggest_expected = dict(suggest_result)
    suggest_expected.pop("schema_version")
    assert suggest_result == suggest_expected

    checklist_result = get_checklist("qft")
    checklist_expected = dict(checklist_result)
    checklist_expected.pop("schema_version")
    assert checklist_result == checklist_expected


def test_run_contract_check_surfaces_machine_readable_contract_salvage_findings() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _load_project_contract_fixture()
    contract["claims"][0]["notes"] = "legacy extra field"

    result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    assert result["contract_salvaged"] is True
    assert result["contract_salvage_findings"] == ["claims.0.notes: Extra inputs are not permitted"]
    assert result["supported_binding_fields"] == [
        "binding.claim_id",
        "binding.claim_ids",
        "binding.deliverable_id",
        "binding.deliverable_ids",
        "binding.acceptance_test_id",
        "binding.acceptance_test_ids",
        "binding.reference_id",
        "binding.reference_ids",
    ]


def test_verification_server_pure_success_tools_return_stable_envelopes() -> None:
    from gpd.mcp.servers import StableMCPEnvelope
    from gpd.mcp.servers.verification_server import (
        dimensional_check,
        get_verification_coverage,
        limiting_case_check,
        symmetry_check,
    )

    assert isinstance(dimensional_check(["[M] = [M]"]), StableMCPEnvelope)
    assert isinstance(limiting_case_check("E = m c^2", {"c -> infinity": "non-rel"}), StableMCPEnvelope)
    assert isinstance(symmetry_check("M(s,t)", ["parity"]), StableMCPEnvelope)
    assert isinstance(get_verification_coverage([15], ["5.1"]), StableMCPEnvelope)
