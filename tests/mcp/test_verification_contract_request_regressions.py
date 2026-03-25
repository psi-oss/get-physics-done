from __future__ import annotations

import copy
import json
from pathlib import Path

import anyio
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_project_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _call_verification_tool(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    from gpd.mcp.servers.verification_server import mcp

    async def _call() -> dict[str, object]:
        result = await mcp.call_tool(tool_name, arguments)
        if isinstance(result, dict):
            return result
        if (
            isinstance(result, list)
            and len(result) == 1
            and hasattr(result[0], "text")
            and isinstance(result[0].text, str)
        ):
            return json.loads(result[0].text)
        raise AssertionError(f"Unexpected MCP call result: {result!r}")

    return anyio.run(_call)


def test_run_contract_check_treats_empty_binding_like_omitted_binding() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    base_request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": copy.deepcopy(_load_project_contract_fixture()),
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    omitted_binding_result = run_contract_check(copy.deepcopy(base_request))
    empty_binding_result = run_contract_check({**copy.deepcopy(base_request), "binding": {}})

    assert empty_binding_result == omitted_binding_result
    assert omitted_binding_result["status"] == "pass"


def test_run_contract_check_accepts_semantically_equivalent_check_key_and_check_id_pairs() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    request_payload = {
        "check_key": "5.16",
        "check_id": "contract.benchmark_reproduction",
        "contract": copy.deepcopy(_load_project_contract_fixture()),
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    expected = run_contract_check({**copy.deepcopy(request_payload), "check_key": "contract.benchmark_reproduction"})
    result = run_contract_check(request_payload)

    assert result == expected
    assert result["status"] == "pass"
    assert result["check_key"] == "contract.benchmark_reproduction"
    assert result["check_id"] == "5.16"
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected


def test_run_contract_check_accepts_typed_nested_request_objects() -> None:
    from gpd.contracts import ResearchContract
    from gpd.mcp.servers.verification_server import (
        ContractBindingRequest,
        ContractMetadataRequest,
        ContractObservedRequest,
        RunContractCheckRequest,
        run_contract_check,
    )

    request = RunContractCheckRequest(
        check_key="contract.benchmark_reproduction",
        contract=ResearchContract.model_validate(_load_project_contract_fixture()),
        binding=ContractBindingRequest(claim_ids=["claim-benchmark"]),
        metadata=ContractMetadataRequest(source_reference_id="ref-benchmark"),
        observed=ContractObservedRequest(metric_value=0.01, threshold_value=0.02),
    )

    result = run_contract_check(request)

    assert result["status"] == "pass"
    assert result["binding"]["claim_ids"] == ["claim-benchmark"]
    assert result["metrics"]["source_reference_id"] == "ref-benchmark"


def test_run_contract_check_accepts_nested_base_model_binding_aliases_in_any_order() -> None:
    from gpd.mcp.servers.verification_server import (
        ContractBindingRequest,
        ContractMetadataRequest,
        ContractObservedRequest,
        RunContractCheckRequest,
        run_contract_check,
    )

    request = RunContractCheckRequest(
        check_key="contract.benchmark_reproduction",
        binding=ContractBindingRequest(
            claim_id=["claim-a", "claim-b"],
            claim_ids=["claim-b", "claim-a"],
        ),
        metadata=ContractMetadataRequest(source_reference_id="ref-benchmark"),
        observed=ContractObservedRequest(metric_value=0.01, threshold_value=0.02),
    )

    result = run_contract_check(request)

    assert result["status"] == "pass"
    assert result["binding"]["claim_id"] == ["claim-a", "claim-b"]
    assert result["binding"]["claim_ids"] == ["claim-b", "claim-a"]


def test_suggest_contract_checks_normalizes_whitespace_padded_active_checks() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    active_checks = [" contract.benchmark_reproduction ", "\n5.16\t"]

    result = suggest_contract_checks(_load_project_contract_fixture(), active_checks=active_checks)
    result_via_mcp = _call_verification_tool(
        "suggest_contract_checks",
        {"contract": _load_project_contract_fixture(), "active_checks": active_checks},
    )

    benchmark = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction")
    assert benchmark["already_active"] is True
    assert result_via_mcp == result


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {
                    "claim_id": "claim-benchmark",
                    "claim_ids": ["claim-other"],
                },
            },
            {
                "error": "binding.claim_id and binding.claim_ids must match when both are provided",
                "schema_version": 1,
            },
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "check_id": "contract.limit_recovery",
            },
            {
                "error": "check_key and check_id must identify the same contract check when both are provided",
                "schema_version": 1,
            },
        ),
    ],
)
def test_run_contract_check_surfaces_cross_field_request_consistency_errors(
    request_payload: dict[str, object],
    expected_error: dict[str, object],
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    assert run_contract_check(request_payload) == expected_error
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected_error


def test_contract_tools_reject_blank_scalar_to_list_drift() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["claims"][0]["references"] = "   "

    expected = {"error": "Invalid contract payload: claims.0.references must not be blank", "schema_version": 1}

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    assert run_contract_check(request) == expected
    assert suggest_contract_checks(contract) == expected
    assert _call_verification_tool("run_contract_check", {"request": request}) == expected
    assert _call_verification_tool("suggest_contract_checks", {"contract": contract}) == expected


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "unexpected": True,
            },
            {
                "error": (
                    "request contains unsupported keys: unexpected; supported keys are "
                    "check_key, check_id, contract, binding, metadata, observed, artifact_content"
                ),
                "schema_version": 1,
            },
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "power_law", "unexpected": True},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            {
                "error": (
                    "metadata contains unsupported keys: unexpected; supported keys are "
                    "regime_label, expected_behavior, source_reference_id, declared_family, allowed_families, "
                    "forbidden_families"
                ),
                "schema_version": 1,
            },
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02, "unexpected": True},
            },
            {
                "error": (
                    "observed contains unsupported keys: unexpected; supported keys are "
                    "limit_passed, observed_limit, metric_value, threshold_value, proxy_only, direct_available, "
                    "proxy_available, consistency_passed, selected_family, competing_family_checked, bias_checked, "
                    "calibration_checked"
                ),
                "schema_version": 1,
            },
        ),
    ],
)
def test_run_contract_check_rejects_unknown_keys_as_stable_request_errors(
    request_payload: dict[str, object],
    expected_error: dict[str, object],
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    assert run_contract_check(request_payload) == expected_error
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected_error
