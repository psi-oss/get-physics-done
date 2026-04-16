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


def _tool_input_schema(mcp_server: object, tool_name: str) -> dict[str, object]:
    async def _load() -> dict[str, object]:
        tools = await mcp_server.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == tool_name)

    return anyio.run(_load)


def _schema_object(schema: dict[str, object], schema_fragment: dict[str, object]) -> dict[str, object]:
    if "properties" in schema_fragment:
        return schema_fragment
    ref = schema_fragment["$ref"]
    target: object = schema
    for segment in str(ref).removeprefix("#/").split("/"):
        if not isinstance(target, dict):
            raise AssertionError(f"Schema pointer {ref} resolved to non-object {target!r}")
        target = target[segment]
    if not isinstance(target, dict):
        raise AssertionError(f"Schema pointer {ref} resolved to non-object {target!r}")
    return target


def _schema_anyof_object(schema_fragment: dict[str, object]) -> dict[str, object]:
    if schema_fragment.get("type") == "object":
        return schema_fragment
    for branch in schema_fragment.get("anyOf", []):
        if isinstance(branch, dict) and branch.get("type") == "object":
            return branch
    raise AssertionError(f"No object branch found in {schema_fragment!r}")


def _request_requirement_for_check(
    run_request_schema: dict[str, object], check_identifier: str
) -> dict[str, object] | None:
    for clause in run_request_schema.get("allOf", []):
        if_branch = clause.get("if")
        if not isinstance(if_branch, dict):
            continue
        candidate_branches = if_branch.get("anyOf", [])
        if not candidate_branches:
            candidate_branches = [if_branch]
        for branch in candidate_branches:
            if not isinstance(branch, dict):
                continue
            field_schema = branch.get("properties", {}).get("check_key")
            if not isinstance(field_schema, dict):
                continue
            enum_values = field_schema.get("enum")
            if isinstance(enum_values, list) and check_identifier in enum_values:
                then_schema = clause.get("then")
                if isinstance(then_schema, dict) and "required" in then_schema:
                    return then_schema
    return None


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


def test_run_contract_check_accepts_numeric_check_key_identifiers() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    request_payload = {
        "check_key": "5.16",
        "contract": copy.deepcopy(_load_project_contract_fixture()),
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    expected = run_contract_check({**copy.deepcopy(request_payload), "check_key": "contract.benchmark_reproduction"})
    result = run_contract_check(request_payload)

    assert result == expected
    assert result["status"] == "pass"
    assert result["check_key"] == "contract.benchmark_reproduction"
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected


def test_run_contract_check_published_schema_keeps_schema_required_fields_strict() -> None:
    from gpd.mcp.servers.verification_server import mcp
    from gpd.mcp.verification_contract_policy import VERIFICATION_BINDING_FIELD_NAMES

    run_schema = _tool_input_schema(mcp, "run_contract_check")
    request_schema = _schema_object(run_schema, run_schema["properties"]["request"])
    assert "check_id" not in request_schema["properties"]
    binding_schema = _schema_anyof_object(request_schema["properties"]["binding"])
    assert set(binding_schema["properties"]) == {
        field_name.removeprefix("binding.") for field_name in VERIFICATION_BINDING_FIELD_NAMES
    }
    for field_name in binding_schema["properties"]:
        field_schema = binding_schema["properties"][field_name]
        assert field_schema["type"] == "array"
        assert field_schema["minItems"] == 1
        assert field_schema["items"]["type"] == "string"
        assert field_schema["items"]["minLength"] == 1
        assert field_schema["items"]["pattern"] == r"\S"
        assert field_schema["uniqueItems"] is True
    benchmark_requirement = _request_requirement_for_check(request_schema, "contract.benchmark_reproduction")
    assert benchmark_requirement is not None
    observed_schema = _schema_anyof_object(benchmark_requirement["properties"]["observed"])

    assert benchmark_requirement["required"] == ["observed"]
    assert observed_schema["required"] == ["metric_value", "threshold_value"]
    assert observed_schema["properties"]["metric_value"]["type"] == "number"
    assert observed_schema["properties"]["threshold_value"]["type"] == "number"
    assert "null" not in json.dumps(observed_schema["properties"]["metric_value"])
    assert "null" not in json.dumps(observed_schema["properties"]["threshold_value"])
    assert "anyOf" in benchmark_requirement
    metadata_branch = next(
        branch for branch in benchmark_requirement["anyOf"] if "metadata" in branch.get("required", [])
    )
    contract_branch = next(
        branch for branch in benchmark_requirement["anyOf"] if "contract" in branch.get("required", [])
    )
    metadata_schema = _schema_anyof_object(metadata_branch["properties"]["metadata"])
    contract_schema = _schema_anyof_object(contract_branch["properties"]["contract"])
    assert metadata_schema["required"] == ["source_reference_id"]
    assert metadata_schema["properties"]["source_reference_id"]["minLength"] == 1
    assert metadata_schema["properties"]["source_reference_id"]["pattern"] == r"\S"
    assert "null" not in json.dumps(metadata_schema["properties"]["source_reference_id"])
    assert contract_schema["required"] == ["schema_version", "scope", "context_intake", "uncertainty_markers"]

    proof_hypothesis_requirement = _request_requirement_for_check(request_schema, "contract.proof_hypothesis_coverage")
    assert proof_hypothesis_requirement is not None
    assert proof_hypothesis_requirement["required"] == ["contract", "metadata", "observed"]
    proof_hypothesis_metadata = _schema_anyof_object(proof_hypothesis_requirement["properties"]["metadata"])
    proof_hypothesis_observed = _schema_anyof_object(proof_hypothesis_requirement["properties"]["observed"])
    assert proof_hypothesis_metadata["required"] == ["hypothesis_ids"]
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["minItems"] == 1
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["items"]["type"] == "string"
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["items"]["minLength"] == 1
    assert proof_hypothesis_observed["required"] == ["covered_hypothesis_ids"]
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["minItems"] == 1
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["items"]["type"] == "string"
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["items"]["minLength"] == 1

    proof_parameter_requirement = _request_requirement_for_check(request_schema, "contract.proof_parameter_coverage")
    assert proof_parameter_requirement is not None
    assert proof_parameter_requirement["required"] == ["contract", "metadata", "observed"]
    proof_parameter_metadata = _schema_anyof_object(proof_parameter_requirement["properties"]["metadata"])
    proof_parameter_observed = _schema_anyof_object(proof_parameter_requirement["properties"]["observed"])
    assert proof_parameter_metadata["required"] == ["theorem_parameter_symbols"]
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["minItems"] == 1
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["items"]["type"] == "string"
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["items"]["minLength"] == 1
    assert proof_parameter_observed["required"] == ["covered_parameter_symbols"]
    assert proof_parameter_observed["properties"]["covered_parameter_symbols"]["minItems"] == 1
    assert proof_parameter_observed["properties"]["covered_parameter_symbols"]["items"]["type"] == "string"
    assert proof_parameter_observed["properties"]["covered_parameter_symbols"]["items"]["minLength"] == 1

    alignment_requirement = _request_requirement_for_check(request_schema, "contract.claim_to_proof_alignment")
    assert alignment_requirement is not None
    assert alignment_requirement["required"] == ["contract", "observed"]
    assert alignment_requirement["anyOf"][0]["required"] == ["metadata"]
    assert alignment_requirement["anyOf"][1]["required"] == ["metadata", "observed"]
    alignment_metadata = _schema_anyof_object(alignment_requirement["anyOf"][0]["properties"]["metadata"])
    alignment_metadata_branch = _schema_anyof_object(alignment_requirement["anyOf"][1]["properties"]["metadata"])
    alignment_observed_branch = _schema_anyof_object(alignment_requirement["anyOf"][1]["properties"]["observed"])
    assert alignment_metadata["required"] == ["claim_statement"]
    assert alignment_metadata["properties"]["claim_statement"]["minLength"] == 1
    assert alignment_metadata["properties"]["claim_statement"]["pattern"] == r"\S"
    assert alignment_metadata_branch["required"] == ["conclusion_clause_ids"]
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["minItems"] == 1
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["items"]["type"] == "string"
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["items"]["minLength"] == 1
    assert alignment_observed_branch["required"] == ["uncovered_conclusion_clause_ids"]
    assert alignment_observed_branch["properties"]["uncovered_conclusion_clause_ids"]["minItems"] == 1
    assert alignment_observed_branch["properties"]["uncovered_conclusion_clause_ids"]["items"]["type"] == "string"
    assert alignment_observed_branch["properties"]["uncovered_conclusion_clause_ids"]["items"]["minLength"] == 1
    assert "check_id" not in json.dumps(run_schema)


def test_contract_binding_request_model_fields_match_canonical_binding_field_names() -> None:
    from gpd.mcp.servers.verification_server import ContractBindingRequest
    from gpd.mcp.verification_contract_policy import VERIFICATION_BINDING_FIELD_NAMES

    assert tuple(ContractBindingRequest.model_fields) == tuple(
        field_name.removeprefix("binding.") for field_name in VERIFICATION_BINDING_FIELD_NAMES
    )


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {"check_key": ""},
            {"error": "check_key must be a non-empty string", "schema_version": 1},
        ),
        (
            {"check_key": " contract.benchmark_reproduction "},
            {"error": "check_key must not include leading or trailing whitespace", "schema_version": 1},
        ),
        (
            {"check_id": "contract.benchmark_reproduction"},
            {
                "error": (
                    "request contains unsupported keys: check_id; supported keys are "
                    "check_key, contract, binding, metadata, observed, artifact_content"
                ),
                "schema_version": 1,
            },
        ),
    ],
)
def test_run_contract_check_rejects_non_exact_check_identifiers(
    request_payload: dict[str, object],
    expected_error: dict[str, object],
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    assert run_contract_check(request_payload) == expected_error
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected_error


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


def test_run_contract_check_accepts_nested_base_model_canonical_binding_lists() -> None:
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
            claim_ids=["claim-a", "claim-b"],
            reference_ids=["ref-benchmark"],
        ),
        metadata=ContractMetadataRequest(source_reference_id="ref-benchmark"),
        observed=ContractObservedRequest(metric_value=0.01, threshold_value=0.02),
    )

    result = run_contract_check(request)

    assert result["status"] == "pass"
    assert result["binding"]["claim_ids"] == ["claim-a", "claim-b"]
    assert result["binding"]["reference_ids"] == ["ref-benchmark"]


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": []},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            {"error": "binding.claim_ids must include at least one non-empty string", "schema_version": 1},
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": ["claim-benchmark", "claim-benchmark"]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            {"error": "binding.claim_ids must not contain duplicate values", "schema_version": 1},
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"allowed_families": ["power_law", "power_law"]},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            {"error": "metadata.allowed_families must not contain duplicate values", "schema_version": 1},
        ),
    ],
)
def test_run_contract_check_rejects_empty_and_duplicate_string_lists(
    request_payload: dict[str, object],
    expected_error: dict[str, object],
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    assert run_contract_check(request_payload) == expected_error
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected_error


def test_suggest_contract_checks_normalizes_whitespace_padded_active_checks() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    active_checks = [" contract.benchmark_reproduction ", "\n5.16\t"]

    result = suggest_contract_checks(_load_project_contract_fixture(), active_checks=active_checks)
    result_via_mcp = _call_verification_tool(
        "suggest_contract_checks",
        {"contract": _load_project_contract_fixture(), "active_checks": active_checks},
    )

    benchmark = next(
        entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction"
    )
    assert benchmark["already_active"] is True
    assert result_via_mcp == result


def test_run_contract_check_rejects_legacy_binding_alias_keys() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    request_payload = {
        "check_key": "contract.benchmark_reproduction",
        "binding": {"claim_id": ["claim-benchmark"]},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    expected_error = {
        "error": (
            "binding contains unsupported keys: claim_id; supported keys are "
            "binding.claim_ids, binding.deliverable_ids, binding.acceptance_test_ids, binding.reference_ids"
        ),
        "schema_version": 1,
    }

    assert run_contract_check(request_payload) == expected_error
    assert _call_verification_tool("run_contract_check", {"request": request_payload}) == expected_error


def test_contract_tools_reject_blank_scalar_to_list_drift() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["claims"][0]["references"] = "   "

    expected = {
        "error": (
            "Invalid contract payload: claims.0.references must not be blank; "
            "claims.0.references was normalized from blank string to empty list"
        ),
        "contract_error_details": [
            "claims.0.references must not be blank",
            "claims.0.references was normalized from blank string to empty list",
        ],
        "schema_version": 1,
    }

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


def test_contract_payload_schema_does_not_advertise_scalar_list_drift() -> None:
    from gpd.mcp.servers.verification_server import _CONTRACT_PAYLOAD_INPUT_SCHEMA

    def assert_array_only(schema: dict[str, object], field_path: tuple[str, ...]) -> None:
        current: object = schema
        for field_name in field_path:
            assert isinstance(current, dict)
            current = current[field_name]
        assert isinstance(current, dict)
        assert current["type"] == "array"
        assert "anyOf" not in current

    assert_array_only(_CONTRACT_PAYLOAD_INPUT_SCHEMA, ("properties", "claims", "items", "properties", "references"))
    assert_array_only(
        _CONTRACT_PAYLOAD_INPUT_SCHEMA,
        ("properties", "references", "items", "properties", "required_actions"),
    )
    assert_array_only(_CONTRACT_PAYLOAD_INPUT_SCHEMA, ("properties", "context_intake", "properties", "must_read_refs"))


def test_contract_check_request_templates_use_string_artifact_placeholders() -> None:
    from gpd.mcp.servers.verification_server import _CONTRACT_CHECK_REQUEST_HINTS

    for hint in _CONTRACT_CHECK_REQUEST_HINTS.values():
        template = hint.get("request_template")
        assert isinstance(template, dict)
        if "artifact_content" in template:
            assert template["artifact_content"] == ""


def test_contract_parse_recoverability_keeps_case_drift_nonblocking() -> None:
    from gpd.mcp.servers.verification_server import _is_recoverable_contract_parse_error, run_contract_check

    contract = _load_project_contract_fixture()

    assert _is_recoverable_contract_parse_error(
        "references.0.role must use exact canonical value: benchmark",
        contract_raw=contract,
    )
    assert not _is_recoverable_contract_parse_error(
        "references.0.notes: Extra inputs are not permitted",
        contract_raw=contract,
    )

    contract["references"][0]["role"] = "BENCHMARK"
    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    result = run_contract_check(request)

    assert result["status"] == "pass"


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
                    "check_key, contract, binding, metadata, observed, artifact_content"
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
                    "forbidden_families, theorem_parameter_symbols, hypothesis_ids, quantifiers, "
                    "conclusion_clause_ids, claim_statement"
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
                    "calibration_checked, covered_hypothesis_ids, missing_hypothesis_ids, "
                    "covered_parameter_symbols, missing_parameter_symbols, uncovered_quantifiers, "
                    "uncovered_conclusion_clause_ids, quantifier_status, scope_status, counterexample_status"
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
