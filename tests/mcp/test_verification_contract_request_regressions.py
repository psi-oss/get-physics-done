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


def _schema_anyof_array(schema_fragment: dict[str, object]) -> dict[str, object]:
    if schema_fragment.get("type") == "array":
        return schema_fragment
    for branch in schema_fragment.get("anyOf", []):
        if isinstance(branch, dict) and branch.get("type") == "array":
            return branch
    raise AssertionError(f"No array branch found in {schema_fragment!r}")


def _schema_anyof_string(schema_fragment: dict[str, object]) -> dict[str, object]:
    if schema_fragment.get("type") == "string":
        return schema_fragment
    for branch in schema_fragment.get("anyOf", []):
        if isinstance(branch, dict) and branch.get("type") == "string":
            return branch
    raise AssertionError(f"No string branch found in {schema_fragment!r}")


def _schema_fragment(schema: object, field_path: tuple[str | int, ...]) -> dict[str, object]:
    current = schema
    for segment in field_path:
        if isinstance(segment, int):
            if not isinstance(current, list):
                raise AssertionError(f"Schema path {field_path!r} resolved to non-list {current!r}")
            current = current[segment]
            continue
        if not isinstance(current, dict):
            raise AssertionError(f"Schema path {field_path!r} resolved to non-object {current!r}")
        current = current[segment]
    if not isinstance(current, dict):
        raise AssertionError(f"Schema path {field_path!r} resolved to non-object {current!r}")
    return current


def _published_contract_payload_schema(tool_name: str) -> dict[str, object]:
    from gpd.mcp.servers.verification_server import mcp

    tool_schema = _tool_input_schema(mcp, tool_name)
    if tool_name == "run_contract_check":
        request_schema = _schema_object(tool_schema, tool_schema["properties"]["request"])
        return _schema_anyof_object(request_schema["properties"]["contract"])
    if tool_name == "suggest_contract_checks":
        return _schema_anyof_object(tool_schema["properties"]["contract"])
    raise AssertionError(f"Unsupported tool name: {tool_name}")


def _assert_contract_scalar_or_array_string_list_schema(
    schema_fragment: dict[str, object],
    *,
    min_items: int | None = None,
) -> None:
    string_branch = _schema_anyof_string(schema_fragment)
    array_branch = _schema_anyof_array(schema_fragment)

    assert string_branch["minLength"] == 1
    assert string_branch["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert array_branch["items"]["type"] == "string"
    assert array_branch["items"]["minLength"] == 1
    assert array_branch["items"]["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert array_branch["uniqueItems"] is True
    if min_items is not None:
        assert array_branch["minItems"] == min_items


def _assert_contract_recoverable_enum_string_schema(
    schema_fragment: dict[str, object],
    *,
    enum_values: tuple[str, ...],
) -> None:
    if schema_fragment.get("type") == "string":
        assert schema_fragment["enum"] == list(enum_values)
        return

    exact_branch = next(
        branch
        for branch in schema_fragment.get("anyOf", [])
        if isinstance(branch, dict) and branch.get("type") == "string" and "enum" in branch
    )
    pattern_branch = next(
        branch
        for branch in schema_fragment.get("anyOf", [])
        if isinstance(branch, dict) and branch.get("type") == "string" and "pattern" in branch
    )
    assert exact_branch["enum"] == list(enum_values)
    assert pattern_branch["pattern"].startswith("^(?:")
    assert pattern_branch["pattern"].endswith(")$")


def _assert_contract_scalar_or_array_enum_list_schema(
    schema_fragment: dict[str, object],
    *,
    enum_values: tuple[str, ...],
) -> None:
    array_branch = _schema_anyof_array(schema_fragment)
    scalar_branch = next(
        branch
        for branch in schema_fragment.get("anyOf", [])
        if isinstance(branch, dict) and branch.get("type") != "array"
    )

    _assert_contract_recoverable_enum_string_schema(scalar_branch, enum_values=enum_values)
    _assert_contract_recoverable_enum_string_schema(array_branch["items"], enum_values=enum_values)
    assert array_branch["uniqueItems"] is True


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
        assert "anyOf" not in field_schema
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
    assert metadata_schema["properties"]["source_reference_id"]["type"] == "string"
    assert "anyOf" not in metadata_schema["properties"]["source_reference_id"]
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
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["type"] == "array"
    assert "anyOf" not in proof_hypothesis_metadata["properties"]["hypothesis_ids"]
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["minItems"] == 1
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["items"]["type"] == "string"
    assert proof_hypothesis_metadata["properties"]["hypothesis_ids"]["items"]["minLength"] == 1
    assert proof_hypothesis_observed["required"] == ["covered_hypothesis_ids"]
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["type"] == "array"
    assert "anyOf" not in proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["minItems"] == 1
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["items"]["type"] == "string"
    assert proof_hypothesis_observed["properties"]["covered_hypothesis_ids"]["items"]["minLength"] == 1

    proof_parameter_requirement = _request_requirement_for_check(request_schema, "contract.proof_parameter_coverage")
    assert proof_parameter_requirement is not None
    assert proof_parameter_requirement["required"] == ["contract", "metadata", "observed"]
    proof_parameter_metadata = _schema_anyof_object(proof_parameter_requirement["properties"]["metadata"])
    proof_parameter_observed = _schema_anyof_object(proof_parameter_requirement["properties"]["observed"])
    assert proof_parameter_metadata["required"] == ["theorem_parameter_symbols"]
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["type"] == "array"
    assert "anyOf" not in proof_parameter_metadata["properties"]["theorem_parameter_symbols"]
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["minItems"] == 1
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["items"]["type"] == "string"
    assert proof_parameter_metadata["properties"]["theorem_parameter_symbols"]["items"]["minLength"] == 1
    assert proof_parameter_observed["required"] == ["covered_parameter_symbols"]
    assert proof_parameter_observed["properties"]["covered_parameter_symbols"]["type"] == "array"
    assert "anyOf" not in proof_parameter_observed["properties"]["covered_parameter_symbols"]
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
    assert alignment_metadata["properties"]["claim_statement"]["type"] == "string"
    assert "anyOf" not in alignment_metadata["properties"]["claim_statement"]
    assert alignment_metadata["properties"]["claim_statement"]["minLength"] == 1
    assert alignment_metadata["properties"]["claim_statement"]["pattern"] == r"\S"
    assert alignment_metadata_branch["required"] == ["conclusion_clause_ids"]
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["type"] == "array"
    assert "anyOf" not in alignment_metadata_branch["properties"]["conclusion_clause_ids"]
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["minItems"] == 1
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["items"]["type"] == "string"
    assert alignment_metadata_branch["properties"]["conclusion_clause_ids"]["items"]["minLength"] == 1
    assert alignment_observed_branch["required"] == ["uncovered_conclusion_clause_ids"]
    assert alignment_observed_branch["properties"]["uncovered_conclusion_clause_ids"]["type"] == "array"
    assert "anyOf" not in alignment_observed_branch["properties"]["uncovered_conclusion_clause_ids"]
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


@pytest.mark.parametrize("tool_name", ["run_contract_check", "suggest_contract_checks"])
def test_contract_payload_schema_relaxes_only_recoverable_embedded_contract_list_fields(
    tool_name: str,
) -> None:
    from gpd.contracts import (
        CONTRACT_REFERENCE_ACTION_VALUES,
        PROJECT_CONTRACT_COLLECTION_LIST_FIELDS,
        PROJECT_CONTRACT_MAPPING_LIST_FIELDS,
        PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS,
    )

    contract_schema = _published_contract_payload_schema(tool_name)

    for field_name in PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS:
        top_level_schema = _schema_fragment(contract_schema, ("properties", field_name))
        assert top_level_schema["type"] == "array"
        assert "anyOf" not in top_level_schema

    required_contract_min_items = {
        ("claims", "deliverables"): 1,
        ("claims", "acceptance_tests"): 1,
        ("uncertainty_markers", "weakest_anchors"): 1,
        ("uncertainty_markers", "disconfirming_observations"): 1,
    }
    for field_name in PROJECT_CONTRACT_MAPPING_LIST_FIELDS["context_intake"]:
        required_contract_min_items[("context_intake", field_name)] = 1

    for section_name, field_names in PROJECT_CONTRACT_MAPPING_LIST_FIELDS.items():
        for field_name in field_names:
            field_schema = _schema_fragment(
                contract_schema,
                ("properties", section_name, "properties", field_name),
            )
            _assert_contract_scalar_or_array_string_list_schema(
                field_schema,
                min_items=required_contract_min_items.get((section_name, field_name)),
            )

    for collection_name, field_names in PROJECT_CONTRACT_COLLECTION_LIST_FIELDS.items():
        for field_name in field_names:
            field_schema = _schema_fragment(
                contract_schema,
                ("properties", collection_name, "items", "properties", field_name),
            )
            if collection_name == "references" and field_name == "required_actions":
                _assert_contract_scalar_or_array_enum_list_schema(
                    field_schema,
                    enum_values=CONTRACT_REFERENCE_ACTION_VALUES,
                )
                continue
            _assert_contract_scalar_or_array_string_list_schema(
                field_schema,
                min_items=required_contract_min_items.get((collection_name, field_name)),
            )

    _assert_contract_scalar_or_array_string_list_schema(
        _schema_fragment(
            contract_schema,
            ("properties", "claims", "items", "properties", "parameters", "items", "properties", "aliases"),
        )
    )
    _assert_contract_scalar_or_array_string_list_schema(
        _schema_fragment(
            contract_schema,
            ("properties", "claims", "items", "properties", "hypotheses", "items", "properties", "symbols"),
        )
    )


def test_suggest_contract_checks_published_schema_keeps_active_checks_strict() -> None:
    from gpd.mcp.servers.verification_server import mcp

    suggest_schema = _tool_input_schema(mcp, "suggest_contract_checks")
    active_checks_schema = suggest_schema["properties"]["active_checks"]
    active_checks_array = _schema_anyof_array(active_checks_schema)

    assert not any(
        isinstance(branch, dict) and branch.get("type") == "string"
        for branch in active_checks_schema.get("anyOf", [])
    )
    assert active_checks_array["items"]["type"] == "string"
    assert active_checks_array["items"]["minLength"] == 1
    assert active_checks_array["items"]["pattern"] == r"\S"


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
