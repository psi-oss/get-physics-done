from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import anyio
import pytest
from pydantic import BaseModel, ConfigDict


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


def _schema_anyof_array(schema_fragment: dict[str, object]) -> dict[str, object]:
    if schema_fragment.get("type") == "array":
        return schema_fragment
    for branch in schema_fragment.get("anyOf", []):
        if isinstance(branch, dict) and branch.get("type") == "array":
            return branch
    raise AssertionError(f"No array branch found in {schema_fragment!r}")


def _assert_recoverable_enum_string_schema(
    schema_fragment: dict[str, object],
    *,
    label: str,
    enum_values: list[str],
) -> None:
    if schema_fragment.get("type") == "string":
        assert schema_fragment["enum"] == enum_values
        return

    assert "anyOf" in schema_fragment, f"{label} must publish case-only enum salvage semantics"
    exact_branch = next(
        branch for branch in schema_fragment["anyOf"] if isinstance(branch, dict) and branch.get("type") == "string" and "enum" in branch
    )
    pattern_branch = next(
        branch
        for branch in schema_fragment["anyOf"]
        if isinstance(branch, dict) and branch.get("type") == "string" and "pattern" in branch
    )
    assert exact_branch["enum"] == enum_values
    assert pattern_branch["pattern"].startswith("^(?:")
    assert pattern_branch["pattern"].endswith(")$")


def _assert_string_list_schema(schema_fragment: dict[str, object], *, label: str) -> None:
    array_branch = _schema_anyof_array(schema_fragment)
    if "anyOf" in schema_fragment:
        string_branch = _schema_anyof_string(schema_fragment)
        assert string_branch["minLength"] == 1
        assert string_branch["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert array_branch["items"]["type"] == "string"
    if "minLength" in array_branch["items"]:
        assert array_branch["items"]["minLength"] == 1
    if "pattern" in array_branch["items"]:
        assert array_branch["items"]["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    if "uniqueItems" in array_branch:
        assert array_branch["uniqueItems"] is True


def _assert_enum_string_list_schema(
    schema_fragment: dict[str, object],
    *,
    label: str,
    enum_values: list[str],
) -> None:
    array_branch = _schema_anyof_array(schema_fragment)
    if "anyOf" in schema_fragment:
        scalar_branch = next(
            branch for branch in schema_fragment["anyOf"] if isinstance(branch, dict) and branch.get("type") != "array"
        )
        _assert_recoverable_enum_string_schema(scalar_branch, label=f"{label} scalar branch", enum_values=enum_values)
    _assert_recoverable_enum_string_schema(array_branch["items"], label=f"{label} items", enum_values=enum_values)
    assert array_branch["uniqueItems"] is True


def _assert_closed_object(schema_fragment: dict[str, object], *, label: str) -> None:
    assert schema_fragment["additionalProperties"] is False, f"{label} must reject unknown top-level keys"


def _assert_strict_required_schema_fragment(schema_fragment: dict[str, object], *, label: str) -> None:
    any_of = schema_fragment.get("anyOf")
    if isinstance(any_of, list):
        assert not any(
            isinstance(branch, dict) and branch.get("type") == "null"
            for branch in any_of
        ), f"{label} must not allow null when schema-required"
        for branch in any_of:
            if not isinstance(branch, dict):
                continue
            if branch.get("type") == "array":
                assert branch.get("minItems") == 1, f"{label} must not allow empty arrays when schema-required"
                assert branch["items"]["type"] == "string"
                assert branch["items"]["minLength"] == 1
                assert branch["items"]["pattern"] == r"\S"
            if branch.get("type") == "string":
                if "enum" in branch:
                    continue
                assert branch["minLength"] == 1
                assert branch["pattern"] == r"\S"
        return

    if schema_fragment.get("type") == "array":
        assert schema_fragment.get("minItems") == 1, f"{label} must not allow empty arrays when schema-required"
        assert schema_fragment["items"]["type"] == "string"
        assert schema_fragment["items"]["minLength"] == 1
        assert schema_fragment["items"]["pattern"] == r"\S"
        return

    if schema_fragment.get("type") == "string":
        if "enum" in schema_fragment:
            return
        assert schema_fragment["minLength"] == 1
        assert schema_fragment["pattern"] == r"\S"


def test_strict_required_schema_fragment_rejects_permissive_anyof_array_branch() -> None:
    with pytest.raises(AssertionError, match="must not allow empty arrays when schema-required"):
        _assert_strict_required_schema_fragment(
            {
                "anyOf": [
                    {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "pattern": r"\S"},
                    }
                ]
            },
            label="proof metadata branch",
        )


def _proof_contract_fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": {
            "question": "Does the proof establish the theorem for all r_0 > 0?",
            "in_scope": ["proof-obligation audit"],
        },
        "context_intake": {
            "must_read_refs": ["ref-proof"],
            "crucial_inputs": ["Track every theorem parameter and conclusion clause through the proof."],
        },
        "observables": [
            {
                "id": "obs-proof",
                "name": "main theorem proof obligation",
                "kind": "proof_obligation",
                "definition": "Formal proof obligation for the main theorem",
            }
        ],
        "claims": [
            {
                "id": "claim-theorem",
                "statement": "For all r_0 > 0, the full theorem holds.",
                "claim_kind": "theorem",
                "observables": ["obs-proof"],
                "deliverables": ["deliv-summary"],
                "acceptance_tests": [
                    "test-proof-param",
                    "test-proof-align",
                    "test-proof-counterexample",
                ],
                "references": ["ref-proof"],
                "parameters": [
                    {"symbol": "r_0", "domain_or_type": "positive real", "aliases": ["r0"], "required_in_proof": True},
                    {"symbol": "n", "domain_or_type": "integer", "required_in_proof": True},
                ],
                "hypotheses": [{"id": "hyp-main", "text": "r_0 > 0", "required_in_proof": True}],
                "quantifiers": ["for all r_0 > 0"],
                "conclusion_clauses": [{"id": "conclusion-main", "text": "the theorem holds"}],
                "proof_deliverables": ["deliv-proof"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-summary",
                "kind": "report",
                "description": "Theorem summary note",
                "must_contain": ["theorem statement"],
            },
            {
                "id": "deliv-proof",
                "kind": "derivation",
                "description": "Formal theorem proof",
                "must_contain": ["proof audit"],
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-proof-param",
                "subject": "claim-theorem",
                "kind": "proof_parameter_coverage",
                "procedure": "Audit theorem parameters against the proof body.",
                "pass_condition": "All theorem parameters remain present in the proof.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-align",
                "subject": "claim-theorem",
                "kind": "claim_to_proof_alignment",
                "procedure": "Audit the theorem statement against the proof conclusion.",
                "pass_condition": "The proof establishes the theorem exactly as stated.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-counterexample",
                "subject": "claim-theorem",
                "kind": "counterexample_search",
                "procedure": "Attempt an adversarial counterexample search.",
                "pass_condition": "No counterexample or narrowed claim is found.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
        ],
        "references": [
            {
                "id": "ref-proof",
                "kind": "paper",
                "locator": "doi:10.1000/proof",
                "role": "definition",
                "why_it_matters": "Defines the theorem statement and notation.",
                "applies_to": ["claim-theorem"],
                "must_surface": True,
                "required_actions": ["read"],
            }
        ],
        "forbidden_proxies": [
            {
                "id": "fp-proof",
                "subject": "claim-theorem",
                "proxy": "Algebraic consistency without theorem alignment",
                "reason": "The theorem still requires statement-to-proof alignment.",
            }
        ],
        "links": [],
        "uncertainty_markers": {
            "weakest_anchors": ["A theorem parameter could disappear from the proof body."],
            "disconfirming_observations": ["The proof only covers the r_0 = 0 special case."],
        },
    }


def _binding_condition_for_check(run_request_schema: dict[str, object], check_identifier: str) -> dict[str, object]:
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
                binding_schema = clause.get("then", {}).get("properties", {}).get("binding")
                if isinstance(binding_schema, dict):
                    return _schema_anyof_object(binding_schema)
    raise AssertionError(f"No binding condition found for {check_identifier!r}")


def _request_requirement_for_check(run_request_schema: dict[str, object], check_identifier: str) -> dict[str, object] | None:
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


def _assert_request_requirement_schema(
    requirement: dict[str, object] | None,
    *,
    required: list[str],
    section_required: dict[str, list[str]] | None = None,
    anyof: list[dict[str, object]] | None = None,
) -> None:
    assert requirement is not None
    assert requirement["required"] == required
    if section_required:
        assert "properties" in requirement
        for section_name, fields in section_required.items():
            section_schema = requirement["properties"][section_name]
            assert section_schema["required"] == fields
            assert "properties" in section_schema
            for field_name in fields:
                _assert_strict_required_schema_fragment(
                    section_schema["properties"][field_name],
                    label=f"request requirement {section_name}.{field_name}",
                )
    for field_name in required:
        if "properties" not in requirement or field_name not in requirement["properties"]:
            continue
        _assert_strict_required_schema_fragment(
            requirement["properties"][field_name],
            label=f"request requirement {field_name}",
        )
    if anyof is None:
        assert "anyOf" not in requirement
        return

    assert len(requirement["anyOf"]) == len(anyof)
    for branch, expected_branch in zip(requirement["anyOf"], anyof, strict=True):
        assert branch["required"] == expected_branch["required"]
        if "section_required" in expected_branch:
            assert "properties" in branch
            for section_name, fields in expected_branch["section_required"].items():
                section_schema = branch["properties"][section_name]
                assert section_schema["required"] == fields


def _assert_contract_schema_sections_closed(contract_schema: dict[str, object]) -> None:
    _assert_closed_object(contract_schema, label="contract")
    assert {"schema_version", "scope", "claims", "references"} <= set(contract_schema["properties"])

    scope = _schema_object(contract_schema, contract_schema["properties"]["scope"])
    _assert_closed_object(scope, label="contract.scope")
    assert scope["required"] == ["question"]
    question_schema = _schema_anyof_string(scope["properties"]["question"])
    assert question_schema["type"] == "string"
    for field_name in ("in_scope", "out_of_scope", "unresolved_questions"):
        _assert_string_list_schema(scope["properties"][field_name], label=f"contract.scope.{field_name}")

    context_intake = _schema_object(contract_schema, contract_schema["properties"]["context_intake"])
    _assert_closed_object(context_intake, label="contract.context_intake")
    if "minProperties" in context_intake:
        assert context_intake["minProperties"] == 1
    for field_name in (
        "must_read_refs",
        "must_include_prior_outputs",
        "user_asserted_anchors",
        "known_good_baselines",
        "context_gaps",
        "crucial_inputs",
    ):
        _assert_string_list_schema(
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
        _assert_string_list_schema(
            approach_policy["properties"][field_name],
            label=f"contract.approach_policy.{field_name}",
        )

    claims = contract_schema["properties"]["claims"]["items"]
    _assert_closed_object(claims, label="contract.claims[]")
    assert {"id", "statement"} <= set(claims["required"])
    claim_id_schema = _schema_anyof_string(claims["properties"]["id"])
    assert claim_id_schema["type"] == "string"
    _assert_recoverable_enum_string_schema(
        claims["properties"]["claim_kind"],
        label="contract.claims[].claim_kind",
        enum_values=[
            "theorem",
            "lemma",
            "corollary",
            "proposition",
            "result",
            "claim",
            "other",
        ],
    )
    for field_name in ("observables", "deliverables", "acceptance_tests", "references", "quantifiers", "proof_deliverables"):
        _assert_string_list_schema(claims["properties"][field_name], label=f"contract.claims[].{field_name}")
    parameters = claims["properties"]["parameters"]["items"]
    _assert_closed_object(parameters, label="contract.claims[].parameters[]")
    _assert_string_list_schema(parameters["properties"]["aliases"], label="contract.claims[].parameters[].aliases")
    hypotheses = claims["properties"]["hypotheses"]["items"]
    _assert_closed_object(hypotheses, label="contract.claims[].hypotheses[]")
    _assert_string_list_schema(hypotheses["properties"]["symbols"], label="contract.claims[].hypotheses[].symbols")
    conclusion_clauses = claims["properties"]["conclusion_clauses"]["items"]
    _assert_closed_object(conclusion_clauses, label="contract.claims[].conclusion_clauses[]")
    if "allOf" not in claims:
        return
    proof_claim_condition = claims["allOf"][0]
    _assert_recoverable_enum_string_schema(
        proof_claim_condition["if"]["properties"]["claim_kind"],
        label="contract.claims[].proof condition claim_kind",
        enum_values=[
            "theorem",
            "lemma",
            "corollary",
            "proposition",
            "claim",
        ],
    )
    assert proof_claim_condition["then"]["required"] == [
        "proof_deliverables",
        "parameters",
        "hypotheses",
        "conclusion_clauses",
    ]
    assert proof_claim_condition["then"]["properties"]["parameters"]["minItems"] == 1
    assert proof_claim_condition["then"]["properties"]["hypotheses"]["minItems"] == 1
    assert proof_claim_condition["then"]["properties"]["conclusion_clauses"]["minItems"] == 1
    assert "statement is theorem-like" in claims["description"]
    assert "`proof_obligation` target" in claims["description"]
    assert "Do not rely on runtime inference" in claims["description"]

    observables = contract_schema["properties"]["observables"]["items"]
    _assert_closed_object(observables, label="contract.observables[]")
    _assert_recoverable_enum_string_schema(
        observables["properties"]["kind"],
        label="contract.observables[].kind",
        enum_values=[
            "scalar",
            "curve",
            "map",
            "classification",
            "proof_obligation",
            "other",
        ],
    )
    for field_name in ("regime", "units"):
        field_schema = observables["properties"][field_name]
        assert len(field_schema["anyOf"]) == 2
        string_branch = _schema_anyof_string(field_schema)
        assert string_branch["minLength"] == 1
        assert string_branch["pattern"] == r"\S"
        assert any(branch.get("type") == "null" for branch in field_schema["anyOf"] if isinstance(branch, dict))

    deliverables = contract_schema["properties"]["deliverables"]["items"]
    _assert_closed_object(deliverables, label="contract.deliverables[]")
    _assert_recoverable_enum_string_schema(
        deliverables["properties"]["kind"],
        label="contract.deliverables[].kind",
        enum_values=[
            "figure",
            "table",
            "dataset",
            "data",
            "derivation",
            "code",
            "note",
            "report",
            "other",
        ],
    )
    _assert_string_list_schema(
        deliverables["properties"]["must_contain"],
        label="contract.deliverables[].must_contain",
    )

    acceptance_tests = contract_schema["properties"]["acceptance_tests"]["items"]
    _assert_closed_object(acceptance_tests, label="contract.acceptance_tests[]")
    _assert_recoverable_enum_string_schema(
        acceptance_tests["properties"]["kind"],
        label="contract.acceptance_tests[].kind",
        enum_values=[
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
        ],
    )
    _assert_recoverable_enum_string_schema(
        acceptance_tests["properties"]["automation"],
        label="contract.acceptance_tests[].automation",
        enum_values=["automated", "hybrid", "human"],
    )
    _assert_string_list_schema(
        acceptance_tests["properties"]["evidence_required"],
        label="contract.acceptance_tests[].evidence_required",
    )

    references = contract_schema["properties"]["references"]["items"]
    _assert_closed_object(references, label="contract.references[]")
    assert references["required"] == ["id", "locator", "why_it_matters"]
    _assert_recoverable_enum_string_schema(
        references["properties"]["kind"],
        label="contract.references[].kind",
        enum_values=["paper", "dataset", "prior_artifact", "spec", "user_anchor", "other"],
    )
    _assert_recoverable_enum_string_schema(
        references["properties"]["role"],
        label="contract.references[].role",
        enum_values=["definition", "benchmark", "method", "must_consider", "background", "other"],
    )
    for field_name in ("aliases", "applies_to", "carry_forward_to"):
        _assert_string_list_schema(
            references["properties"][field_name],
            label=f"contract.references[].{field_name}",
        )
    _assert_enum_string_list_schema(
        references["properties"]["required_actions"],
        label="contract.references[].required_actions",
        enum_values=["read", "use", "compare", "cite", "avoid"],
    )

    links = contract_schema["properties"]["links"]["items"]
    _assert_closed_object(links, label="contract.links[]")
    _assert_recoverable_enum_string_schema(
        links["properties"]["relation"],
        label="contract.links[].relation",
        enum_values=[
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
        ],
    )
    _assert_string_list_schema(links["properties"]["verified_by"], label="contract.links[].verified_by")

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
        _assert_string_list_schema(
            uncertainty_markers["properties"][field_name],
            label=f"contract.uncertainty_markers.{field_name}",
        )


def _identity_condition_for_check(run_request_schema: dict[str, object], check_identifier: str) -> list[tuple[str, list[str]]]:
    for clause in run_request_schema.get("allOf", []):
        if_branch = clause.get("if")
        if not isinstance(if_branch, dict):
            continue
        matches: list[tuple[str, list[str]]] = []
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
                matches.append(("check_key", [str(value) for value in enum_values]))
        if matches:
            return matches
    raise AssertionError(f"No identity condition found for {check_identifier!r}")


def _identity_requirement_branches_for_check(
    run_request_schema: dict[str, object],
    check_identifier: str,
) -> list[tuple[str, list[str], list[str]]]:
    for clause in run_request_schema.get("allOf", []):
        if_branch = clause.get("if")
        if not isinstance(if_branch, dict):
            continue
        matches: list[tuple[str, list[str], list[str]]] = []
        candidate_branches = if_branch.get("anyOf", [])
        if not candidate_branches:
            candidate_branches = [if_branch]
        for branch in candidate_branches:
            if not isinstance(branch, dict):
                continue
            required = branch.get("required")
            if not isinstance(required, list) or len(required) != 1:
                continue
            field_name = required[0]
            if field_name != "check_key":
                continue
            field_schema = branch.get("properties", {}).get(field_name)
            if not isinstance(field_schema, dict):
                continue
            enum_values = field_schema.get("enum")
            if isinstance(enum_values, list) and check_identifier in enum_values:
                matches.append((field_name, [str(value) for value in required], [str(value) for value in enum_values]))
        if matches:
            return matches
    raise AssertionError(f"No identity requirement branches found for {check_identifier!r}")


def test_run_contract_check_tool_description_surfaces_request_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp
    from gpd.mcp.verification_contract_policy import verification_contract_surface_summary_text

    description = _tool_description(mcp, "run_contract_check")

    assert "full request contract lives on the ``request`` input schema itself" in description
    assert "``request.contract`` is optional" in description
    assert "``project_dir`` is optional" in description
    assert "absolute project root" in description
    assert verification_contract_surface_summary_text() in description


def test_suggest_contract_checks_tool_description_surfaces_contract_requirements() -> None:
    from gpd.mcp.servers.verification_server import mcp
    from gpd.mcp.verification_contract_policy import verification_contract_surface_summary_text

    description = _tool_description(mcp, "suggest_contract_checks")

    assert "``project_dir`` is optional" in description
    assert "absolute project root" in description
    assert "``active_checks`` is optional and must be ``list[str]``" in description
    assert "``already_active``" in description
    assert "``run_contract_check(request=...)``" in description
    assert verification_contract_surface_summary_text() in description


def test_contract_tools_list_tools_expose_structured_request_schemas() -> None:
    from gpd.mcp.servers import ABSOLUTE_PROJECT_DIR_SCHEMA
    from gpd.mcp.servers.verification_server import list_verification_checks, mcp

    run_schema = _tool_input_schema(mcp, "run_contract_check")
    run_request = _schema_object(run_schema, run_schema["properties"]["request"])
    assert run_schema["properties"]["project_dir"]["anyOf"] == [ABSOLUTE_PROJECT_DIR_SCHEMA, {"type": "null"}]
    assert run_schema["properties"]["project_dir"]["default"] is None

    assert run_request["additionalProperties"] is False
    check_key_requirement = next(
        branch
        for branch in run_request["anyOf"]
        if isinstance(branch, dict) and branch.get("required") == ["check_key"]
    )
    expected_identifiers = {
        str(entry["check_key"])
        for entry in list_verification_checks()
        if entry.get("contract_aware")
    } | {
        str(entry["check_id"])
        for entry in list_verification_checks()
        if entry.get("contract_aware")
    }
    assert check_key_requirement["properties"]["check_key"]["type"] == "string"
    assert check_key_requirement["properties"]["check_key"]["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert set(check_key_requirement["properties"]["check_key"]["enum"]) == expected_identifiers

    assert {"check_key", "contract", "binding", "metadata", "observed", "artifact_content"} <= set(
        run_request["properties"]
    )
    assert "Closed `run_contract_check` request object." in run_request["description"]
    assert "`schema_required_request_fields`" in run_request["description"]
    assert "`schema_required_request_anyof_fields`" in run_request["description"]
    assert "`supported_binding_fields`" in run_request["description"]
    assert "`request_template`" in run_request["description"]
    assert "starter `request_template`" in run_request["description"]
    assert "safe `request_template`" not in run_request["description"]
    contract_schema = run_request["properties"]["contract"]
    contract_description = str(contract_schema.get("description", ""))
    for branch in contract_schema.get("anyOf", []):
        contract_description += " " + str(branch.get("description", ""))
    assert "salvage" not in contract_description.lower()
    assert "Contract payload rules" in contract_description
    assert "check_id" not in run_request["properties"]
    check_key = _schema_anyof_string(run_request["properties"]["check_key"])
    assert check_key["minLength"] == 1
    assert check_key["pattern"] == r"^\S(?:[\s\S]*\S)?$"
    assert set(check_key["enum"]) == expected_identifiers
    assert any(
        isinstance(branch, dict) and branch.get("type") == "null"
        for branch in run_request["properties"]["check_key"]["anyOf"]
    )

    binding = _schema_anyof_object(run_request["properties"]["binding"])
    assert binding["additionalProperties"] is False
    assert {"observable_ids", "claim_ids", "deliverable_ids", "acceptance_test_ids", "reference_ids", "forbidden_proxy_ids"} == set(
        binding["properties"]
    )
    for field_name, field_schema in binding["properties"].items():
        assert field_schema["type"] == "array", field_name
        assert field_schema["minItems"] == 1, field_name
        assert field_schema["items"]["type"] == "string", field_name
        assert field_schema["items"]["minLength"] == 1, field_name
        assert field_schema["items"]["pattern"] == r"\S", field_name
        assert field_schema["uniqueItems"] is True, field_name

    direct_proxy_binding = _binding_condition_for_check(run_request, "contract.direct_proxy_consistency")
    assert {"claim_ids", "deliverable_ids", "acceptance_test_ids", "forbidden_proxy_ids"} == set(
        direct_proxy_binding["properties"]
    )
    assert "reference_ids" not in direct_proxy_binding["properties"]

    benchmark_binding = _binding_condition_for_check(run_request, "contract.benchmark_reproduction")
    assert {"claim_ids", "deliverable_ids", "acceptance_test_ids", "reference_ids"} == set(
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
    allowed_families_schema = metadata["properties"]["allowed_families"]
    allowed_families_array = _schema_anyof_array(allowed_families_schema)
    assert allowed_families_array["items"]["type"] == "string"
    assert allowed_families_array["items"]["minLength"] == 1
    assert allowed_families_array["items"]["pattern"] == r"\S"
    assert any(
        isinstance(branch, dict) and branch.get("type") == "null"
        for branch in allowed_families_schema.get("anyOf", [])
    )

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

    contract_schema = _schema_anyof_object(run_request["properties"]["contract"])
    references = contract_schema["properties"]["references"]
    reference_item = references["items"]
    assert "literature, dataset, or artifact anchor" in reference_item["description"]
    assert reference_item["additionalProperties"] is False
    assert reference_item["properties"]["must_surface"]["type"] == "boolean"

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.benchmark_reproduction"),
        required=["observed"],
        section_required={
            "observed": ["metric_value", "threshold_value"],
        },
        anyof=[
            {
                "required": ["metadata"],
                "section_required": {
                    "metadata": ["source_reference_id"],
                },
            },
            {
                "required": ["contract"],
            },
        ],
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.limit_recovery"),
        required=["metadata"],
        section_required={
            "metadata": ["regime_label", "expected_behavior"],
        },
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.fit_family_mismatch"),
        required=["metadata", "observed"],
        section_required={
            "metadata": ["declared_family"],
            "observed": ["selected_family"],
        },
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.estimator_family_mismatch"),
        required=["metadata", "observed"],
        section_required={
            "metadata": ["declared_family"],
            "observed": ["selected_family", "bias_checked", "calibration_checked"],
        },
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.proof_hypothesis_coverage"),
        required=["contract", "metadata", "observed"],
        section_required={
            "metadata": ["hypothesis_ids"],
            "observed": ["covered_hypothesis_ids"],
        },
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.proof_parameter_coverage"),
        required=["contract", "metadata", "observed"],
        section_required={
            "metadata": ["theorem_parameter_symbols"],
            "observed": ["covered_parameter_symbols"],
        },
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.proof_quantifier_domain"),
        required=["contract", "observed"],
        section_required={
            "observed": ["quantifier_status", "scope_status"],
        },
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.claim_to_proof_alignment"),
        required=["contract", "observed"],
        section_required={
            "observed": ["scope_status"],
        },
        anyof=[
            {
                "required": ["metadata"],
                "section_required": {"metadata": ["claim_statement"]},
            },
            {
                "required": ["metadata", "observed"],
                "section_required": {
                    "metadata": ["conclusion_clause_ids"],
                    "observed": ["uncovered_conclusion_clause_ids"],
                },
            },
        ],
    )

    _assert_request_requirement_schema(
        _request_requirement_for_check(run_request, "contract.counterexample_search"),
        required=["contract", "observed"],
        section_required={
            "observed": ["counterexample_status"],
        },
    )

    contract_schema = _schema_anyof_object(run_request["properties"]["contract"])
    _assert_contract_schema_sections_closed(contract_schema)
    assert "scope" in contract_schema["required"]
    for field_name in ("claims", "deliverables", "acceptance_tests", "references", "forbidden_proxies", "links"):
        assert "minItems" not in contract_schema["properties"][field_name]
    assert "schema_version" in contract_schema["description"]
    assert "suggest_contract_checks" in contract_schema["description"]

    suggest_schema = _tool_input_schema(mcp, "suggest_contract_checks")
    assert suggest_schema["properties"]["project_dir"]["anyOf"] == [ABSOLUTE_PROJECT_DIR_SCHEMA, {"type": "null"}]
    assert suggest_schema["properties"]["project_dir"]["default"] is None
    contract_schema = _schema_anyof_object(suggest_schema["properties"]["contract"])
    _assert_contract_schema_sections_closed(contract_schema)
    assert "scope" in contract_schema["required"]
    for field_name in ("claims", "deliverables", "acceptance_tests", "references", "forbidden_proxies", "links"):
        assert "minItems" not in contract_schema["properties"][field_name]
    assert "schema_version" in contract_schema["description"]
    assert "suggest_contract_checks" in contract_schema["description"]
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
    ]

    limit_identity = _identity_condition_for_check(run_request, "contract.limit_recovery")
    assert limit_identity == [
        ("check_key", ["contract.limit_recovery", "5.15"]),
    ]

    proof_identity = _identity_condition_for_check(run_request, "contract.proof_parameter_coverage")
    assert proof_identity == [
        ("check_key", ["contract.proof_parameter_coverage", "5.21"]),
    ]

    proof_requirement = _request_requirement_for_check(run_request, "contract.proof_hypothesis_coverage")
    assert proof_requirement["properties"]["contract"]["description"].startswith("Contract payload rules:")
    assert "hypothesis_ids" in proof_requirement["properties"]["metadata"]["properties"]
    assert "covered_hypothesis_ids" in proof_requirement["properties"]["observed"]["properties"]

    for check_identifier in (
        "contract.benchmark_reproduction",
        "contract.limit_recovery",
        "contract.fit_family_mismatch",
        "contract.estimator_family_mismatch",
        "contract.proof_hypothesis_coverage",
        "contract.proof_parameter_coverage",
        "contract.proof_quantifier_domain",
        "contract.claim_to_proof_alignment",
        "contract.counterexample_search",
    ):
        for field_name, required, enum_values in _identity_requirement_branches_for_check(run_request, check_identifier):
            assert required == [field_name]
            assert check_identifier in enum_values


def test_suggest_contract_checks_exposes_claim_alignment_branches() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_proof_contract_fixture())
    alignment = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.claim_to_proof_alignment")

    assert alignment["required_request_fields"] == ["contract", "observed.scope_status"]
    assert alignment["schema_required_request_fields"] == ["contract", "observed.scope_status"]
    assert alignment["schema_required_request_anyof_fields"] == [
        ["metadata.claim_statement"],
        ["metadata.conclusion_clause_ids", "observed.uncovered_conclusion_clause_ids"],
    ]
    assert alignment["request_template"]["metadata"]["claim_statement"] == "For all r_0 > 0, the full theorem holds."
    assert "conclusion_clause_ids" not in alignment["request_template"]["metadata"]
    assert "uncovered_conclusion_clause_ids" not in alignment["request_template"]["observed"]


def test_suggest_contract_templates_avoid_placeholder_contract() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_proof_contract_fixture())
    alignment = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.claim_to_proof_alignment")

    assert alignment["request_template"].get("contract") is None


def test_run_contract_check_shape_errors_expose_request_template_guidance() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check({"check_key": "contract.limit_recovery", "unknown_field": 1})

    assert result["error"].startswith("request contains unsupported keys")
    assert result.get("request_template")
    assert result["request_template"].get("check_key") == "contract.limit_recovery"
    assert "required_request_fields" in result


def test_suggested_claim_alignment_template_is_runnable_without_clause_audit_preset() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    result = suggest_contract_checks(_proof_contract_fixture())
    alignment = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.claim_to_proof_alignment")
    request = copy.deepcopy(alignment["request_template"])
    request["contract"] = _proof_contract_fixture()
    request["observed"]["scope_status"] = "matched"

    verification = run_contract_check(request)

    assert verification["status"] == "pass"
    assert "observed.uncovered_conclusion_clause_ids" not in verification["missing_inputs"]


def test_contract_request_templates_preserve_non_null_required_fields() -> None:
    from gpd.mcp.servers.verification_server import _CONTRACT_CHECK_REQUEST_HINTS, _contract_check_request_hint

    def _lookup(template: dict[str, object], field_path: str) -> object | None:
        current: object | None = template
        for part in field_path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    for check_key, hint in _CONTRACT_CHECK_REQUEST_HINTS.items():
        template = _contract_check_request_hint(check_key)["request_template"]
        for field_name in hint.get("required_request_fields", []):
            if field_name == "contract":
                continue
            assert _lookup(template, field_name) is not None


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
    from gpd.mcp.verification_contract_policy import verification_contract_surface_summary_text

    descriptors = build_public_descriptors()

    verification = descriptors["gpd-verification"]
    assert verification["description"].startswith("GPD physics verification checks.")
    assert verification_contract_surface_summary_text() in verification["description"]
    assert "never invent grounding or proof artifacts" in verification["description"]


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


def test_tighten_registered_tool_contracts_updates_detached_public_tool_descriptors() -> None:
    from gpd.mcp.servers import tighten_registered_tool_contracts

    class DemoArgs(BaseModel):
        model_config = ConfigDict(extra="allow")

        project_dir: str

    async def _call_fn_with_arg_validation(fn, fn_is_async, arguments_to_validate, arguments_to_pass_directly):
        return {
            "fn": fn,
            "fn_is_async": fn_is_async,
            "arguments_to_validate": arguments_to_validate,
            "arguments_to_pass_directly": arguments_to_pass_directly,
        }

    @dataclasses.dataclass
    class _FakeFnMetadata:
        arg_model: type[BaseModel]
        call_fn_with_arg_validation: object

    @dataclasses.dataclass
    class _FakeRegisteredTool:
        name: str
        inputSchema: dict[str, object]
        parameters: dict[str, object]
        fn_metadata: _FakeFnMetadata

    @dataclasses.dataclass
    class _FakePublicTool:
        name: str
        inputSchema: dict[str, object]

    @dataclasses.dataclass
    class _FakeToolManager:
        tools: list[_FakeRegisteredTool]

        def list_tools(self) -> list[_FakeRegisteredTool]:
            return self.tools

    class _FakeMCP:
        def __init__(self) -> None:
            self._registered_tool = _FakeRegisteredTool(
                name="demo",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": True},
                parameters={"type": "object", "properties": {}, "additionalProperties": True},
                fn_metadata=_FakeFnMetadata(
                    arg_model=DemoArgs,
                    call_fn_with_arg_validation=_call_fn_with_arg_validation,
                ),
            )
            self._tool_manager = _FakeToolManager([self._registered_tool])

        async def list_tools(self) -> list[_FakePublicTool]:
            return [
                _FakePublicTool(
                    name="demo",
                    inputSchema={"type": "object", "properties": {}, "additionalProperties": True},
                )
            ]

    fake_mcp = _FakeMCP()

    tighten_registered_tool_contracts(fake_mcp)

    public_tools = anyio.run(fake_mcp.list_tools)

    public_schema = public_tools[0].inputSchema
    registered_schema = fake_mcp._registered_tool.parameters
    assert public_schema["additionalProperties"] is False
    assert public_schema["required"] == ["project_dir"]
    assert public_schema["properties"]["project_dir"]["type"] == "string"
    assert fake_mcp._registered_tool.inputSchema["additionalProperties"] is False
    assert registered_schema["additionalProperties"] is False
    assert fake_mcp._registered_tool.inputSchema == public_schema
    assert registered_schema == public_schema


def test_tighten_registered_tool_contracts_requires_tool_manager() -> None:
    from gpd.mcp.servers import FastMCPCompatibilityError, tighten_registered_tool_contracts

    class _FakeMCP:
        pass

    with pytest.raises(FastMCPCompatibilityError, match="_tool_manager"):
        tighten_registered_tool_contracts(_FakeMCP())


def test_tighten_registered_tool_contracts_validates_tool_metadata() -> None:
    from gpd.mcp.servers import FastMCPCompatibilityError, tighten_registered_tool_contracts

    @dataclasses.dataclass
    class _FakeTool:
        name = "demo"
        inputSchema: dict[str, object] = dataclasses.field(default_factory=dict)
        parameters: dict[str, object] = dataclasses.field(default_factory=dict)

    @dataclasses.dataclass
    class _FakeToolManager:
        tools: list[_FakeTool]

        def list_tools(self) -> list[_FakeTool]:
            return self.tools

    class _FakeMCP:
        def __init__(self) -> None:
            self._tool_manager = _FakeToolManager([_FakeTool()])

        async def list_tools(self) -> list[object]:
            return []

    with pytest.raises(FastMCPCompatibilityError, match="fn_metadata"):
        tighten_registered_tool_contracts(_FakeMCP())


def test_skill_category_schema_refresh_handles_reversed_anyof_branch_order() -> None:
    from gpd import registry as content_registry
    from gpd.mcp.servers.skills_server import _schema_with_refreshed_skill_category_enum

    schema = {
        "type": "object",
        "properties": {
            "category": {
                "anyOf": [
                    {"type": "object", "properties": {"extra": {"type": "string"}}},
                    {"type": "string", "minLength": 1, "pattern": r"^\S(?:[\s\S]*\S)?$"},
                ]
            }
        },
    }

    refreshed = _schema_with_refreshed_skill_category_enum(schema)
    branches = refreshed["properties"]["category"]["anyOf"]

    assert branches[0]["type"] == "object"
    assert "enum" not in branches[0]
    assert branches[1]["enum"] == list(content_registry.skill_categories())


def test_protocol_domain_schema_refresh_handles_reversed_anyof_branch_order() -> None:
    from gpd.mcp.servers.protocols_server import _protocol_domain_values, _schema_with_refreshed_protocol_domain_enum

    schema = {
        "type": "object",
        "properties": {
            "domain": {
                "anyOf": [
                    {"type": "object", "properties": {"extra": {"type": "string"}}},
                    {"type": "string", "minLength": 1, "pattern": r"^\S(?:[\s\S]*\S)?$"},
                ]
            }
        },
    }

    refreshed = _schema_with_refreshed_protocol_domain_enum(schema)
    branches = refreshed["properties"]["domain"]["anyOf"]

    assert branches[0]["type"] == "object"
    assert "enum" not in branches[0]
    assert branches[1]["enum"] == list(_protocol_domain_values())


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
    assert "before executing" in description


def test_public_verification_infra_descriptor_surfaces_semantic_contract_rules() -> None:
    from gpd.mcp.verification_contract_policy import verification_contract_surface_summary_text

    descriptor = json.loads(
        (Path(__file__).resolve().parents[2] / "infra" / "gpd-verification.json").read_text(encoding="utf-8")
    )

    description = descriptor["description"]
    assert description.startswith("GPD physics verification checks.")
    assert verification_contract_surface_summary_text() in description
