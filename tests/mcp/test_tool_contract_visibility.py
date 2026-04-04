from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest


def _tool_description(mcp_server: object, tool_name: str) -> str:
    async def _load() -> str:
        tools = await mcp_server.list_tools()
        return next(tool.description for tool in tools if tool.name == tool_name)

    return anyio.run(_load)


def _tool_input_schema(mcp_server: object, tool_name: str) -> dict[str, object]:
    async def _load() -> dict[str, object]:
        tools = await mcp_server.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == tool_name)

    return anyio.run(_load)


def _schema_ref(schema_fragment: dict[str, object]) -> str:
    if "$ref" in schema_fragment:
        return str(schema_fragment["$ref"])
    for branch in schema_fragment.get("anyOf", []):
        if isinstance(branch, dict) and "$ref" in branch:
            return str(branch["$ref"])
    raise AssertionError(f"No schema reference found in {schema_fragment!r}")


def _schema_object(schema: dict[str, object], schema_fragment: dict[str, object]) -> dict[str, object]:
    if "properties" in schema_fragment:
        return schema_fragment
    ref = _schema_ref(schema_fragment)
    target: object = schema
    for segment in ref.removeprefix("#/").split("/"):
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


def _schema_anyof_string(schema_fragment: dict[str, object]) -> dict[str, object]:
    if schema_fragment.get("type") == "string":
        return schema_fragment
    for branch in schema_fragment.get("anyOf", []):
        if isinstance(branch, dict) and branch.get("type") == "string":
            return branch
    raise AssertionError(f"No string branch found in {schema_fragment!r}")


def _assert_string_or_string_list_schema(schema_fragment: dict[str, object], *, label: str) -> None:
    assert len(schema_fragment["anyOf"]) == 2, f"{label} must publish string-or-list recovery boundary"
    string_branch = _schema_anyof_string(schema_fragment)
    assert string_branch["minLength"] == 1
    assert string_branch["pattern"] == r"\S"

    array_branch = next(
        branch for branch in schema_fragment["anyOf"] if isinstance(branch, dict) and branch.get("type") == "array"
    )
    assert array_branch["items"]["type"] == "string"
    assert array_branch["items"]["minLength"] == 1
    assert array_branch["items"]["pattern"] == r"\S"
    assert array_branch["uniqueItems"] is True


def _assert_enum_string_or_string_list_schema(
    schema_fragment: dict[str, object],
    *,
    label: str,
    enum_values: list[str],
) -> None:
    assert len(schema_fragment["anyOf"]) == 2, f"{label} must publish enum-string-or-list recovery boundary"
    enum_branch = next(
        branch for branch in schema_fragment["anyOf"] if isinstance(branch, dict) and branch.get("type") == "string"
    )
    assert enum_branch["enum"] == enum_values

    array_branch = next(
        branch for branch in schema_fragment["anyOf"] if isinstance(branch, dict) and branch.get("type") == "array"
    )
    assert array_branch["items"]["type"] == "string"
    assert array_branch["items"]["enum"] == enum_values
    assert array_branch["uniqueItems"] is True


def _assert_closed_object(schema_fragment: dict[str, object], *, label: str) -> None:
    assert schema_fragment["additionalProperties"] is False, f"{label} must reject unknown top-level keys"


def _binding_condition_for_check(run_request_schema: dict[str, object], check_identifier: str) -> dict[str, object]:
    for clause in run_request_schema.get("allOf", []):
        if_branch = clause.get("if")
        if not isinstance(if_branch, dict):
            continue
        for branch in if_branch.get("anyOf", []):
            if not isinstance(branch, dict):
                continue
            for field_name in ("check_key", "check_id"):
                field_schema = branch.get("properties", {}).get(field_name)
                if not isinstance(field_schema, dict):
                    continue
                enum_values = field_schema.get("enum")
                if isinstance(enum_values, list) and check_identifier in enum_values:
                    binding_schema = clause.get("then", {}).get("properties", {}).get("binding")
                    if isinstance(binding_schema, dict):
                        return _schema_anyof_object(binding_schema)
    raise AssertionError(f"No binding condition found for {check_identifier!r}")


def _request_requirement_for_check(run_request_schema: dict[str, object], check_identifier: str) -> dict[str, object]:
    fallback: dict[str, object] | None = None
    for clause in run_request_schema.get("allOf", []):
        if_branch = clause.get("if")
        if not isinstance(if_branch, dict):
            continue
        for branch in if_branch.get("anyOf", []):
            if not isinstance(branch, dict):
                continue
            for field_name in ("check_key", "check_id"):
                field_schema = branch.get("properties", {}).get(field_name)
                if not isinstance(field_schema, dict):
                    continue
                enum_values = field_schema.get("enum")
                if isinstance(enum_values, list) and check_identifier in enum_values:
                    then_schema = clause.get("then")
                    if isinstance(then_schema, dict):
                        if "required" in then_schema:
                            return then_schema
                        fallback = then_schema
    if fallback is not None:
        return fallback
    raise AssertionError(f"No request requirement condition found for {check_identifier!r}")


def _assert_contract_schema_sections_closed(contract_schema: dict[str, object]) -> None:
    _assert_closed_object(contract_schema, label="contract")
    assert {"schema_version", "scope", "claims", "references"} <= set(contract_schema["properties"])

    scope = _schema_object(contract_schema, contract_schema["properties"]["scope"])
    _assert_closed_object(scope, label="contract.scope")
    assert scope["required"] == ["question"]
    assert scope["properties"]["question"]["minLength"] == 1
    assert scope["properties"]["question"]["pattern"] == r"\S"
    for field_name in ("in_scope", "out_of_scope", "unresolved_questions"):
        _assert_string_or_string_list_schema(scope["properties"][field_name], label=f"contract.scope.{field_name}")

    context_intake = _schema_object(contract_schema, contract_schema["properties"]["context_intake"])
    _assert_closed_object(context_intake, label="contract.context_intake")
    assert context_intake["minProperties"] == 1
    for field_name in (
        "must_read_refs",
        "must_include_prior_outputs",
        "user_asserted_anchors",
        "known_good_baselines",
        "context_gaps",
        "crucial_inputs",
    ):
        _assert_string_or_string_list_schema(
            context_intake["properties"][field_name],
            label=f"contract.context_intake.{field_name}",
        )

    approach_policy = _schema_object(contract_schema, contract_schema["properties"]["approach_policy"])
    _assert_closed_object(approach_policy, label="contract.approach_policy")
    for field_name in (
        "formulations",
        "allowed_estimator_families",
        "forbidden_estimator_families",
        "allowed_fit_families",
        "forbidden_fit_families",
        "stop_and_rethink_conditions",
    ):
        _assert_string_or_string_list_schema(
            approach_policy["properties"][field_name],
            label=f"contract.approach_policy.{field_name}",
        )

    claims = contract_schema["properties"]["claims"]["items"]
    _assert_closed_object(claims, label="contract.claims[]")
    assert claims["required"] == ["id", "statement", "deliverables", "acceptance_tests"]
    assert claims["properties"]["id"]["minLength"] == 1
    assert claims["properties"]["id"]["pattern"] == r"\S"
    assert claims["properties"]["claim_kind"]["enum"] == [
        "theorem",
        "lemma",
        "corollary",
        "proposition",
        "result",
        "claim",
        "other",
    ]
    for field_name in ("observables", "deliverables", "acceptance_tests", "references", "quantifiers", "proof_deliverables"):
        _assert_string_or_string_list_schema(claims["properties"][field_name], label=f"contract.claims[].{field_name}")
    parameters = claims["properties"]["parameters"]["items"]
    _assert_closed_object(parameters, label="contract.claims[].parameters[]")
    _assert_string_or_string_list_schema(parameters["properties"]["aliases"], label="contract.claims[].parameters[].aliases")
    hypotheses = claims["properties"]["hypotheses"]["items"]
    _assert_closed_object(hypotheses, label="contract.claims[].hypotheses[]")
    _assert_string_or_string_list_schema(hypotheses["properties"]["symbols"], label="contract.claims[].hypotheses[].symbols")
    conclusion_clauses = claims["properties"]["conclusion_clauses"]["items"]
    _assert_closed_object(conclusion_clauses, label="contract.claims[].conclusion_clauses[]")

    observables = contract_schema["properties"]["observables"]["items"]
    _assert_closed_object(observables, label="contract.observables[]")
    assert observables["properties"]["kind"]["enum"] == [
        "scalar",
        "curve",
        "map",
        "classification",
        "proof_obligation",
        "other",
    ]
    for field_name in ("regime", "units"):
        field_schema = observables["properties"][field_name]
        assert len(field_schema["anyOf"]) == 2
        string_branch = _schema_anyof_string(field_schema)
        assert string_branch["minLength"] == 1
        assert string_branch["pattern"] == r"\S"
        assert any(branch.get("type") == "null" for branch in field_schema["anyOf"] if isinstance(branch, dict))

    deliverables = contract_schema["properties"]["deliverables"]["items"]
    _assert_closed_object(deliverables, label="contract.deliverables[]")
    assert deliverables["properties"]["kind"]["enum"] == [
        "figure",
        "table",
        "dataset",
        "data",
        "derivation",
        "code",
        "note",
        "report",
        "other",
    ]
    _assert_string_or_string_list_schema(
        deliverables["properties"]["must_contain"],
        label="contract.deliverables[].must_contain",
    )

    acceptance_tests = contract_schema["properties"]["acceptance_tests"]["items"]
    _assert_closed_object(acceptance_tests, label="contract.acceptance_tests[]")
    assert acceptance_tests["properties"]["kind"]["enum"] == [
        "existence",
        "schema",
        "benchmark",
        "consistency",
        "cross_method",
        "limiting_case",
        "symmetry",
        "dimensional_analysis",
        "convergence",
        "oracle",
        "proxy",
        "reproducibility",
        "proof_hypothesis_coverage",
        "proof_parameter_coverage",
        "proof_quantifier_domain",
        "claim_to_proof_alignment",
        "lemma_dependency_closure",
        "counterexample_search",
        "human_review",
        "other",
    ]
    assert acceptance_tests["properties"]["automation"]["enum"] == ["automated", "hybrid", "human"]
    _assert_string_or_string_list_schema(
        acceptance_tests["properties"]["evidence_required"],
        label="contract.acceptance_tests[].evidence_required",
    )

    references = contract_schema["properties"]["references"]["items"]
    _assert_closed_object(references, label="contract.references[]")
    assert references["required"] == ["id", "locator", "why_it_matters"]
    assert references["properties"]["kind"]["enum"] == [
        "paper",
        "dataset",
        "prior_artifact",
        "spec",
        "user_anchor",
        "other",
    ]
    assert references["properties"]["role"]["enum"] == [
        "definition",
        "benchmark",
        "method",
        "must_consider",
        "background",
        "other",
    ]
    for field_name in ("aliases", "applies_to", "carry_forward_to"):
        _assert_string_or_string_list_schema(
            references["properties"][field_name],
            label=f"contract.references[].{field_name}",
        )
    _assert_enum_string_or_string_list_schema(
        references["properties"]["required_actions"],
        label="contract.references[].required_actions",
        enum_values=["read", "use", "compare", "cite", "avoid"],
    )

    links = contract_schema["properties"]["links"]["items"]
    _assert_closed_object(links, label="contract.links[]")
    assert links["properties"]["relation"]["enum"] == [
        "supports",
        "computes",
        "visualizes",
        "benchmarks",
        "depends_on",
        "evaluated_by",
        "proves",
        "uses_hypothesis",
        "depends_on_lemma",
        "other",
    ]
    _assert_string_or_string_list_schema(links["properties"]["verified_by"], label="contract.links[].verified_by")

    forbidden_proxies = contract_schema["properties"]["forbidden_proxies"]["items"]
    _assert_closed_object(forbidden_proxies, label="contract.forbidden_proxies[]")

    uncertainty_markers = _schema_object(contract_schema, contract_schema["properties"]["uncertainty_markers"])
    _assert_closed_object(uncertainty_markers, label="contract.uncertainty_markers")
    assert uncertainty_markers["required"] == ["weakest_anchors", "disconfirming_observations"]
    for field_name in (
        "weakest_anchors",
        "unvalidated_assumptions",
        "competing_explanations",
        "disconfirming_observations",
    ):
        _assert_string_or_string_list_schema(
            uncertainty_markers["properties"][field_name],
            label=f"contract.uncertainty_markers.{field_name}",
        )


def _identity_condition_for_check(run_request_schema: dict[str, object], check_identifier: str) -> list[tuple[str, list[str]]]:
    for clause in run_request_schema.get("allOf", []):
        if_branch = clause.get("if")
        if not isinstance(if_branch, dict):
            continue
        matches: list[tuple[str, list[str]]] = []
        for branch in if_branch.get("anyOf", []):
            if not isinstance(branch, dict):
                continue
            for field_name in ("check_key", "check_id"):
                field_schema = branch.get("properties", {}).get(field_name)
                if not isinstance(field_schema, dict):
                    continue
                enum_values = field_schema.get("enum")
                if isinstance(enum_values, list) and check_identifier in enum_values:
                    matches.append((field_name, [str(value) for value in enum_values]))
        if matches:
            return matches
    raise AssertionError(f"No identity condition found for {check_identifier!r}")


def test_run_contract_check_tool_description_surfaces_request_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "run_contract_check")

    assert "``request.check_key`` or ``request.check_id`` is required" in description
    assert "without leading or trailing" in description
    assert "whitespace" in description
    assert "``request.contract`` is optional" in description
    assert "``schema_version`` is required and must equal ``1``" in description
    assert "unknown top-level keys" in description
    assert "same-kind IDs must be unique" in description
    assert "contract context must stay consistent with metadata defaults" in description
    assert "metadata defaults and explicit" in description
    assert "metadata fields, so benchmark anchors" in description
    assert "``request.binding``, ``request.metadata``, and ``request.observed`` are each" in description
    assert "Singular/plural binding" in description
    assert "aliases (for example ``claim_id`` / ``claim_ids``) must match when both are" in description
    assert "may use either the canonical key or the numeric id" in description
    assert "``request.artifact_content``" in description
    assert "must be a string when present" in description
    assert "``required_request_fields``" in description
    assert "``optional_request_fields``" in description
    assert "``supported_binding_fields``" in description
    assert "``request_template``" in description
    assert "workflow scope labels, never contract IDs" in description
    assert "``references[].must_surface`` requires non-empty ``applies_to`` and ``required_actions`` lists" in description
    assert "make resolution ambiguous" in description


def test_suggest_contract_checks_tool_description_surfaces_contract_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "suggest_contract_checks")

    assert "``schema_version`` is required and must equal ``1``" in description
    assert "same-kind IDs must be unique" in description
    assert "contract context must stay" in description
    assert "consistent with metadata defaults and explicit metadata fields" in description
    assert "metadata defaults and explicit" in description
    assert "metadata fields, so" in description
    assert "benchmark anchors, regime labels, and family selections" in description
    assert "``active_checks`` is optional and must be ``list[str]``" in description
    assert "``already_active``" in description
    assert "``supported_binding_fields``" in description
    assert "``references[].carry_forward_to`` uses workflow" in description
    assert "scope labels, never contract IDs" in description
    assert "``references[].must_surface`` requires non-empty ``applies_to`` and ``required_actions`` lists" in description
    assert "``run_contract_check(request=...)``" in description
    assert description.count("same-kind IDs must be unique") == 1
    assert description.count("never contract IDs") == 1
    assert description.count("contract context must stay") == 1


def test_contract_tools_list_tools_expose_structured_request_schemas() -> None:
    from gpd.mcp.servers.verification_server import mcp

    run_schema = _tool_input_schema(mcp, "run_contract_check")
    run_request = _schema_object(run_schema, run_schema["properties"]["request"])

    assert run_request["additionalProperties"] is False
    check_key_requirement = next(
        branch
        for branch in run_request["anyOf"]
        if isinstance(branch, dict) and branch.get("required") == ["check_key"]
    )
    assert check_key_requirement["properties"]["check_key"]["type"] == "string"
    assert check_key_requirement["properties"]["check_key"]["pattern"] == r"^\S(?:[\s\S]*\S)?$"

    check_id_requirement = next(
        branch
        for branch in run_request["anyOf"]
        if isinstance(branch, dict) and branch.get("required") == ["check_id"]
    )
    assert check_id_requirement["properties"]["check_id"]["type"] == "string"
    assert check_id_requirement["properties"]["check_id"]["pattern"] == r"^\S(?:[\s\S]*\S)?$"

    assert {"check_key", "check_id", "contract", "binding", "metadata", "observed", "artifact_content"} <= set(
        run_request["properties"]
    )
    check_key = _schema_anyof_string(run_request["properties"]["check_key"])
    assert check_key["minLength"] == 1
    assert check_key["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert "enum" not in check_key
    assert any(
        isinstance(branch, dict) and branch.get("type") == "null"
        for branch in run_request["properties"]["check_key"]["anyOf"]
    )

    check_id = _schema_anyof_string(run_request["properties"]["check_id"])
    assert check_id["minLength"] == 1
    assert check_id["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert "enum" not in check_id
    assert any(
        isinstance(branch, dict) and branch.get("type") == "null"
        for branch in run_request["properties"]["check_id"]["anyOf"]
    )

    binding = _schema_anyof_object(run_request["properties"]["binding"])
    assert binding["additionalProperties"] is False
    assert {"claim_ids", "reference_ids", "forbidden_proxy_ids"} <= set(binding["properties"])
    assert len(binding["properties"]["claim_ids"]["anyOf"]) == 2
    assert binding["properties"]["claim_ids"]["anyOf"][0]["pattern"] == r"\S"
    assert binding["properties"]["claim_ids"]["anyOf"][1]["type"] == "array"
    assert binding["properties"]["claim_ids"]["anyOf"][1]["minItems"] == 1
    assert binding["properties"]["claim_ids"]["anyOf"][1]["items"]["type"] == "string"
    assert binding["properties"]["claim_ids"]["anyOf"][1]["items"]["minLength"] == 1
    assert binding["properties"]["claim_ids"]["anyOf"][1]["items"]["pattern"] == r"\S"

    direct_proxy_binding = _binding_condition_for_check(run_request, "contract.direct_proxy_consistency")
    assert {"claim_ids", "deliverable_ids", "acceptance_test_ids", "forbidden_proxy_ids"} <= set(
        direct_proxy_binding["properties"]
    )
    assert "reference_ids" not in direct_proxy_binding["properties"]

    benchmark_binding = _binding_condition_for_check(run_request, "contract.benchmark_reproduction")
    assert {"claim_ids", "deliverable_ids", "acceptance_test_ids", "reference_ids"} <= set(
        benchmark_binding["properties"]
    )
    assert "forbidden_proxy_ids" not in benchmark_binding["properties"]

    proof_binding = _binding_condition_for_check(run_request, "contract.proof_parameter_coverage")
    assert {"observable_ids", "claim_ids", "deliverable_ids", "acceptance_test_ids"} <= set(
        proof_binding["properties"]
    )
    assert "reference_ids" not in proof_binding["properties"]
    assert "forbidden_proxy_ids" not in proof_binding["properties"]

    metadata = _schema_anyof_object(run_request["properties"]["metadata"])
    assert {
        "source_reference_id",
        "allowed_families",
        "forbidden_families",
        "theorem_parameter_symbols",
        "hypothesis_ids",
        "quantifiers",
        "conclusion_clause_ids",
        "claim_statement",
    } <= set(metadata["properties"])
    assert metadata["properties"]["allowed_families"]["type"] == "array"
    assert metadata["properties"]["allowed_families"]["items"]["type"] == "string"
    assert metadata["properties"]["allowed_families"]["items"]["minLength"] == 1
    assert metadata["properties"]["allowed_families"]["items"]["pattern"] == r"\S"

    observed = _schema_anyof_object(run_request["properties"]["observed"])
    assert {
        "metric_value",
        "threshold_value",
        "selected_family",
        "bias_checked",
        "covered_hypothesis_ids",
        "missing_hypothesis_ids",
        "covered_parameter_symbols",
        "missing_parameter_symbols",
        "uncovered_quantifiers",
        "uncovered_conclusion_clause_ids",
        "quantifier_status",
        "scope_status",
        "counterexample_status",
    } <= set(observed["properties"])
    for field_name in ("observed_limit", "selected_family"):
        field_schema = _schema_anyof_string(observed["properties"][field_name])
        assert field_schema["minLength"] == 1
        assert field_schema["pattern"] == r"\S"
    for field_name in (
        "covered_hypothesis_ids",
        "missing_hypothesis_ids",
        "covered_parameter_symbols",
        "missing_parameter_symbols",
        "uncovered_quantifiers",
        "uncovered_conclusion_clause_ids",
    ):
        field_schema = observed["properties"][field_name]
        array_branch = next(
            branch for branch in field_schema["anyOf"] if isinstance(branch, dict) and branch.get("type") == "array"
        )
        assert array_branch["items"]["type"] == "string"
        assert array_branch["items"]["minLength"] == 1
        assert array_branch["items"]["pattern"] == r"\S"
        assert any(branch.get("type") == "null" for branch in field_schema["anyOf"] if isinstance(branch, dict))

    artifact_content = _schema_anyof_string(run_request["properties"]["artifact_content"])
    assert artifact_content["minLength"] == 1
    assert artifact_content["pattern"] == r"\S"

    benchmark_requirements = _request_requirement_for_check(run_request, "contract.benchmark_reproduction")
    assert set(benchmark_requirements["required"]) == {"observed"}
    assert "metadata" not in benchmark_requirements.get("properties", {})
    benchmark_observed = _schema_object(benchmark_requirements, benchmark_requirements["properties"]["observed"])
    assert set(benchmark_observed["required"]) == {"metric_value", "threshold_value"}

    limit_requirements = _request_requirement_for_check(run_request, "contract.limit_recovery")
    assert "metadata" not in limit_requirements.get("required", [])
    assert "metadata" not in limit_requirements.get("properties", {})

    fit_requirements = _request_requirement_for_check(run_request, "contract.fit_family_mismatch")
    assert set(fit_requirements["required"]) == {"observed"}
    assert "metadata" not in fit_requirements.get("properties", {})
    fit_observed = _schema_object(fit_requirements, fit_requirements["properties"]["observed"])
    assert fit_observed["required"] == ["selected_family"]

    estimator_requirements = _request_requirement_for_check(run_request, "contract.estimator_family_mismatch")
    assert set(estimator_requirements["required"]) == {"observed"}
    assert "metadata" not in estimator_requirements.get("properties", {})
    estimator_observed = _schema_object(estimator_requirements, estimator_requirements["properties"]["observed"])
    assert set(estimator_observed["required"]) == {"selected_family", "bias_checked", "calibration_checked"}

    proof_parameter_requirements = _request_requirement_for_check(run_request, "contract.proof_parameter_coverage")
    assert set(proof_parameter_requirements["required"]) == {"observed"}
    proof_parameter_observed = _schema_object(proof_parameter_requirements, proof_parameter_requirements["properties"]["observed"])
    assert proof_parameter_observed["required"] == ["covered_parameter_symbols"]

    proof_alignment_requirements = _request_requirement_for_check(run_request, "contract.claim_to_proof_alignment")
    assert set(proof_alignment_requirements["required"]) == {"observed"}
    proof_alignment_observed = _schema_object(proof_alignment_requirements, proof_alignment_requirements["properties"]["observed"])
    assert set(proof_alignment_observed["required"]) == {"scope_status", "uncovered_conclusion_clause_ids"}

    contract_schema = _schema_anyof_object(run_request["properties"]["contract"])
    _assert_contract_schema_sections_closed(contract_schema)
    assert set(contract_schema["required"]) == {"schema_version", "scope", "context_intake", "uncertainty_markers"}

    suggest_schema = _tool_input_schema(mcp, "suggest_contract_checks")
    contract_schema = _schema_anyof_object(suggest_schema["properties"]["contract"])
    _assert_contract_schema_sections_closed(contract_schema)
    assert set(contract_schema["required"]) == {"schema_version", "scope", "context_intake", "uncertainty_markers"}
    active_checks = suggest_schema["properties"]["active_checks"]
    assert active_checks["anyOf"][0]["type"] == "array"
    assert active_checks["anyOf"][0]["items"]["type"] == "string"
    assert active_checks["anyOf"][0]["items"]["minLength"] == 1
    assert active_checks["anyOf"][0]["items"]["pattern"] == r"\S"

    for field_name in ("source_reference_id", "regime_label", "expected_behavior", "declared_family", "claim_statement"):
        field_schema = _schema_anyof_string(metadata["properties"][field_name])
        assert field_schema["minLength"] == 1
        assert field_schema["pattern"] == r"\S"

    for field_name, expected_values in (
        ("quantifier_status", ["matched", "narrowed", "mismatched", "unclear"]),
        ("scope_status", ["matched", "narrower_than_claim", "mismatched", "unclear"]),
        ("counterexample_status", ["none_found", "counterexample_found", "not_attempted", "narrowed_claim"]),
    ):
        field_schema = observed["properties"][field_name]
        enum_branch = next(
            branch for branch in field_schema["anyOf"] if isinstance(branch, dict) and branch.get("type") == "string"
        )
        assert enum_branch["enum"] == expected_values
        assert any(branch.get("type") == "null" for branch in field_schema["anyOf"] if isinstance(branch, dict))

    benchmark_identity = _identity_condition_for_check(run_request, "contract.benchmark_reproduction")
    assert benchmark_identity == [
        ("check_key", ["contract.benchmark_reproduction", "5.16"]),
        ("check_id", ["contract.benchmark_reproduction", "5.16"]),
    ]

    limit_identity = _identity_condition_for_check(run_request, "contract.limit_recovery")
    assert limit_identity == [
        ("check_key", ["contract.limit_recovery", "5.15"]),
        ("check_id", ["contract.limit_recovery", "5.15"]),
    ]

    proof_identity = _identity_condition_for_check(run_request, "contract.proof_parameter_coverage")
    assert proof_identity == [
        ("check_key", ["contract.proof_parameter_coverage", "5.21"]),
        ("check_id", ["contract.proof_parameter_coverage", "5.21"]),
    ]


def test_patterns_tools_expose_domain_category_and_severity_enums() -> None:
    from gpd.core.patterns import VALID_CATEGORIES, VALID_DOMAINS, VALID_SEVERITIES
    from gpd.mcp.servers.patterns_server import mcp

    lookup_schema = _tool_input_schema(mcp, "lookup_pattern")
    lookup_domain = lookup_schema["properties"]["domain"]["anyOf"][0]
    lookup_category = lookup_schema["properties"]["category"]["anyOf"][0]
    assert lookup_domain["enum"] == sorted(VALID_DOMAINS)
    assert lookup_category["enum"] == sorted(VALID_CATEGORIES)

    add_schema = _tool_input_schema(mcp, "add_pattern")
    assert add_schema["properties"]["domain"]["enum"] == sorted(VALID_DOMAINS)
    assert add_schema["properties"]["category"]["enum"] == sorted(VALID_CATEGORIES)
    assert add_schema["properties"]["severity"]["enum"] == list(VALID_SEVERITIES)


def test_assert_convention_validate_description_surfaces_required_headers() -> None:
    from gpd.mcp.servers.conventions_server import mcp

    description = _tool_description(mcp, "assert_convention_validate")

    assert "Every derivation artifact must include at least one ASSERT_CONVENTION line." in description
    assert "Missing assertions are treated as invalid, not advisory" in description


def test_public_descriptors_surface_contract_and_optional_dependency_visibility() -> None:
    from gpd.mcp.builtin_servers import build_public_descriptors

    descriptors = build_public_descriptors()

    verification = descriptors["gpd-verification"]
    assert "contract payloads whose `schema_version` is required and must equal `1`" in verification["description"]
    assert "required_request_fields" in verification["description"]
    assert "optional_request_fields" in verification["description"]
    assert "request_template" in verification["description"]
    assert "supported binding fields" in verification["description"]
    for field in (
        "binding.observable_id(s)",
        "binding.claim_id(s)",
        "binding.deliverable_id(s)",
        "binding.acceptance_test_id(s)",
        "binding.reference_id(s)",
        "binding.forbidden_proxy_id(s)",
    ):
        assert field in verification["description"]
    assert "live semantic integrity rules" in verification["description"]
    assert "target resolution ambiguous" in verification["description"]
    assert "`references[].carry_forward_to` entries as workflow scope labels only" in verification["description"]
    assert "never contract IDs" in verification["description"]


@pytest.mark.parametrize(
    ("mcp_module", "expected_tools"),
    [
        ("gpd.mcp.servers.conventions_server", {"convention_lock_status", "convention_set", "convention_check", "convention_diff", "assert_convention_validate"}),
        ("gpd.mcp.servers.errors_mcp", {"get_error_class", "check_error_classes", "get_detection_strategy", "get_traceability", "list_error_classes"}),
        ("gpd.mcp.servers.patterns_server", {"lookup_pattern", "add_pattern", "promote_pattern", "seed_patterns", "list_domains"}),
        ("gpd.mcp.servers.protocols_server", {"get_protocol", "list_protocols", "route_protocol", "get_protocol_checkpoints"}),
        ("gpd.mcp.servers.skills_server", {"list_skills", "get_skill", "route_skill", "get_skill_index"}),
    ],
)
def test_non_verification_tools_publish_closed_input_schemas(mcp_module: str, expected_tools: set[str]) -> None:
    module = __import__(mcp_module, fromlist=["mcp"])

    tools = anyio.run(module.mcp.list_tools)

    names = {tool.name for tool in tools}
    assert expected_tools <= names
    for tool in tools:
        assert tool.inputSchema["additionalProperties"] is False, f"{tool.name} must reject unknown top-level keys"


def test_state_server_tools_publish_absolute_project_dir_schema() -> None:
    from gpd.mcp.servers import ABSOLUTE_PROJECT_DIR_SCHEMA
    from gpd.mcp.servers.state_server import mcp

    async def _load() -> dict[str, object]:
        tools = await mcp.list_tools()
        return {tool.name: tool.inputSchema for tool in tools}

    schemas = anyio.run(_load)

    for tool_name in ("get_state", "get_phase_info", "advance_plan", "get_progress", "validate_state", "run_health_check", "get_config"):
        project_dir = schemas[tool_name]["properties"]["project_dir"]
        for key, value in ABSOLUTE_PROJECT_DIR_SCHEMA.items():
            assert project_dir[key] == value


def test_state_workflow_docs_do_not_reference_dead_emit_phase_event_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    for rel_path in (
        "src/gpd/specs/workflows/plan-phase.md",
        "src/gpd/specs/workflows/execute-phase.md",
    ):
        text = (repo_root / rel_path).read_text(encoding="utf-8")
        assert "gpd-state_emit_phase_event" not in text
        assert "Phase Lifecycle Events" not in text


def test_conventions_server_tools_publish_same_absolute_project_dir_schema_as_state_server() -> None:
    from gpd.mcp.servers.conventions_server import mcp as conventions_mcp
    from gpd.mcp.servers.state_server import mcp as state_mcp

    async def _load() -> tuple[dict[str, object], dict[str, object]]:
        conventions_tools = await conventions_mcp.list_tools()
        state_tools = await state_mcp.list_tools()
        return (
            {tool.name: tool.inputSchema for tool in conventions_tools},
            {tool.name: tool.inputSchema for tool in state_tools},
        )

    conventions_schemas, state_schemas = anyio.run(_load)

    state_project_dir = state_schemas["get_state"]["properties"]["project_dir"]
    for tool_name in ("convention_lock_status", "convention_set"):
        assert conventions_schemas[tool_name]["properties"]["project_dir"] == state_project_dir


def test_public_protocols_infra_descriptor_matches_live_catalog_surface() -> None:
    descriptor = json.loads((Path(__file__).resolve().parents[2] / "infra" / "gpd-protocols.json").read_text(encoding="utf-8"))

    description = descriptor["description"]
    assert "live protocol catalog" in description
    assert "47 physics domains" not in description


def test_get_checklist_tool_description_mentions_full_live_registry() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "get_checklist")

    assert "currently 5.1-5.24" in description
    assert "5.1-5.14" not in description


def test_run_check_tool_description_surfaces_alias_and_contract_hint_support() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "run_check")

    assert "canonical check keys" in description
    assert "contract.limit_recovery" in description
    assert "required_request_fields" in description
    assert "optional_request_fields" in description
    assert "supported_binding_fields" in description
    assert "request_template" in description
    assert "run_contract_check" in description


def test_public_verification_infra_descriptor_surfaces_semantic_contract_rules() -> None:
    descriptor = json.loads(
        (Path(__file__).resolve().parents[2] / "infra" / "gpd-verification.json").read_text(encoding="utf-8")
    )

    description = descriptor["description"]
    assert "contract payloads whose `schema_version` is required and must equal `1`" in description
    assert "required_request_fields" in description
    assert "optional_request_fields" in description
    assert "request_template" in description
    assert "supported binding fields" in description
    for field in (
        "binding.observable_id(s)",
        "binding.claim_id(s)",
        "binding.deliverable_id(s)",
        "binding.acceptance_test_id(s)",
        "binding.reference_id(s)",
        "binding.forbidden_proxy_id(s)",
    ):
        assert field in description
    assert "live semantic integrity rules" in description
    assert "target resolution ambiguous" in description
    assert "`references[].carry_forward_to` entries as workflow scope labels only" in description
    assert "never contract IDs" in description
