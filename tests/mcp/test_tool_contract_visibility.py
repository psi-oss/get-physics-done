from __future__ import annotations

import json
from pathlib import Path

import anyio


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
    assert claims["required"] == ["id", "statement"]
    assert claims["properties"]["id"]["minLength"] == 1
    assert claims["properties"]["id"]["pattern"] == r"\S"
    for field_name in ("observables", "deliverables", "acceptance_tests", "references"):
        _assert_string_or_string_list_schema(claims["properties"][field_name], label=f"contract.claims[].{field_name}")

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
        "other",
    ]
    _assert_string_or_string_list_schema(links["properties"]["verified_by"], label="contract.links[].verified_by")

    forbidden_proxies = contract_schema["properties"]["forbidden_proxies"]["items"]
    _assert_closed_object(forbidden_proxies, label="contract.forbidden_proxies[]")

    uncertainty_markers = _schema_object(contract_schema, contract_schema["properties"]["uncertainty_markers"])
    _assert_closed_object(uncertainty_markers, label="contract.uncertainty_markers")
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
    assert "``request.contract`` is optional" in description
    assert "``schema_version`` defaults to ``1`` when omitted" in description
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
    assert "make resolution ambiguous" in description


def test_suggest_contract_checks_tool_description_surfaces_contract_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "suggest_contract_checks")

    assert "``schema_version`` defaults to ``1`` when omitted" in description
    assert "same-kind IDs must be unique" in description
    assert "contract context must stay consistent with metadata defaults" in description
    assert "metadata defaults and explicit" in description
    assert "metadata fields, so benchmark anchors" in description
    assert "``active_checks`` is optional and must be ``list[str]``" in description
    assert "``already_active``" in description
    assert "``supported_binding_fields``" in description
    assert "workflow scope labels, never contract IDs" in description
    assert "``run_contract_check(request=...)``" in description


def test_contract_tools_list_tools_expose_structured_request_schemas() -> None:
    from gpd.mcp.servers.verification_server import mcp

    run_schema = _tool_input_schema(mcp, "run_contract_check")
    run_request = _schema_object(run_schema, run_schema["properties"]["request"])

    assert run_request["additionalProperties"] is False
    assert {"required": ["check_key"]} in run_request["anyOf"]
    assert {"required": ["check_id"]} in run_request["anyOf"]
    assert {"check_key", "check_id", "contract", "binding", "metadata", "observed", "artifact_content"} <= set(
        run_request["properties"]
    )
    assert run_request["properties"]["check_key"]["enum"] == [
        "contract.limit_recovery",
        "5.15",
        "contract.benchmark_reproduction",
        "5.16",
        "contract.direct_proxy_consistency",
        "5.17",
        "contract.fit_family_mismatch",
        "5.18",
        "contract.estimator_family_mismatch",
        "5.19",
    ]
    assert run_request["properties"]["check_id"]["enum"] == run_request["properties"]["check_key"]["enum"]

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

    metadata = _schema_anyof_object(run_request["properties"]["metadata"])
    assert {"source_reference_id", "allowed_families", "forbidden_families"} <= set(metadata["properties"])
    assert metadata["properties"]["allowed_families"]["type"] == "array"
    assert metadata["properties"]["allowed_families"]["items"]["type"] == "string"
    assert metadata["properties"]["allowed_families"]["items"]["minLength"] == 1
    assert metadata["properties"]["allowed_families"]["items"]["pattern"] == r"\S"

    observed = _schema_anyof_object(run_request["properties"]["observed"])
    assert {"metric_value", "threshold_value", "selected_family", "bias_checked"} <= set(observed["properties"])
    for field_name in ("observed_limit", "selected_family"):
        field_schema = _schema_anyof_string(observed["properties"][field_name])
        assert field_schema["minLength"] == 1
        assert field_schema["pattern"] == r"\S"

    artifact_content = _schema_anyof_string(run_request["properties"]["artifact_content"])
    assert artifact_content["minLength"] == 1
    assert artifact_content["pattern"] == r"\S"

    contract_schema = _schema_anyof_object(run_request["properties"]["contract"])
    _assert_contract_schema_sections_closed(contract_schema)

    suggest_schema = _tool_input_schema(mcp, "suggest_contract_checks")
    contract_schema = _schema_anyof_object(suggest_schema["properties"]["contract"])
    _assert_contract_schema_sections_closed(contract_schema)
    active_checks = suggest_schema["properties"]["active_checks"]
    assert active_checks["anyOf"][0]["type"] == "array"
    assert active_checks["anyOf"][0]["items"]["type"] == "string"
    assert active_checks["anyOf"][0]["items"]["minLength"] == 1
    assert active_checks["anyOf"][0]["items"]["pattern"] == r"\S"

    for field_name in ("source_reference_id", "regime_label", "expected_behavior", "declared_family"):
        field_schema = _schema_anyof_string(metadata["properties"][field_name])
        assert field_schema["minLength"] == 1
        assert field_schema["pattern"] == r"\S"

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
    assert "structured request objects or schema_version=1 contract payloads" in verification["description"]
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

    conventions = descriptors["gpd-conventions"]
    assert "ASSERT_CONVENTION validation" in conventions["description"]
    assert "Every derivation artifact must carry at least one ASSERT_CONVENTION header" in conventions["description"]

    protocols = descriptors["gpd-protocols"]
    assert "live protocol catalog" in protocols["description"]
    assert "47 physics domains" not in protocols["description"]

    arxiv = descriptors["gpd-arxiv"]
    assert arxiv["optional"] is True
    assert arxiv["availability"] == "conditional"
    assert "optional Python module 'arxiv_mcp_server'" in arxiv["availability_condition"]
    assert "Optional arXiv paper search, retrieval, and analysis" in arxiv["description"]
    assert arxiv["prompts"] == ["deep-paper-analysis"]


def test_public_protocols_infra_descriptor_matches_live_catalog_surface() -> None:
    descriptor = json.loads((Path(__file__).resolve().parents[2] / "infra" / "gpd-protocols.json").read_text(encoding="utf-8"))

    description = descriptor["description"]
    assert "live protocol catalog" in description
    assert "47 physics domains" not in description


def test_get_checklist_tool_description_mentions_full_live_registry() -> None:
    from gpd.mcp.servers.verification_server import mcp

    description = _tool_description(mcp, "get_checklist")

    assert "currently 5.1-5.19" in description
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
    assert "structured request objects or schema_version=1 contract payloads" in description
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
