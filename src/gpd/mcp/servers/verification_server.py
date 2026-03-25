"""MCP server for GPD physics verification.

Exposes verification checks as MCP tools for solver agents to run
dimensional analysis, limiting case checks, symmetry verification,
and domain-specific checklists.

Usage:
    python -m gpd.mcp.servers.verification_server
    # or via entry point:
    gpd-mcp-verification
"""

import copy
import logging
import re
import sys
from collections.abc import Iterable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import ResearchContract, collect_contract_integrity_errors
from gpd.core.contract_validation import (
    _sanitize_contract_scalars,
    _split_project_contract_schema_findings,
    salvage_project_contract,
)
from gpd.core.observability import gpd_span
from gpd.core.protocol_bundles import ResolvedProtocolBundle, get_protocol_bundle, render_protocol_bundle_context
from gpd.core.verification_checks import (
    ERROR_CLASS_COVERAGE,
    VERIFICATION_CHECK_IDS,
    VERIFICATION_SCHEMA_VERSION,
    get_verification_check,
    list_verification_checks,
)
from gpd.mcp.servers import stable_mcp_error, stable_mcp_response

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-verification")

mcp = FastMCP("gpd-verification")

_CONTRACT_CHECK_REQUEST_HINTS: dict[str, dict[str, object]] = {
    "contract.limit_recovery": {
        "required_request_fields": ["metadata.regime_label", "metadata.expected_behavior"],
        "optional_request_fields": ["binding.*", "observed.limit_passed", "observed.observed_limit", "artifact_content"],
        "request_template": {
            "binding": {},
            "metadata": {
                "regime_label": None,
                "expected_behavior": None,
            },
            "observed": {
                "limit_passed": None,
                "observed_limit": None,
            },
            "artifact_content": None,
        },
    },
    "contract.benchmark_reproduction": {
        "required_request_fields": [
            "metadata.source_reference_id",
            "observed.metric_value",
            "observed.threshold_value",
        ],
        "optional_request_fields": ["binding.*", "artifact_content"],
        "request_template": {
            "binding": {},
            "metadata": {
                "source_reference_id": None,
            },
            "observed": {
                "metric_value": None,
                "threshold_value": None,
            },
            "artifact_content": None,
        },
    },
    "contract.direct_proxy_consistency": {
        "required_request_fields": [],
        "optional_request_fields": [
            "binding.*",
            "observed.proxy_only",
            "observed.direct_available",
            "observed.proxy_available",
            "observed.consistency_passed",
            "artifact_content",
        ],
        "request_template": {
            "binding": {},
            "metadata": {},
            "observed": {
                "proxy_only": None,
                "direct_available": None,
                "proxy_available": None,
                "consistency_passed": None,
            },
            "artifact_content": None,
        },
    },
    "contract.fit_family_mismatch": {
        "required_request_fields": ["metadata.declared_family", "observed.selected_family"],
        "optional_request_fields": [
            "binding.*",
            "metadata.allowed_families[]",
            "metadata.forbidden_families[]",
            "observed.competing_family_checked",
            "artifact_content",
        ],
        "request_template": {
            "binding": {},
            "metadata": {
                "declared_family": None,
                "allowed_families": [],
                "forbidden_families": [],
            },
            "observed": {
                "selected_family": None,
                "competing_family_checked": None,
            },
            "artifact_content": None,
        },
    },
    "contract.estimator_family_mismatch": {
        "required_request_fields": ["metadata.declared_family", "observed.selected_family"],
        "optional_request_fields": [
            "binding.*",
            "metadata.allowed_families[]",
            "metadata.forbidden_families[]",
            "observed.bias_checked",
            "observed.calibration_checked",
            "artifact_content",
        ],
        "request_template": {
            "binding": {},
            "metadata": {
                "declared_family": None,
                "allowed_families": [],
                "forbidden_families": [],
            },
            "observed": {
                "selected_family": None,
                "bias_checked": None,
                "calibration_checked": None,
            },
            "artifact_content": None,
        },
    },
}


class _ContractRequestBase(BaseModel):
    model_config = ConfigDict(extra="allow")


class ContractBindingRequest(_ContractRequestBase):
    observable_id: str | list[str] | None = Field(
        default=None,
        description="Binding to one observable id or a list of observable ids.",
    )
    observable_ids: str | list[str] | None = Field(
        default=None,
        description="Plural alias accepted for observable bindings.",
    )
    claim_id: str | list[str] | None = Field(
        default=None,
        description="Binding to one claim id or a list of claim ids.",
    )
    claim_ids: str | list[str] | None = Field(
        default=None,
        description="Plural alias accepted for claim bindings.",
    )
    deliverable_id: str | list[str] | None = Field(
        default=None,
        description="Binding to one deliverable id or a list of deliverable ids.",
    )
    deliverable_ids: str | list[str] | None = Field(
        default=None,
        description="Plural alias accepted for deliverable bindings.",
    )
    acceptance_test_id: str | list[str] | None = Field(
        default=None,
        description="Binding to one acceptance-test id or a list of acceptance-test ids.",
    )
    acceptance_test_ids: str | list[str] | None = Field(
        default=None,
        description="Plural alias accepted for acceptance-test bindings.",
    )
    reference_id: str | list[str] | None = Field(
        default=None,
        description="Binding to one reference id or a list of reference ids.",
    )
    reference_ids: str | list[str] | None = Field(
        default=None,
        description="Plural alias accepted for reference bindings.",
    )
    forbidden_proxy_id: str | list[str] | None = Field(
        default=None,
        description="Binding to one forbidden-proxy id or a list of forbidden-proxy ids.",
    )
    forbidden_proxy_ids: str | list[str] | None = Field(
        default=None,
        description="Plural alias accepted for forbidden-proxy bindings.",
    )


class ContractMetadataRequest(_ContractRequestBase):
    regime_label: str | None = None
    expected_behavior: str | None = None
    source_reference_id: str | None = None
    declared_family: str | None = None
    allowed_families: list[str] | None = None
    forbidden_families: list[str] | None = None


class ContractObservedRequest(_ContractRequestBase):
    limit_passed: bool | None = None
    observed_limit: str | None = None
    metric_value: int | float | None = None
    threshold_value: int | float | None = None
    proxy_only: bool | None = None
    direct_available: bool | None = None
    proxy_available: bool | None = None
    consistency_passed: bool | None = None
    selected_family: str | None = None
    competing_family_checked: bool | None = None
    bias_checked: bool | None = None
    calibration_checked: bool | None = None


class RunContractCheckRequest(_ContractRequestBase):
    check_key: str | None = Field(
        default=None,
        description="Canonical contract-aware check key, or a stable numeric id that resolves to the same check.",
    )
    check_id: str | None = Field(
        default=None,
        description="Compatibility alias for check_key; may use either the canonical key or numeric id.",
    )
    contract: dict[str, object] | ResearchContract | None = Field(
        default=None,
        description="Optional project or phase contract payload; salvage remains runtime-managed.",
    )
    binding: ContractBindingRequest | None = None
    metadata: ContractMetadataRequest | None = None
    observed: ContractObservedRequest | None = None
    artifact_content: str | None = None


def _non_empty_string_schema() -> dict[str, object]:
    return {"type": "string", "minLength": 1, "pattern": r"\S"}


def _string_schema() -> dict[str, object]:
    return {"type": "string"}


def _string_or_null_schema() -> dict[str, object]:
    return {"anyOf": [dict(_string_schema()), {"type": "null"}]}


def _non_empty_string_or_null_schema() -> dict[str, object]:
    return {"anyOf": [dict(_non_empty_string_schema()), {"type": "null"}]}


def _string_list_schema(*, min_items: int | None = None) -> dict[str, object]:
    schema: dict[str, object] = {"type": "array", "items": _non_empty_string_schema()}
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def _string_or_string_list_or_null_schema(*, min_items: int | None = None) -> dict[str, object]:
    return {
        "anyOf": [
            dict(_non_empty_string_schema()),
            _string_list_schema(min_items=min_items),
            {"type": "null"},
        ]
    }


def _string_or_string_list_schema(*, min_items: int | None = None) -> dict[str, object]:
    return {
        "anyOf": [
            dict(_non_empty_string_schema()),
            _string_list_schema(min_items=min_items),
        ]
    }


def _boolean_or_null_schema() -> dict[str, object]:
    return {"anyOf": [{"type": "boolean"}, {"type": "null"}]}


def _number_or_null_schema() -> dict[str, object]:
    return {"anyOf": [{"type": "number"}, {"type": "null"}]}


def _object_schema(
    properties: dict[str, object],
    *,
    required: Iterable[str] = (),
    additional_properties: bool = False,
) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": additional_properties,
        "properties": properties,
    }
    required_list = list(required)
    if required_list:
        schema["required"] = required_list
    return schema


def _open_object_schema(
    properties: dict[str, object],
    *,
    required: Iterable[str] = (),
) -> dict[str, object]:
    return _object_schema(
        properties,
        required=required,
        additional_properties=True,
    )


def _enum_string_schema(values: Iterable[str]) -> dict[str, object]:
    return {
        "type": "string",
        "enum": list(values),
    }


def _binding_input_schema_for_targets(targets: Iterable[str]) -> dict[str, object]:
    properties: dict[str, object] = {}
    for target in targets:
        properties[f"{target}_id"] = _string_or_string_list_schema(min_items=1)
        properties[f"{target}_ids"] = _string_or_string_list_schema(min_items=1)
    return _object_schema(properties, additional_properties=False)


_CONTRACT_OBSERVABLE_KIND_VALUES = (
    "scalar",
    "curve",
    "map",
    "classification",
    "proof_obligation",
    "other",
)
_CONTRACT_DELIVERABLE_KIND_VALUES = (
    "figure",
    "table",
    "dataset",
    "data",
    "derivation",
    "code",
    "note",
    "report",
    "other",
)
_CONTRACT_ACCEPTANCE_TEST_KIND_VALUES = (
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
)
_CONTRACT_ACCEPTANCE_AUTOMATION_VALUES = ("automated", "hybrid", "human")
_CONTRACT_REFERENCE_KIND_VALUES = ("paper", "dataset", "prior_artifact", "spec", "user_anchor", "other")
_CONTRACT_REFERENCE_ROLE_VALUES = ("definition", "benchmark", "method", "must_consider", "background", "other")
_CONTRACT_REFERENCE_ACTION_VALUES = ("read", "use", "compare", "cite", "avoid")
_CONTRACT_LINK_RELATION_VALUES = (
    "supports",
    "computes",
    "visualizes",
    "benchmarks",
    "depends_on",
    "evaluated_by",
    "other",
)
_CONTRACT_BINDING_TARGETS: tuple[str, ...] = (
    "observable",
    "claim",
    "deliverable",
    "acceptance_test",
    "reference",
    "forbidden_proxy",
)
_CONTRACT_AWARE_CHECK_ENTRIES: tuple[dict[str, object], ...] = tuple(
    entry for entry in list_verification_checks() if bool(entry.get("contract_aware"))
)


def _check_identifier_values(entry: dict[str, object]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("check_key", "check_id"):
        value = entry.get(key)
        if not isinstance(value, str):
            continue
        if value in values:
            continue
        values.append(value)
    return tuple(values)


_CONTRACT_CHECK_IDENTIFIER_VALUES: tuple[str, ...] = tuple(
    identifier
    for entry in _CONTRACT_AWARE_CHECK_ENTRIES
    for identifier in _check_identifier_values(entry)
)


_CONTRACT_BINDING_INPUT_SCHEMA: dict[str, object] = _binding_input_schema_for_targets(_CONTRACT_BINDING_TARGETS)
_CONTRACT_METADATA_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "regime_label": _non_empty_string_or_null_schema(),
        "expected_behavior": _non_empty_string_or_null_schema(),
        "source_reference_id": _non_empty_string_or_null_schema(),
        "declared_family": _non_empty_string_or_null_schema(),
        "allowed_families": _string_list_schema(),
        "forbidden_families": _string_list_schema(),
    },
    additional_properties=False,
)
_CONTRACT_OBSERVED_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "limit_passed": _boolean_or_null_schema(),
        "observed_limit": _non_empty_string_or_null_schema(),
        "metric_value": _number_or_null_schema(),
        "threshold_value": _number_or_null_schema(),
        "proxy_only": _boolean_or_null_schema(),
        "direct_available": _boolean_or_null_schema(),
        "proxy_available": _boolean_or_null_schema(),
        "consistency_passed": _boolean_or_null_schema(),
        "selected_family": _non_empty_string_or_null_schema(),
        "competing_family_checked": _boolean_or_null_schema(),
        "bias_checked": _boolean_or_null_schema(),
        "calibration_checked": _boolean_or_null_schema(),
    },
    additional_properties=False,
)
_CONTRACT_SCOPE_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "question": _non_empty_string_schema(),
        "in_scope": _string_list_schema(),
        "out_of_scope": _string_list_schema(),
        "unresolved_questions": _string_list_schema(),
    },
    required=("question",),
)
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "must_read_refs": _string_list_schema(),
        "must_include_prior_outputs": _string_list_schema(),
        "user_asserted_anchors": _string_list_schema(),
        "known_good_baselines": _string_list_schema(),
        "context_gaps": _string_list_schema(),
        "crucial_inputs": _string_list_schema(),
    }
)
_CONTRACT_APPROACH_POLICY_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "formulations": _string_list_schema(),
        "allowed_estimator_families": _string_list_schema(),
        "forbidden_estimator_families": _string_list_schema(),
        "allowed_fit_families": _string_list_schema(),
        "forbidden_fit_families": _string_list_schema(),
        "stop_and_rethink_conditions": _string_list_schema(),
    }
)
_CONTRACT_OBSERVABLE_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "name": _non_empty_string_schema(),
        "kind": _enum_string_schema(_CONTRACT_OBSERVABLE_KIND_VALUES),
        "definition": _non_empty_string_schema(),
        "regime": _non_empty_string_or_null_schema(),
        "units": _non_empty_string_or_null_schema(),
    },
    required=("id", "name", "definition"),
)
_CONTRACT_CLAIM_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "statement": _non_empty_string_schema(),
        "observables": _string_list_schema(),
        "deliverables": _string_list_schema(),
        "acceptance_tests": _string_list_schema(),
        "references": _string_list_schema(),
    },
    required=("id", "statement"),
)
_CONTRACT_DELIVERABLE_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "kind": _enum_string_schema(_CONTRACT_DELIVERABLE_KIND_VALUES),
        "path": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "description": _non_empty_string_schema(),
        "must_contain": _string_list_schema(),
    },
    required=("id", "description"),
)
_CONTRACT_ACCEPTANCE_TEST_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "subject": _non_empty_string_schema(),
        "kind": _enum_string_schema(_CONTRACT_ACCEPTANCE_TEST_KIND_VALUES),
        "procedure": _non_empty_string_schema(),
        "pass_condition": _non_empty_string_schema(),
        "evidence_required": _string_list_schema(),
        "automation": _enum_string_schema(_CONTRACT_ACCEPTANCE_AUTOMATION_VALUES),
    },
    required=("id", "subject", "procedure", "pass_condition"),
)
_CONTRACT_REFERENCE_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "kind": _enum_string_schema(_CONTRACT_REFERENCE_KIND_VALUES),
        "locator": _non_empty_string_schema(),
        "aliases": _string_list_schema(),
        "role": _enum_string_schema(_CONTRACT_REFERENCE_ROLE_VALUES),
        "why_it_matters": _non_empty_string_schema(),
        "applies_to": _string_list_schema(),
        "carry_forward_to": _string_list_schema(),
        "must_surface": {"type": "boolean"},
        "required_actions": {
            "type": "array",
            "items": _enum_string_schema(_CONTRACT_REFERENCE_ACTION_VALUES),
        },
    },
    required=("id", "locator", "why_it_matters"),
)
_CONTRACT_FORBIDDEN_PROXY_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "subject": _non_empty_string_schema(),
        "proxy": _non_empty_string_schema(),
        "reason": _non_empty_string_schema(),
    },
    required=("id", "subject", "proxy", "reason"),
)
_CONTRACT_LINK_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "id": _non_empty_string_schema(),
        "source": _non_empty_string_schema(),
        "target": _non_empty_string_schema(),
        "relation": _enum_string_schema(_CONTRACT_LINK_RELATION_VALUES),
        "verified_by": _string_list_schema(),
    },
    required=("id", "source", "target"),
)
_CONTRACT_UNCERTAINTY_MARKERS_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "weakest_anchors": _string_list_schema(),
        "unvalidated_assumptions": _string_list_schema(),
        "competing_explanations": _string_list_schema(),
        "disconfirming_observations": _string_list_schema(),
    }
)
_CONTRACT_PAYLOAD_INPUT_SCHEMA: dict[str, object] = _open_object_schema(
    {
        "schema_version": {"type": "integer", "const": 1},
        "scope": dict(_CONTRACT_SCOPE_INPUT_SCHEMA),
        "context_intake": dict(_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA),
        "approach_policy": dict(_CONTRACT_APPROACH_POLICY_INPUT_SCHEMA),
        "observables": {
            "type": "array",
            "items": dict(_CONTRACT_OBSERVABLE_INPUT_SCHEMA),
        },
        "claims": {
            "type": "array",
            "items": dict(_CONTRACT_CLAIM_INPUT_SCHEMA),
        },
        "deliverables": {
            "type": "array",
            "items": dict(_CONTRACT_DELIVERABLE_INPUT_SCHEMA),
        },
        "acceptance_tests": {
            "type": "array",
            "items": dict(_CONTRACT_ACCEPTANCE_TEST_INPUT_SCHEMA),
        },
        "references": {
            "type": "array",
            "items": dict(_CONTRACT_REFERENCE_INPUT_SCHEMA),
        },
        "forbidden_proxies": {
            "type": "array",
            "items": dict(_CONTRACT_FORBIDDEN_PROXY_INPUT_SCHEMA),
        },
        "links": {
            "type": "array",
            "items": dict(_CONTRACT_LINK_INPUT_SCHEMA),
        },
        "uncertainty_markers": dict(_CONTRACT_UNCERTAINTY_MARKERS_INPUT_SCHEMA),
    },
    required=("scope",),
)


def _run_contract_binding_condition_schema() -> list[dict[str, object]]:
    conditions: list[dict[str, object]] = []
    for entry in _CONTRACT_AWARE_CHECK_ENTRIES:
        identifiers = _check_identifier_values(entry)
        if not identifiers:
            continue
        binding_targets = tuple(target for target in entry.get("binding_targets", ()) if isinstance(target, str))
        conditions.append(
            {
                "if": {
                    "anyOf": [
                        {"required": ["check_key"], "properties": {"check_key": {"enum": list(identifiers)}}},
                        {"required": ["check_id"], "properties": {"check_id": {"enum": list(identifiers)}}},
                    ]
                },
                "then": {
                    "properties": {
                        "binding": {
                            "anyOf": [
                                _binding_input_schema_for_targets(binding_targets),
                                {"type": "null"},
                            ]
                        }
                    }
                },
            }
        )
    return conditions


def _run_contract_identifier_pairing_condition_schema() -> dict[str, object] | None:
    options: list[dict[str, object]] = []
    for entry in _CONTRACT_AWARE_CHECK_ENTRIES:
        identifiers = _check_identifier_values(entry)
        if not identifiers:
            continue
        identifier_schema = {"enum": list(identifiers)}
        options.append(
            {
                "properties": {
                    "check_key": dict(identifier_schema),
                    "check_id": dict(identifier_schema),
                },
                "required": ["check_key", "check_id"],
            }
        )
    if not options:
        return None
    return {
        "if": {"required": ["check_key", "check_id"]},
        "then": {"anyOf": options},
    }


_RUN_CONTRACT_CHECK_BINDING_CONDITIONS = _run_contract_binding_condition_schema()
_RUN_CONTRACT_CHECK_IDENTIFIER_PAIRING_CONDITION = _run_contract_identifier_pairing_condition_schema()
_RUN_CONTRACT_CHECK_REQUEST_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "anyOf": [
        {"required": ["check_key"]},
        {"required": ["check_id"]},
    ],
    "properties": {
        "check_key": _enum_string_schema(_CONTRACT_CHECK_IDENTIFIER_VALUES),
        "check_id": _enum_string_schema(_CONTRACT_CHECK_IDENTIFIER_VALUES),
        "contract": {"anyOf": [dict(_CONTRACT_PAYLOAD_INPUT_SCHEMA), {"type": "null"}]},
        "binding": {"anyOf": [dict(_CONTRACT_BINDING_INPUT_SCHEMA), {"type": "null"}]},
        "metadata": {"anyOf": [dict(_CONTRACT_METADATA_INPUT_SCHEMA), {"type": "null"}]},
        "observed": {"anyOf": [dict(_CONTRACT_OBSERVED_INPUT_SCHEMA), {"type": "null"}]},
        "artifact_content": _non_empty_string_or_null_schema(),
    },
}
all_of_conditions: list[dict[str, object]] = []
if _RUN_CONTRACT_CHECK_BINDING_CONDITIONS:
    all_of_conditions.extend(_RUN_CONTRACT_CHECK_BINDING_CONDITIONS)
if _RUN_CONTRACT_CHECK_IDENTIFIER_PAIRING_CONDITION is not None:
    all_of_conditions.append(_RUN_CONTRACT_CHECK_IDENTIFIER_PAIRING_CONDITION)
if all_of_conditions:
    _RUN_CONTRACT_CHECK_REQUEST_SCHEMA["allOf"] = all_of_conditions

RunContractCheckPayload = Annotated[object, WithJsonSchema(_RUN_CONTRACT_CHECK_REQUEST_SCHEMA)]
SuggestContractPayload = Annotated[object, WithJsonSchema(_CONTRACT_PAYLOAD_INPUT_SCHEMA)]
StringListPayload = Annotated[
    object | None,
    WithJsonSchema({"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]}),
]


def _contract_check_request_hint(check_key: str, *, contract: ResearchContract | None = None) -> dict[str, object]:
    hint = _CONTRACT_CHECK_REQUEST_HINTS.get(check_key, {})
    check_meta = get_verification_check(check_key)
    binding_targets = list(check_meta.binding_targets) if check_meta is not None else []
    supported_binding_fields = _supported_binding_fields_for_targets(binding_targets)
    request_template = copy.deepcopy(hint.get("request_template", {}))
    if check_key:
        request_template["check_key"] = check_key
    enriched_hint = {
        "required_request_fields": list(hint.get("required_request_fields", [])),
        "optional_request_fields": [
            *supported_binding_fields,
            *[
                field
                for field in hint.get("optional_request_fields", [])
                if field != "binding.*"
            ],
        ],
        "supported_binding_fields": supported_binding_fields,
        "request_template": request_template,
    }

    if contract is None:
        return enriched_hint

    binding = request_template.setdefault("binding", {})
    metadata = request_template.setdefault("metadata", {})
    if check_key == "contract.benchmark_reproduction":
        benchmark_reference_ids = [
            reference.id
            for reference in contract.references
            if reference.role == "benchmark" or "compare" in reference.required_actions
        ]
        benchmark_tests = _matching_acceptance_tests(
            contract,
            kinds=("benchmark",),
            keywords=("benchmark", "baseline", "reference"),
            evidence_ids=benchmark_reference_ids,
        )
        if len(_unique_strings(benchmark_reference_ids)) == 1 and len(benchmark_tests) == 1:
            benchmark_reference_id = benchmark_reference_ids[0]
            metadata["source_reference_id"] = benchmark_reference_id
            binding.setdefault("reference_ids", [benchmark_reference_id])
            benchmark_test = _apply_single_acceptance_test_binding(binding, contract, benchmark_tests)
            if benchmark_test is not None:
                _set_single_binding_value(
                    binding,
                    "reference_ids",
                    [reference_id for reference_id in benchmark_test.evidence_required if reference_id in benchmark_reference_ids],
                )
            enriched_hint["required_request_fields"] = [
                field for field in enriched_hint["required_request_fields"] if field != "metadata.source_reference_id"
            ]

    elif check_key == "contract.limit_recovery":
        limit_tests = _matching_acceptance_tests(
            contract,
            kinds=("limiting_case",),
            keywords=("limit", "asymptotic", "boundary", "scaling"),
        )
        regime_candidates = _unique_strings(
            observable.regime for observable in contract.observables if observable.regime
        )
        if len(regime_candidates) == 1 and len(limit_tests) == 1:
            regime_label = regime_candidates[0]
            metadata["regime_label"] = regime_label
            _set_single_binding_value(
                binding,
                "observable_ids",
                [observable.id for observable in contract.observables if observable.regime == regime_label],
            )
            _set_single_binding_value(binding, "claim_ids", _claim_ids_for_regime(contract, regime_label))
            limit_test = _apply_single_acceptance_test_binding(
                binding,
                contract,
                limit_tests,
                include_observable_binding=True,
            )
            if limit_test is None:
                binding_ids = {target: _binding_values_for_target(binding, target) for target in _BINDING_TARGETS}
                limit_test = _resolve_single_limit_acceptance_test(contract, binding_ids)
            if limit_test is not None and limit_test.pass_condition:
                metadata["expected_behavior"] = limit_test.pass_condition
            enriched_hint["required_request_fields"] = [
                field for field in enriched_hint["required_request_fields"] if field != "metadata.regime_label"
            ]
            if limit_test is not None and limit_test.pass_condition:
                enriched_hint["required_request_fields"] = [
                    field
                    for field in enriched_hint["required_request_fields"]
                    if field != "metadata.expected_behavior"
                ]

    elif check_key == "contract.direct_proxy_consistency":
        forbidden_proxy_candidates, _ = _direct_proxy_candidates(
            contract,
            {},
            binding_supplied=False,
        )
        if len(forbidden_proxy_candidates) == 1:
            forbidden_proxy_id = forbidden_proxy_candidates[0]
            binding["forbidden_proxy_ids"] = [forbidden_proxy_id]
            forbidden_proxy = next(
                (proxy for proxy in contract.forbidden_proxies if proxy.id == forbidden_proxy_id),
                None,
            )
            if forbidden_proxy is not None:
                _apply_subject_binding(binding, contract, forbidden_proxy.subject)
            proxy_tests = _matching_acceptance_tests(
                contract,
                kinds=("proxy",),
                keywords=("proxy", "surrogate"),
            )
            _apply_single_acceptance_test_binding_if_consistent(
                binding,
                contract,
                proxy_tests,
            )
        else:
            enriched_hint["required_request_fields"] = ["binding.forbidden_proxy_ids"]

    elif check_key == "contract.fit_family_mismatch":
        allowed_families = list(contract.approach_policy.allowed_fit_families)
        forbidden_families = list(contract.approach_policy.forbidden_fit_families)
        if allowed_families:
            metadata["allowed_families"] = allowed_families
        if forbidden_families:
            metadata["forbidden_families"] = forbidden_families
        if len(allowed_families) == 1:
            metadata["declared_family"] = allowed_families[0]
        fit_tests = _matching_acceptance_tests(
            contract,
            keywords=("fit", "residual", "extrapolat", "ansatz"),
        )
        _apply_single_acceptance_test_binding(
            binding,
            contract,
            fit_tests,
            include_observable_binding=True,
        )

    elif check_key == "contract.estimator_family_mismatch":
        allowed_families = list(contract.approach_policy.allowed_estimator_families)
        forbidden_families = list(contract.approach_policy.forbidden_estimator_families)
        if allowed_families:
            metadata["allowed_families"] = allowed_families
        if forbidden_families:
            metadata["forbidden_families"] = forbidden_families
        if len(allowed_families) == 1:
            metadata["declared_family"] = allowed_families[0]
        estimator_tests = _matching_acceptance_tests(
            contract,
            keywords=("estimator", "bootstrap", "jackknife", "posterior", "bias", "variance"),
        )
        _apply_single_acceptance_test_binding(
            binding,
            contract,
            estimator_tests,
            include_observable_binding=True,
        )

    return enriched_hint


def _subject_binding_requirement(
    check_key: str,
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    resolved_subject: str | None,
) -> tuple[list[str], str | None]:
    """Return missing selector hints when a subject-bound check is still ambiguous."""

    if contract is None or resolved_subject:
        return [], None

    if check_key == "contract.benchmark_reproduction":
        benchmark_reference_ids = [
            reference.id
            for reference in contract.references
            if reference.role == "benchmark" or "compare" in reference.required_actions
        ]
        benchmark_tests = _matching_acceptance_tests(
            contract,
            kinds=("benchmark",),
            keywords=("benchmark", "baseline", "reference"),
            evidence_ids=benchmark_reference_ids,
        )
        reference_candidates, _ = _benchmark_reference_candidates(
            contract,
            binding_ids,
            binding_supplied=bool(binding_ids),
        )
        if len(reference_candidates) > 1 or (
            not binding_ids and (len(_unique_strings(benchmark_reference_ids)) > 1 or len(benchmark_tests) > 1)
        ):
            return [
                "metadata.source_reference_id"
            ], "Ambiguous benchmark context requires an explicit benchmark reference"

    if check_key == "contract.limit_recovery":
        regime_ids = _unique_strings(observable.regime for observable in contract.observables if observable.regime)
        limit_tests = _matching_acceptance_tests(
            contract,
            kinds=("limiting_case",),
            keywords=("limit", "asymptotic", "boundary", "scaling"),
        )
        regime_candidates, _ = _limit_regime_candidates(
            contract,
            binding_ids,
            binding_supplied=bool(binding_ids),
        )
        if len(regime_candidates) > 1 or (not binding_ids and (len(regime_ids) > 1 or len(limit_tests) > 1)):
            return ["metadata.regime_label"], "Ambiguous limit context requires an explicit regime selection"

    if check_key == "contract.direct_proxy_consistency":
        forbidden_proxy_candidates, _ = _direct_proxy_candidates(
            contract,
            binding_ids,
            binding_supplied=bool(binding_ids),
        )
        if len(forbidden_proxy_candidates) > 1 or (not binding_ids and len(contract.forbidden_proxies) > 1):
            return [
                "binding.forbidden_proxy_ids"
            ], "Ambiguous direct/proxy context requires an explicit forbidden proxy binding"

    return [], None


def _normalize_optional_scalar_str(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    return stripped or None


def _validate_optional_string(value: object, *, field_name: str) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, f"{field_name} must be a string"
    stripped = value.strip()
    if not stripped:
        return None, f"{field_name} must be a non-empty string"
    return stripped, None


def _normalize_string_list(value: object) -> object:
    if not isinstance(value, list):
        return value
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped:
            normalized.append(stripped)
    return normalized


def _validate_string_list_members(value: object, *, field_name: str) -> str | None:
    if not isinstance(value, list):
        return None
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            return f"{field_name}[{index}] must be a non-empty string"
    return None


def _validate_string_list_field(value: object, *, field_name: str) -> str | None:
    if not isinstance(value, list):
        return f"{field_name} must be a list of strings"
    return _validate_string_list_members(value, field_name=field_name)


def _validate_binding_field_value(value: object, *, field_name: str) -> str | None:
    if isinstance(value, str):
        if not value.strip():
            return f"{field_name} must be a non-empty string"
        return None
    if isinstance(value, list):
        error = _validate_string_list_members(value, field_name=field_name)
        if error is not None:
            return error
        if not value:
            return f"{field_name} must include at least one non-empty string"
        return None
    return f"{field_name} must be a string or list of strings"


def _normalize_binding_alias_values(value: object) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            values.append(stripped)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    values.append(stripped)
    return _unique_strings(values)


def _validate_binding_payload(binding: dict[str, object], *, allowed_targets: Iterable[str]) -> str | None:
    allowed_targets = tuple(allowed_targets)
    allowed_keys = {
        key
        for target in allowed_targets
        for key in (f"{target}_id", f"{target}_ids")
    }
    unknown_keys = sorted(str(key) for key in binding if key not in allowed_keys)
    if unknown_keys:
        supported = ", ".join(_supported_binding_fields_for_targets(allowed_targets))
        joined = ", ".join(unknown_keys)
        return f"binding contains unsupported keys: {joined}; supported keys are {supported}"

    for target in allowed_targets:
        singular_key = f"{target}_id"
        plural_key = f"{target}_ids"
        if singular_key in binding and plural_key in binding:
            singular_error = _validate_binding_field_value(binding[singular_key], field_name=f"binding.{singular_key}")
            if singular_error is not None:
                return singular_error
            plural_error = _validate_binding_field_value(binding[plural_key], field_name=f"binding.{plural_key}")
            if plural_error is not None:
                return plural_error
            singular_values = _normalize_binding_alias_values(binding[singular_key])
            plural_values = _normalize_binding_alias_values(binding[plural_key])
            if set(singular_values) != set(plural_values):
                return f"binding.{singular_key} and binding.{plural_key} must match when both are provided"

    for key in sorted(binding):
        raw = binding[key]
        error = _validate_binding_field_value(raw, field_name=f"binding.{key}")
        if error is not None:
            return error
    return None


def _normalize_contract_metadata(metadata: dict[str, object]) -> tuple[dict[str, object], str | None]:
    normalized = dict(metadata)
    for key in ("regime_label", "expected_behavior", "source_reference_id", "declared_family"):
        if key in normalized:
            normalized_value, error = _validate_optional_string(normalized[key], field_name=f"metadata.{key}")
            if error is not None:
                return {}, error
            normalized[key] = normalized_value
    for key in ("allowed_families", "forbidden_families"):
        if key in normalized:
            error = _validate_string_list_field(normalized[key], field_name=f"metadata.{key}")
            if error is not None:
                return {}, error
            normalized[key] = _normalize_string_list(normalized[key])
    return normalized, None


def _serialize_verification_check_entry(check_entry: dict[str, object]) -> dict[str, object]:
    serialized = dict(check_entry)
    if bool(serialized.get("contract_aware")):
        serialized.update(_contract_check_request_hint(str(serialized.get("check_key") or "")))
    return serialized

# ─── Domain Checklists ────────────────────────────────────────────────────────

DOMAIN_CHECKLISTS: dict[str, list[dict[str, str]]] = {
    "qft": [
        {"check": "Ward identities after vertex corrections", "check_ids": "5.9"},
        {"check": "Optical theorem after amplitude computation", "check_ids": "5.10"},
        {"check": "Gauge independence (compute in two gauges)", "check_ids": "5.3,5.9"},
        {"check": "UV divergence structure matches power counting", "check_ids": "5.1,5.8"},
        {"check": "Crossing symmetry of scattering amplitudes", "check_ids": "5.10"},
        {"check": "Mandelstam variables: s + t + u = sum(m^2)", "check_ids": "5.2"},
    ],
    "condensed_matter": [
        {"check": "f-sum rule for optical conductivity", "check_ids": "5.9"},
        {"check": "Luttinger theorem (Fermi surface volume = electron count)", "check_ids": "5.4"},
        {"check": "Kramers-Kronig for all response functions", "check_ids": "5.13"},
        {"check": "Goldstone modes match broken symmetry count", "check_ids": "5.3,5.4"},
        {"check": "Spectral weight positive everywhere", "check_ids": "5.12"},
    ],
    "stat_mech": [
        {"check": "Z -> (number of states) at high T", "check_ids": "5.3"},
        {"check": "Critical exponents match universality class", "check_ids": "5.6"},
        {"check": "Finite-size scaling collapse with correct exponents", "check_ids": "5.5"},
        {"check": "Detailed balance: W(A->B)P_eq(A) = W(B->A)P_eq(B)", "check_ids": "5.4"},
        {"check": "C_V >= 0 (thermodynamic stability)", "check_ids": "5.8"},
        {"check": "S -> 0 as T -> 0 (third law)", "check_ids": "5.3"},
    ],
    "gr_cosmology": [
        {"check": "Friedmann + continuity equations consistent", "check_ids": "5.4"},
        {"check": "Comoving vs physical distance factors of (1+z)", "check_ids": "5.1"},
        {"check": "Bianchi identity satisfied", "check_ids": "5.4"},
        {"check": "Energy conditions respected or explicitly violated", "check_ids": "5.8"},
        {"check": "Geodesic equation consistent with metric", "check_ids": "5.3"},
    ],
    "amo": [
        {"check": "Selection rules from angular momentum coupling", "check_ids": "5.4"},
        {"check": "Transition rates obey sum rules", "check_ids": "5.9"},
        {"check": "Dipole matrix elements have correct parity", "check_ids": "5.3"},
        {"check": "Oscillator strengths positive and sum to Z", "check_ids": "5.12,5.9"},
    ],
    "nuclear_particle": [
        {"check": "Cross section satisfies optical theorem", "check_ids": "5.10"},
        {"check": "Isospin quantum numbers conserved", "check_ids": "5.4"},
        {"check": "Branching ratios sum to 1", "check_ids": "5.8"},
        {"check": "Decay widths positive", "check_ids": "5.12"},
    ],
    "quantum_info": [
        {"check": "Tr(rho) = 1, eigenvalues in [0,1], rho = rho^dag", "check_ids": "5.4,5.12"},
        {"check": "Quantum channels are CPTP (Choi matrix PSD)", "check_ids": "5.12"},
        {"check": "Fidelity F in [0,1]", "check_ids": "5.8"},
        {"check": "No-cloning: apparent cloning must violate unitarity", "check_ids": "5.10"},
        {"check": "Entanglement entropy non-negative", "check_ids": "5.12"},
    ],
    "fluid_plasma": [
        {"check": "CFL condition satisfied", "check_ids": "5.5"},
        {"check": "Debye length resolved by grid", "check_ids": "5.5"},
        {"check": "Energy conservation to integrator tolerance", "check_ids": "5.4"},
        {"check": "Reynolds number appropriate for model", "check_ids": "5.8"},
        {"check": "Divergence-free magnetic field maintained", "check_ids": "5.4"},
    ],
    "mathematical_physics": [
        {"check": "Analyticity structure correct (poles, cuts, sheets)", "check_ids": "5.11"},
        {"check": "Index theorem / topological invariant computed", "check_ids": "5.4"},
        {"check": "Symmetry group representation correct", "check_ids": "5.3"},
    ],
    "astrophysics": [
        {"check": "Eddington luminosity limit respected", "check_ids": "5.8"},
        {"check": "Virial theorem applied correctly", "check_ids": "5.4"},
        {"check": "Optical depth integral convergent", "check_ids": "5.5"},
    ],
    "soft_matter": [
        {"check": "Fluctuation-dissipation theorem satisfied", "check_ids": "5.9"},
        {"check": "Free energy extensive in system size", "check_ids": "5.1,5.3"},
        {"check": "Diffusion coefficient positive", "check_ids": "5.12"},
    ],
    "algebraic_qft": [
        {"check": "Wightman axioms satisfied (temperedness, spectral condition, locality)", "check_ids": "5.3,5.4"},
        {"check": "Haag-Kastler net isotony and locality verified", "check_ids": "5.3"},
        {"check": "Reeh-Schlieder property accounted for", "check_ids": "5.10"},
        {"check": "PCT theorem assumptions validated", "check_ids": "5.4"},
    ],
    "string_field_theory": [
        {"check": "BRST cohomology correctly identifies physical states", "check_ids": "5.3,5.9"},
        {"check": "Ghost number conservation at each vertex", "check_ids": "5.4"},
        {"check": "L_infinity / A_infinity relations verified", "check_ids": "5.4"},
        {"check": "Gauge invariance of observables confirmed", "check_ids": "5.3,5.9"},
    ],
    "classical_mechanics": [
        {"check": "Energy conservation (T + V = const for conservative systems)", "check_ids": "5.4"},
        {"check": "Hamilton's equations consistent with Lagrangian formulation", "check_ids": "5.3"},
        {"check": "Canonical transformation preserves Poisson brackets", "check_ids": "5.4"},
        {"check": "Action principle yields correct Euler-Lagrange equations", "check_ids": "5.3"},
    ],
}


def _error_result(message: object) -> dict[str, object]:
    """Return a stable MCP error envelope for verification tools."""
    return stable_mcp_error(message)


def _validate_run_contract_check_request_keys(request: dict[str, object]) -> str | None:
    """Reject unknown keys in the run_contract_check request sections."""

    request_fields = tuple(RunContractCheckRequest.model_fields)
    unknown_request_keys = sorted(str(key) for key in request if key not in request_fields)
    if unknown_request_keys:
        supported = ", ".join(request_fields)
        joined = ", ".join(unknown_request_keys)
        return f"request contains unsupported keys: {joined}; supported keys are {supported}"

    for section_name, model in (
        ("metadata", ContractMetadataRequest),
        ("observed", ContractObservedRequest),
    ):
        section = request.get(section_name)
        if not isinstance(section, dict):
            continue
        section_fields = tuple(model.model_fields)
        unknown_section_keys = sorted(str(key) for key in section if key not in section_fields)
        if unknown_section_keys:
            supported = ", ".join(section_fields)
            joined = ", ".join(unknown_section_keys)
            return f"{section_name} contains unsupported keys: {joined}; supported keys are {supported}"

    return None


def _payload_mapping(value: object, *, field_name: str) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Return a defensive mapping copy from a dict or pydantic model."""
    if isinstance(value, dict):
        return copy.deepcopy(value), None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python", exclude_none=True), None
    return None, _error_result(f"{field_name} must be an object")


def _optional_mapping_field(request: dict[str, object], field_name: str) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Return an optional mapping payload or an MCP error envelope."""
    raw = request.get(field_name)
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, BaseModel):
        return raw.model_dump(mode="python", exclude_none=True), None
    return None, _error_result(f"{field_name} must be an object")


def _validate_string(value: object, *, field_name: str) -> tuple[str | None, dict[str, object] | None]:
    """Return a validated string scalar or an MCP error envelope."""
    if not isinstance(value, str):
        return None, _error_result(f"{field_name} must be a string")
    return value, None


def _validate_string_list(value: object, *, field_name: str) -> tuple[list[str] | None, dict[str, object] | None]:
    """Return a validated list[str] or an MCP error envelope."""
    if not isinstance(value, list):
        return None, _error_result(f"{field_name} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            return None, _error_result(f"{field_name}[{index}] must be a string")
    return value, None


def _normalize_active_checks(active_checks: list[str]) -> list[str]:
    """Trim and dedupe active check identifiers before they are compared."""
    return _unique_strings(item.strip() for item in active_checks if item.strip())


def _validate_boolean(value: object, *, field_name: str) -> tuple[bool | None, dict[str, object] | None]:
    """Return a validated bool or an MCP error envelope."""
    if value is None:
        return None, None
    if not isinstance(value, bool):
        return None, _error_result(f"{field_name} must be a boolean")
    return value, None


def _validate_number(value: object, *, field_name: str) -> tuple[int | float | None, dict[str, object] | None]:
    """Return a validated numeric scalar without accepting bools."""
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, _error_result(f"{field_name} must be a number")
    return value, None


def _validate_string_mapping(
    value: object,
    *,
    field_name: str,
) -> tuple[dict[str, str] | None, dict[str, object] | None]:
    """Return a validated dict[str, str] or an MCP error envelope."""
    if not isinstance(value, dict):
        return None, _error_result(f"{field_name} must be an object with string keys and string values")

    validated: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None, _error_result(f"{field_name} keys must be strings")
        if not isinstance(item, str):
            return None, _error_result(f"{field_name}[{key}] must be a string")
        validated[key] = item
    return validated, None


def _validate_int_list(value: object, *, field_name: str) -> tuple[list[int] | None, dict[str, object] | None]:
    """Return a validated list[int] or an MCP error envelope."""
    if not isinstance(value, list):
        return None, _error_result(f"{field_name} must be a list of integers")
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, int):
            return None, _error_result(f"{field_name}[{index}] must be an integer")
    return value, None

# ─── Dimension Parsing ────────────────────────────────────────────────────────

# Base dimensions: [M], [L], [T], [Q], [Theta]
_DIM_PATTERN = re.compile(r"\[([MLTQ]|Theta)\](?:\^([+-]?\d+))?")


def _parse_dimensions(expr: str) -> dict[str, int]:
    """Parse a dimensional expression like '[M][L]^2[T]^-2' into {M: 1, L: 2, T: -2}."""
    dims: dict[str, int] = {"M": 0, "L": 0, "T": 0, "Q": 0, "Theta": 0}
    for match in _DIM_PATTERN.finditer(expr):
        dim = match.group(1)
        power = int(match.group(2)) if match.group(2) else 1
        dims[dim] += power
    return dims


def _dims_equal(a: dict[str, int], b: dict[str, int]) -> bool:
    """Check if two dimensional dicts are equal."""
    all_keys = set(a.keys()) | set(b.keys())
    return all(a.get(k, 0) == b.get(k, 0) for k in all_keys)


# ─── MCP Tools ────────────────────────────────────────────────────────────────


@mcp.tool()
def run_check(check_id: str, domain: str, artifact_content: str) -> dict:
    """Run a specific verification check on an artifact.

    Returns the check result with evidence and confidence.
    The actual physics verification is performed by the calling agent;
    this tool provides the check specification, what to look for,
    and structured result formatting.

    Args:
        check_id: Check identifier (e.g., "5.1", "5.3")
        domain: Physics domain for domain-specific guidance
        artifact_content: The content to verify (derivation, code, etc.)
    """
    with gpd_span("mcp.verification.run_check", check_type=check_id, domain=domain):
        try:
            check_meta = get_verification_check(check_id)
            if check_meta is None:
                return _error_result(
                    f"Unknown check_id: {check_id}. Valid check ids: {list(VERIFICATION_CHECK_IDS)}"
                )

            # Get domain-specific guidance
            domain_checks = DOMAIN_CHECKLISTS.get(domain, [])
            relevant_domain_checks = [
                c
                for c in domain_checks
                if check_meta.check_id in [token.strip() for token in c.get("check_ids", "").split(",") if token.strip()]
            ]

            # Scan artifact for obvious issues
            issues: list[str] = []
            artifact_lower = artifact_content.lower()

            if check_meta.check_id == "5.1":
                # Dimensional analysis: look for common pitfalls
                if "hbar" not in artifact_content and "\\hbar" not in artifact_content:
                    if any(kw in artifact_lower for kw in ["quantum", "planck", "commutator"]):
                        issues.append("Quantum context detected but no hbar found -- check natural unit conventions")
                if re.search(r"exp\s*\([^)]*\[(?:M|L|T|Q|Theta)\]", artifact_content):
                    issues.append("Possible dimensionful argument to exponential")

            elif check_meta.check_id == "5.3":
                # Limiting cases: check if any limits are discussed
                limit_keywords = ["limit", "->", "\\to", "limiting", "reduces to", "special case"]
                has_limits = any(kw in artifact_lower for kw in limit_keywords)
                if not has_limits:
                    issues.append("No limiting case analysis found in artifact")

            elif check_meta.check_id == "5.15":
                limit_keywords = ["limit", "asymptotic", "boundary", "scaling", "regime", "\\to", "->"]
                if not any(kw in artifact_lower for kw in limit_keywords):
                    issues.append("No explicit contracted limit or asymptotic regime found in artifact")

            elif check_meta.check_id == "5.16":
                benchmark_keywords = ["benchmark", "baseline", "published", "reference", "prior work", "agreement"]
                if not any(kw in artifact_lower for kw in benchmark_keywords):
                    issues.append("No decisive benchmark or baseline comparison found in artifact")

            elif check_meta.check_id == "5.17":
                proxy_keywords = ["proxy", "surrogate", "heuristic", "loss", "trend", "qualitative"]
                direct_keywords = ["direct", "benchmark", "observable", "measured", "ground truth", "anchor"]
                if any(kw in artifact_lower for kw in proxy_keywords) and not any(
                    kw in artifact_lower for kw in direct_keywords
                ):
                    issues.append("Proxy or surrogate evidence appears without a direct anchor comparison")

            elif check_meta.check_id == "5.18":
                fit_keywords = ["fit", "regression", "extrapolat", "ansatz", "model family"]
                diagnostics = ["residual", "aic", "bic", "cross-validation", "goodness of fit", "family comparison"]
                if any(kw in artifact_lower for kw in fit_keywords) and not any(kw in artifact_lower for kw in diagnostics):
                    issues.append("Fit family is present without residual or family-selection diagnostics")

            elif check_meta.check_id == "5.19":
                estimator_keywords = ["estimator", "bootstrap", "jackknife", "posterior", "bayesian", "reweight"]
                diagnostics = ["bias", "variance", "consistency", "calibration", "ess", "autocorrelation"]
                if any(kw in artifact_lower for kw in estimator_keywords) and not any(
                    kw in artifact_lower for kw in diagnostics
                ):
                    issues.append("Estimator family is present without bias/variance or calibration diagnostics")

            result = _serialize_verification_check_entry(check_meta.model_dump())
            result.update(
                {
                    "check_name": check_meta.name,
                    "domain": domain,
                    "domain_specific_checks": relevant_domain_checks,
                    "automated_issues": issues,
                    "artifact_length": len(artifact_content),
                    "guidance": (
                        f"Run check {check_meta.check_id} ({check_meta.name}) for domain '{domain}'. "
                        f"This check catches: {check_meta.catches}."
                    ),
                }
            )
            return stable_mcp_response(result)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


def _truthy(value: object) -> bool:
    return value in (True, "true", "True", 1, "1", "yes", "YES")


_BINDING_TARGETS: tuple[str, ...] = (
    "observable",
    "claim",
    "deliverable",
    "acceptance_test",
    "reference",
    "forbidden_proxy",
)
_SUPPORTED_BINDING_KEY_LABELS: tuple[str, ...] = tuple(f"{target}_id(s)" for target in _BINDING_TARGETS)
_SUPPORTED_BINDING_KEYS: dict[str, str] = {
    key: target
    for target in _BINDING_TARGETS
    for key in (f"{target}_id", f"{target}_ids")
}


def _binding_key_labels_for_targets(targets: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    labels: list[str] = []
    for target in targets:
        label = f"{target}_id(s)"
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def _supported_binding_fields_for_targets(targets: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for target in targets:
        for suffix in ("id", "ids"):
            field = f"binding.{target}_{suffix}"
            if field in seen:
                continue
            seen.add(field)
            fields.append(field)
    return fields


def _binding_values_for_target(binding: dict[str, object], target: str) -> list[str]:
    values: list[str] = []
    for key in (f"{target}_id", f"{target}_ids"):
        raw = binding.get(key)
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped:
                values.append(stripped)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        values.append(stripped)
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _binding_values_by_field_for_target(binding: dict[str, object], target: str) -> dict[str, list[str]]:
    values_by_field: dict[str, list[str]] = {}
    for key in (f"{target}_id", f"{target}_ids"):
        raw = binding.get(key)
        values: list[str] = []
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped:
                values.append(stripped)
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    stripped = item.strip()
                    if stripped:
                        values.append(stripped)
        unique = _unique_strings(values)
        if unique:
            values_by_field[key] = unique
    return values_by_field


def _binding_claim_contexts(
    *,
    binding_ids: dict[str, list[str]],
    contract: ResearchContract,
) -> dict[str, list[str]]:
    """Return the claim IDs implied by each binding target family."""

    claims_by_id = {claim.id: claim for claim in contract.claims}
    claims_by_deliverable = _claim_ids_by_deliverable(contract)
    tests_by_id = {test.id: test for test in contract.acceptance_tests}
    forbidden_proxies_by_id = {proxy.id: proxy for proxy in contract.forbidden_proxies}

    contexts: dict[str, list[str]] = {}

    claim_ids = _unique_strings(binding_ids.get("claim", []))
    if claim_ids:
        contexts["claim"] = [claim_id for claim_id in claim_ids if claim_id in claims_by_id]

    deliverable_claim_ids: list[str] = []
    for deliverable_id in _unique_strings(binding_ids.get("deliverable", [])):
        deliverable_claim_ids.extend(claims_by_deliverable.get(deliverable_id, []))
    if binding_ids.get("deliverable"):
        contexts["deliverable"] = _unique_strings(deliverable_claim_ids)

    acceptance_test_claim_ids: list[str] = []
    for test_id in _unique_strings(binding_ids.get("acceptance_test", [])):
        test = tests_by_id.get(test_id)
        if test is None:
            continue
        acceptance_test_claim_ids.extend(
            _claim_ids_for_subject(
                test.subject,
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
            )
        )
    if binding_ids.get("acceptance_test"):
        contexts["acceptance_test"] = _unique_strings(acceptance_test_claim_ids)

    forbidden_proxy_claim_ids: list[str] = []
    for forbidden_proxy_id in _unique_strings(binding_ids.get("forbidden_proxy", [])):
        forbidden_proxy = forbidden_proxies_by_id.get(forbidden_proxy_id)
        if forbidden_proxy is None:
            continue
        forbidden_proxy_claim_ids.extend(
            _claim_ids_for_subject(
                forbidden_proxy.subject,
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
            )
        )
    if binding_ids.get("forbidden_proxy"):
        contexts["forbidden_proxy"] = _unique_strings(forbidden_proxy_claim_ids)

    return contexts


def _binding_claim_context_issue(
    *,
    binding_ids: dict[str, list[str]],
    contract: ResearchContract | None,
) -> str | None:
    """Return an error when claim/deliverable/acceptance-test bindings disagree."""

    if contract is None:
        return None

    contexts = _binding_claim_contexts(binding_ids=binding_ids, contract=contract)
    provided_contexts = [(name, values) for name, values in contexts.items()]
    if len(provided_contexts) < 2:
        return None

    expected = set(provided_contexts[0][1])
    for _name, values in provided_contexts[1:]:
        if set(values) != expected:
            details = "; ".join(f"{name} -> {', '.join(values)}" for name, values in provided_contexts)
            return f"binding contexts disagree on claim targets; {details}"

    return None


def _contract_ids_for_target(contract: ResearchContract, target: str) -> set[str]:
    if target == "observable":
        return {observable.id for observable in contract.observables}
    if target == "claim":
        return {claim.id for claim in contract.claims}
    if target == "deliverable":
        return {deliverable.id for deliverable in contract.deliverables}
    if target == "acceptance_test":
        return {test.id for test in contract.acceptance_tests}
    if target == "reference":
        return {reference.id for reference in contract.references}
    if target == "forbidden_proxy":
        return {proxy.id for proxy in contract.forbidden_proxies}
    return set()


def _validate_bound_contract_ids(
    *,
    binding: dict[str, object],
    allowed_targets: Iterable[str],
    contract: ResearchContract | None,
) -> str | None:
    if contract is None:
        return None

    for target in allowed_targets:
        known_ids = _contract_ids_for_target(contract, target)
        for field_name, values in _binding_values_by_field_for_target(binding, target).items():
            unknown_values = [value for value in values if value not in known_ids]
            if unknown_values:
                return f"binding.{field_name} references unknown contract {target} {', '.join(unknown_values)}"
    return None


def _collect_binding_context(
    *,
    check_targets: Iterable[str],
    binding: dict[str, object],
    contract: ResearchContract | None,
    binding_supplied: bool,
) -> tuple[dict[str, list[str]], list[str], list[str]]:
    """Return valid binding ids by target, user-facing issues, and contract impacts."""

    check_targets = tuple(check_targets)
    valid_by_target: dict[str, list[str]] = {}
    binding_issues: list[str] = []
    contract_impacts: list[str] = []

    for target in check_targets:
        values = _binding_values_for_target(binding, target)
        if not values:
            continue
        if contract is None:
            valid_by_target[target] = values
            contract_impacts.extend(values)
            continue

        valid_by_target[target] = values
        contract_impacts.extend(values)

    if binding_supplied and not any(valid_by_target.values()):
        expected = ", ".join(_binding_key_labels_for_targets(check_targets))
        binding_issues.append(
            "binding must include at least one valid bound ID for this check"
            + (f" via {expected}" if expected else "")
        )

    return valid_by_target, binding_issues, contract_impacts


def _decisive_contract_impacts(
    *,
    check_key: str,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    binding_supplied: bool,
    metadata: dict[str, object],
) -> list[str]:
    if contract is None:
        return []

    if check_key == "contract.benchmark_reproduction":
        source_reference_id = _normalize_optional_scalar_str(metadata.get("source_reference_id"))
        if source_reference_id:
            return [source_reference_id]
        candidates, _ = _benchmark_reference_candidates(
            contract,
            binding_ids,
            binding_supplied=binding_supplied,
        )
        return candidates

    if check_key == "contract.limit_recovery":
        regime_label = _normalize_optional_scalar_str(metadata.get("regime_label"))
        if not regime_label:
            candidates, _ = _limit_regime_candidates(
                contract,
                binding_ids,
                binding_supplied=binding_supplied,
            )
            if len(candidates) == 1:
                regime_label = candidates[0]
        resolved_binding_ids = _binding_ids_with_regime(contract, binding_ids, regime_label)
        impacts = [
            *resolved_binding_ids.get("claim", []),
            *resolved_binding_ids.get("observable", []),
        ]
        if impacts:
            return _unique_strings(impacts)
        limit_test = _resolve_single_limit_acceptance_test(contract, resolved_binding_ids)
        if limit_test is not None:
            return [limit_test.id]
        return []

    if check_key == "contract.direct_proxy_consistency":
        candidates, _ = _direct_proxy_candidates(
            contract,
            binding_ids,
            binding_supplied=binding_supplied,
        )
        return candidates

    return []


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _claim_ids_by_deliverable(contract: ResearchContract) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for claim in contract.claims:
        for deliverable_id in claim.deliverables:
            mapping.setdefault(deliverable_id, []).append(claim.id)
    return mapping


def _claim_ids_for_subject(
    subject_id: str,
    *,
    claims_by_id: dict[str, object],
    claims_by_deliverable: dict[str, list[str]],
) -> list[str]:
    claim_ids: list[str] = []
    if subject_id in claims_by_id:
        claim_ids.append(subject_id)
    claim_ids.extend(claims_by_deliverable.get(subject_id, []))
    return _unique_strings(claim_ids)


def _resolve_binding_candidates(
    *,
    label: str,
    context_candidates: dict[str, list[str]],
) -> tuple[list[str], str | None]:
    non_empty = [(context, candidates) for context, candidates in context_candidates.items() if candidates]
    if not non_empty:
        return [], None

    intersection = set(non_empty[0][1])
    for _, candidates in non_empty[1:]:
        intersection.intersection_update(candidates)

    if intersection:
        agreed: list[str] = []
        for _, candidates in non_empty:
            for candidate in candidates:
                if candidate in intersection and candidate not in agreed:
                    agreed.append(candidate)
        return agreed, None

    details = "; ".join(f"{context} -> {', '.join(candidates)}" for context, candidates in non_empty)
    return [], f"binding contexts disagree on {label}; {details}"


def _benchmark_references_for_subject_ids(
    subject_ids: Iterable[str],
    *,
    benchmark_refs: list[object],
    benchmark_reference_ids: set[str],
    claims_by_id: dict[str, object],
    claims_by_deliverable: dict[str, list[str]],
) -> list[str]:
    candidate_reference_ids: list[str] = []
    normalized_subject_ids = _unique_strings(subject_ids)
    for reference in benchmark_refs:
        if set(reference.applies_to).intersection(normalized_subject_ids):
            candidate_reference_ids.append(reference.id)

    claim_ids: list[str] = []
    for subject_id in normalized_subject_ids:
        claim_ids.extend(
            _claim_ids_for_subject(
                subject_id,
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
            )
        )

    for claim_id in _unique_strings(claim_ids):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        candidate_reference_ids.extend(
            reference_id
            for reference_id in claim.references
            if reference_id in benchmark_reference_ids
        )

    return _unique_strings(candidate_reference_ids)


def _benchmark_reference_candidates(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
    *,
    binding_supplied: bool,
) -> tuple[list[str], str | None]:
    benchmark_refs = [
        reference
        for reference in contract.references
        if reference.role == "benchmark" or "compare" in reference.required_actions
    ]
    references_by_id = {reference.id: reference for reference in benchmark_refs}
    claims_by_id = {claim.id: claim for claim in contract.claims}
    tests_by_id = {test.id: test for test in contract.acceptance_tests}
    claims_by_deliverable = _claim_ids_by_deliverable(contract)

    context_candidates: dict[str, list[str]] = {}
    reference_candidates = [
        reference_id for reference_id in binding_ids.get("reference", []) if reference_id in references_by_id
    ]
    if reference_candidates:
        context_candidates["reference"] = _unique_strings(reference_candidates)

    claim_candidates = _benchmark_references_for_subject_ids(
        binding_ids.get("claim", []),
        benchmark_refs=benchmark_refs,
        benchmark_reference_ids=set(references_by_id),
        claims_by_id=claims_by_id,
        claims_by_deliverable=claims_by_deliverable,
    )
    if claim_candidates:
        context_candidates["claim"] = claim_candidates

    deliverable_candidates = _benchmark_references_for_subject_ids(
        binding_ids.get("deliverable", []),
        benchmark_refs=benchmark_refs,
        benchmark_reference_ids=set(references_by_id),
        claims_by_id=claims_by_id,
        claims_by_deliverable=claims_by_deliverable,
    )
    if deliverable_candidates:
        context_candidates["deliverable"] = deliverable_candidates

    acceptance_test_candidates: list[str] = []
    for test_id in binding_ids.get("acceptance_test", []):
        test = tests_by_id.get(test_id)
        if test is None:
            continue
        direct_benchmark_refs = [evidence_id for evidence_id in test.evidence_required if evidence_id in references_by_id]
        if direct_benchmark_refs:
            acceptance_test_candidates.extend(direct_benchmark_refs)
            continue
        acceptance_test_candidates.extend(
            _benchmark_references_for_subject_ids(
                [test.subject],
                benchmark_refs=benchmark_refs,
                benchmark_reference_ids=set(references_by_id),
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
            )
        )
    if acceptance_test_candidates:
        context_candidates["acceptance_test"] = _unique_strings(acceptance_test_candidates)

    candidates, issue = _resolve_binding_candidates(
        label="benchmark reference candidates",
        context_candidates=context_candidates,
    )
    if candidates or issue:
        return candidates, issue

    if not binding_supplied and not binding_ids and len(benchmark_refs) == 1:
        return [benchmark_refs[0].id], None

    return [], None


def _direct_proxy_candidates(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
    *,
    binding_supplied: bool,
) -> tuple[list[str], str | None]:
    forbidden_proxies = list(contract.forbidden_proxies)
    proxies_by_id = {proxy.id: proxy for proxy in forbidden_proxies}
    claims_by_id = {claim.id: claim for claim in contract.claims}
    tests_by_id = {test.id: test for test in contract.acceptance_tests}
    claims_by_deliverable = _claim_ids_by_deliverable(contract)

    def _proxy_candidates_for_subject_ids(subject_ids: Iterable[str]) -> list[str]:
        normalized_subject_ids = _unique_strings(subject_ids)
        if not normalized_subject_ids:
            return []

        bound_claim_ids: list[str] = []
        bound_deliverable_ids: list[str] = []
        for subject_id in normalized_subject_ids:
            bound_claim_ids.extend(
                _claim_ids_for_subject(
                    subject_id,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
            bound_deliverable_ids.extend(
                _deliverable_ids_for_subject(
                    subject_id,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )

        bound_claim_set = set(_unique_strings(bound_claim_ids))
        bound_deliverable_set = set(_unique_strings(bound_deliverable_ids))
        candidates: list[str] = []
        for forbidden_proxy in forbidden_proxies:
            if forbidden_proxy.subject in normalized_subject_ids:
                candidates.append(forbidden_proxy.id)
                continue
            proxy_claim_ids = set(
                _claim_ids_for_subject(
                    forbidden_proxy.subject,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
            if proxy_claim_ids.intersection(bound_claim_set):
                candidates.append(forbidden_proxy.id)
                continue
            proxy_deliverable_ids = set(
                _deliverable_ids_for_subject(
                    forbidden_proxy.subject,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
            if proxy_deliverable_ids.intersection(bound_deliverable_set):
                candidates.append(forbidden_proxy.id)
        return _unique_strings(candidates)

    context_candidates: dict[str, list[str]] = {}
    direct_candidates = [
        forbidden_proxy_id
        for forbidden_proxy_id in binding_ids.get("forbidden_proxy", [])
        if forbidden_proxy_id in proxies_by_id
    ]
    if direct_candidates:
        context_candidates["forbidden_proxy"] = _unique_strings(direct_candidates)

    claim_candidates = _proxy_candidates_for_subject_ids(binding_ids.get("claim", []))
    if claim_candidates:
        context_candidates["claim"] = claim_candidates

    deliverable_candidates = _proxy_candidates_for_subject_ids(binding_ids.get("deliverable", []))
    if deliverable_candidates:
        context_candidates["deliverable"] = deliverable_candidates

    acceptance_test_candidates: list[str] = []
    for test_id in binding_ids.get("acceptance_test", []):
        test = tests_by_id.get(test_id)
        if test is None:
            continue
        acceptance_test_candidates.extend(_proxy_candidates_for_subject_ids([test.subject]))
    if acceptance_test_candidates:
        context_candidates["acceptance_test"] = _unique_strings(acceptance_test_candidates)

    candidates, issue = _resolve_binding_candidates(
        label="forbidden proxy candidates",
        context_candidates=context_candidates,
    )
    if candidates or issue:
        return candidates, issue

    if not binding_supplied and not binding_ids and len(forbidden_proxies) == 1:
        return [forbidden_proxies[0].id], None

    return [], None


def _regimes_for_claim_ids(
    claim_ids: Iterable[str],
    *,
    claims_by_id: dict[str, object],
    observables_by_id: dict[str, object],
) -> list[str]:
    candidate_regimes: list[str] = []
    for claim_id in _unique_strings(claim_ids):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        for observable_id in claim.observables:
            observable = observables_by_id.get(observable_id)
            if observable is not None and observable.regime:
                candidate_regimes.append(observable.regime)
    return _unique_strings(candidate_regimes)


def _limit_regimes_for_subject_ids(
    subject_ids: Iterable[str],
    *,
    claims_by_id: dict[str, object],
    claims_by_deliverable: dict[str, list[str]],
    observables_by_id: dict[str, object],
) -> list[str]:
    claim_ids: list[str] = []
    for subject_id in _unique_strings(subject_ids):
        claim_ids.extend(
            _claim_ids_for_subject(
                subject_id,
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
            )
        )
    return _regimes_for_claim_ids(
        claim_ids,
        claims_by_id=claims_by_id,
        observables_by_id=observables_by_id,
    )


def _limit_regime_candidates(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
    *,
    binding_supplied: bool,
) -> tuple[list[str], str | None]:
    observables_by_id = {observable.id: observable for observable in contract.observables}
    claims_by_id = {claim.id: claim for claim in contract.claims}
    tests_by_id = {test.id: test for test in contract.acceptance_tests}
    references_by_id = {reference.id: reference for reference in contract.references}
    claims_by_deliverable = _claim_ids_by_deliverable(contract)

    context_candidates: dict[str, list[str]] = {}
    observable_candidates: list[str] = []
    for observable_id in binding_ids.get("observable", []):
        observable = observables_by_id.get(observable_id)
        if observable is not None and observable.regime:
            observable_candidates.append(observable.regime)
    if observable_candidates:
        context_candidates["observable"] = _unique_strings(observable_candidates)

    claim_candidates = _limit_regimes_for_subject_ids(
        binding_ids.get("claim", []),
        claims_by_id=claims_by_id,
        claims_by_deliverable=claims_by_deliverable,
        observables_by_id=observables_by_id,
    )
    if claim_candidates:
        context_candidates["claim"] = claim_candidates

    deliverable_candidates = _limit_regimes_for_subject_ids(
        binding_ids.get("deliverable", []),
        claims_by_id=claims_by_id,
        claims_by_deliverable=claims_by_deliverable,
        observables_by_id=observables_by_id,
    )
    if deliverable_candidates:
        context_candidates["deliverable"] = deliverable_candidates

    acceptance_test_candidates: list[str] = []
    for test_id in binding_ids.get("acceptance_test", []):
        test = tests_by_id.get(test_id)
        if test is not None:
            acceptance_test_candidates.extend(
                _limit_regimes_for_subject_ids(
                    [test.subject],
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                    observables_by_id=observables_by_id,
                )
            )
    if acceptance_test_candidates:
        context_candidates["acceptance_test"] = _unique_strings(acceptance_test_candidates)

    reference_candidates: list[str] = []
    for reference_id in binding_ids.get("reference", []):
        reference = references_by_id.get(reference_id)
        if reference is None:
            continue
        reference_candidates.extend(
            _limit_regimes_for_subject_ids(
                reference.applies_to,
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
                observables_by_id=observables_by_id,
            )
        )
    if reference_candidates:
        context_candidates["reference"] = _unique_strings(reference_candidates)

    candidates, issue = _resolve_binding_candidates(
        label="limit regime candidates",
        context_candidates=context_candidates,
    )
    if candidates or issue:
        return candidates, issue

    global_regimes = _unique_strings(
        observable.regime for observable in contract.observables if observable.regime
    )
    if not binding_supplied and not binding_ids and len(global_regimes) == 1:
        return global_regimes, None
    return [], None


def _deliverable_ids_for_subject(
    subject_id: str,
    *,
    claims_by_id: dict[str, object],
    claims_by_deliverable: dict[str, list[str]],
) -> list[str]:
    claim = claims_by_id.get(subject_id)
    if claim is not None:
        return _unique_strings(claim.deliverables)
    if subject_id in claims_by_deliverable:
        return [subject_id]
    return []


def _observable_ids_for_subject(
    subject_id: str,
    *,
    claims_by_id: dict[str, object],
    claims_by_deliverable: dict[str, list[str]],
) -> list[str]:
    observable_ids: list[str] = []
    for claim_id in _claim_ids_for_subject(
        subject_id,
        claims_by_id=claims_by_id,
        claims_by_deliverable=claims_by_deliverable,
    ):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        observable_ids.extend(claim.observables)
    return _unique_strings(observable_ids)


def _resolve_single_limit_acceptance_test(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
) -> object | None:
    """Return the uniquely bound limiting-case acceptance test when one can be resolved."""

    limit_tests = _matching_acceptance_tests(
        contract,
        kinds=("limiting_case",),
        keywords=("limit", "asymptotic", "boundary", "scaling"),
    )
    if not limit_tests:
        return None

    tests_by_id = {test.id: test for test in limit_tests}
    bound_acceptance_tests = [
        tests_by_id[test_id]
        for test_id in binding_ids.get("acceptance_test", [])
        if test_id in tests_by_id
    ]
    if len(bound_acceptance_tests) == 1:
        return bound_acceptance_tests[0]
    if len(bound_acceptance_tests) > 1:
        return None

    claims_by_id = {claim.id: claim for claim in contract.claims}
    claims_by_deliverable = _claim_ids_by_deliverable(contract)
    references_by_id = {reference.id: reference for reference in contract.references}
    candidates = list(limit_tests)

    claim_ids = set(binding_ids.get("claim", []))
    if claim_ids:
        candidates = [
            test
            for test in candidates
            if claim_ids.intersection(
                _claim_ids_for_subject(
                    test.subject,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
        ]

    deliverable_ids = set(binding_ids.get("deliverable", []))
    if deliverable_ids:
        candidates = [
            test
            for test in candidates
            if deliverable_ids.intersection(
                _deliverable_ids_for_subject(
                    test.subject,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
        ]

    observable_ids = set(binding_ids.get("observable", []))
    if observable_ids:
        candidates = [
            test
            for test in candidates
            if observable_ids.intersection(
                _observable_ids_for_subject(
                    test.subject,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
        ]

    reference_ids = set(binding_ids.get("reference", []))
    if reference_ids:
        reference_subject_claim_ids: set[str] = set()
        for reference_id in reference_ids:
            reference = references_by_id.get(reference_id)
            if reference is None:
                continue
            for subject_id in reference.applies_to:
                reference_subject_claim_ids.update(
                    _claim_ids_for_subject(
                        subject_id,
                        claims_by_id=claims_by_id,
                        claims_by_deliverable=claims_by_deliverable,
                    )
                )
        candidates = [
            test
            for test in candidates
            if reference_ids.intersection(test.evidence_required)
            or reference_subject_claim_ids.intersection(
                _claim_ids_for_subject(
                    test.subject,
                    claims_by_id=claims_by_id,
                    claims_by_deliverable=claims_by_deliverable,
                )
            )
        ]

    return candidates[0] if len(candidates) == 1 else None


def _summarize_contract_salvage_errors(errors: list[str]) -> str:
    if not errors:
        return ""
    summary = "; ".join(errors[:3])
    if len(errors) > 3:
        summary += f"; +{len(errors) - 3} more"
    return summary


def _contract_payload_error(errors: list[str]) -> dict[str, object]:
    details = list(dict.fromkeys(errors))
    if not details:
        return _error_result("Invalid contract payload")
    message = f"Invalid contract payload: {_summarize_contract_salvage_errors(details)}"
    if len(details) == 1:
        return _error_result(message)
    return stable_mcp_response({"contract_error_details": details}, error=message)


def _validate_contract_schema_version(raw: object) -> dict[str, object] | None:
    """Reject unsupported contract schema versions without coercing or salvaging them."""

    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        return _error_result("Invalid contract payload: schema_version must be the integer 1")
    if raw != VERIFICATION_SCHEMA_VERSION:
        return _error_result(f"Invalid contract payload: schema_version must be {VERIFICATION_SCHEMA_VERSION}")
    return None


def _validate_contract_scalar_fields(contract_raw: dict[str, object]) -> dict[str, object] | None:
    """Reject coercive scalar contract fields before Pydantic can canonicalize them."""

    errors: list[str] = []
    _sanitize_contract_scalars(contract_raw, errors=errors)
    errors = list(dict.fromkeys(errors))
    if not errors:
        return None
    return _contract_payload_error(errors)


def _validate_contract_list_members(contract_raw: dict[str, object]) -> dict[str, object] | None:
    """Reject blank or malformed string-list members before contract salvage can hide them."""

    errors: list[str] = []

    def _validate_scalar_list_drift(container: object, field_name: str) -> None:
        if isinstance(container, str) and not container.strip():
            errors.append(f"{field_name} must not be blank")

    def _validate_list_field(container: object, field_name: str) -> None:
        _validate_scalar_list_drift(container, field_name)
        error = _validate_string_list_members(container, field_name=field_name)
        if error is not None:
            errors.append(error)

    def _validate_object_lists(container: object, prefix: str, fields: Iterable[str]) -> None:
        if not isinstance(container, dict):
            return
        for field_name in fields:
            if field_name in container:
                _validate_list_field(container[field_name], f"{prefix}.{field_name}")

    _validate_object_lists(contract_raw.get("scope"), "scope", ("in_scope", "out_of_scope", "unresolved_questions"))
    _validate_object_lists(
        contract_raw.get("context_intake"),
        "context_intake",
        (
            "must_read_refs",
            "must_include_prior_outputs",
            "user_asserted_anchors",
            "known_good_baselines",
            "context_gaps",
            "crucial_inputs",
        ),
    )
    _validate_object_lists(
        contract_raw.get("approach_policy"),
        "approach_policy",
        (
            "formulations",
            "allowed_estimator_families",
            "forbidden_estimator_families",
            "allowed_fit_families",
            "forbidden_fit_families",
            "stop_and_rethink_conditions",
        ),
    )

    claims = contract_raw.get("claims")
    if isinstance(claims, list):
        for index, claim in enumerate(claims):
            _validate_object_lists(
                claim,
                f"claims.{index}",
                ("observables", "deliverables", "acceptance_tests", "references"),
            )

    deliverables = contract_raw.get("deliverables")
    if isinstance(deliverables, list):
        for index, deliverable in enumerate(deliverables):
            _validate_object_lists(deliverable, f"deliverables.{index}", ("must_contain",))

    acceptance_tests = contract_raw.get("acceptance_tests")
    if isinstance(acceptance_tests, list):
        for index, acceptance_test in enumerate(acceptance_tests):
            _validate_object_lists(acceptance_test, f"acceptance_tests.{index}", ("evidence_required",))

    references = contract_raw.get("references")
    if isinstance(references, list):
        for index, reference in enumerate(references):
            _validate_object_lists(
                reference,
                f"references.{index}",
                ("aliases", "applies_to", "carry_forward_to", "required_actions"),
            )

    links = contract_raw.get("links")
    if isinstance(links, list):
        for index, link in enumerate(links):
            _validate_object_lists(link, f"links.{index}", ("verified_by",))

    uncertainty_markers = contract_raw.get("uncertainty_markers")
    _validate_object_lists(
        uncertainty_markers,
        "uncertainty_markers",
        (
            "weakest_anchors",
            "unvalidated_assumptions",
            "competing_explanations",
            "disconfirming_observations",
        ),
    )

    if not errors:
        return None
    return _contract_payload_error(errors)


def _validate_contract_integrity(contract: ResearchContract) -> dict[str, object] | None:
    """Reject semantically ambiguous contracts after structural validation."""

    errors = collect_contract_integrity_errors(contract)
    if not errors:
        return None
    return _contract_payload_error(errors)


def _parse_contract_payload(contract_raw: dict[str, object]) -> tuple[ResearchContract | None, list[str], dict | None]:
    schema_error = _validate_contract_schema_version(contract_raw.get("schema_version"))
    if schema_error is not None:
        return None, [], schema_error
    scalar_error = _validate_contract_scalar_fields(contract_raw)
    if scalar_error is not None:
        return None, [], scalar_error
    list_member_error = _validate_contract_list_members(contract_raw)
    if list_member_error is not None:
        return None, [], list_member_error
    try:
        contract = ResearchContract.model_validate(contract_raw)
        integrity_error = _validate_contract_integrity(contract)
        if integrity_error is not None:
            return None, [], integrity_error
        return contract, [], None
    except PydanticValidationError as exc:
        contract, salvage_errors = salvage_project_contract(contract_raw)
        if contract is not None:
            recoverable, blocking = _split_project_contract_schema_findings(
                salvage_errors,
                allow_singleton_defaults=False,
            )
            if not blocking:
                integrity_error = _validate_contract_integrity(contract)
                if integrity_error is not None:
                    return None, [], integrity_error
                return contract, recoverable, None
            return None, [], _contract_payload_error(blocking)
        if salvage_errors:
            return None, [], _contract_payload_error(salvage_errors)
        return None, [], _error_result(f"Invalid contract payload: {exc}")


def _validate_benchmark_reference_binding(
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    binding_supplied: bool,
    source_reference_id: object,
) -> tuple[str | None, str | None]:
    """Validate that a benchmark anchor exists and matches the bound contract context."""

    source_reference_id = _normalize_optional_scalar_str(source_reference_id)
    if not isinstance(source_reference_id, str) or not source_reference_id:
        return None, None
    if contract is None:
        return source_reference_id, None
    if source_reference_id not in _contract_ids_for_target(contract, "reference"):
        return None, f"metadata.source_reference_id references unknown contract reference {source_reference_id}"

    candidates, candidate_issue = _benchmark_reference_candidates(
        contract,
        binding_ids,
        binding_supplied=binding_supplied,
    )
    if candidate_issue:
        return None, candidate_issue
    if candidates and source_reference_id not in candidates:
        expected = ", ".join(candidates)
        context_label = "bound contract context" if binding_ids else "resolved contract context"
        return None, (
            f"metadata.source_reference_id does not match the {context_label}; "
            f"expected one of {expected}"
        )
    return source_reference_id, None


def _validate_limit_regime_binding(
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    binding_supplied: bool,
    regime_label: object,
) -> tuple[str | None, str | None]:
    """Validate that a regime label matches the bound contract context when known."""

    regime_label = _normalize_optional_scalar_str(regime_label)
    if not isinstance(regime_label, str) or not regime_label:
        return None, None
    if contract is None:
        return regime_label, None

    candidates, candidate_issue = _limit_regime_candidates(
        contract,
        binding_ids,
        binding_supplied=binding_supplied,
    )
    if candidate_issue:
        return None, candidate_issue
    if candidates and regime_label not in candidates:
        expected = ", ".join(candidates)
        context_label = "bound contract context" if binding_ids else "resolved contract context"
        return None, (
            f"metadata.regime_label does not match the {context_label}; "
            f"expected one of {expected}"
        )
    return regime_label, None


def _with_contract_policy_defaults(
    check_key: str,
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    binding_supplied: bool,
    metadata: dict[str, object],
) -> dict[str, object]:
    """Fill contract-check metadata from structured contract policy when missing."""

    if contract is None:
        return metadata

    enriched = dict(metadata)
    if check_key == "contract.benchmark_reproduction" and not enriched.get("source_reference_id"):
        candidates, _ = _benchmark_reference_candidates(contract, binding_ids, binding_supplied=binding_supplied)
        if len(candidates) == 1:
            enriched["source_reference_id"] = candidates[0]

    if check_key == "contract.fit_family_mismatch":
        if not enriched.get("allowed_families") and contract.approach_policy.allowed_fit_families:
            enriched["allowed_families"] = list(contract.approach_policy.allowed_fit_families)
        if not enriched.get("forbidden_families") and contract.approach_policy.forbidden_fit_families:
            enriched["forbidden_families"] = list(contract.approach_policy.forbidden_fit_families)
        if not enriched.get("declared_family") and len(contract.approach_policy.allowed_fit_families) == 1:
            enriched["declared_family"] = contract.approach_policy.allowed_fit_families[0]

    if check_key == "contract.estimator_family_mismatch":
        if not enriched.get("allowed_families") and contract.approach_policy.allowed_estimator_families:
            enriched["allowed_families"] = list(contract.approach_policy.allowed_estimator_families)
        if not enriched.get("forbidden_families") and contract.approach_policy.forbidden_estimator_families:
            enriched["forbidden_families"] = list(contract.approach_policy.forbidden_estimator_families)
        if not enriched.get("declared_family") and len(contract.approach_policy.allowed_estimator_families) == 1:
            enriched["declared_family"] = contract.approach_policy.allowed_estimator_families[0]

    if check_key == "contract.limit_recovery":
        if not enriched.get("regime_label"):
            candidates, _ = _limit_regime_candidates(contract, binding_ids, binding_supplied=binding_supplied)
            if len(candidates) == 1:
                enriched["regime_label"] = candidates[0]
        if not enriched.get("expected_behavior"):
            resolved_binding_ids = _binding_ids_with_regime(
                contract,
                binding_ids,
                _normalize_optional_scalar_str(enriched.get("regime_label")),
            )
            limit_test = _resolve_single_limit_acceptance_test(contract, resolved_binding_ids)
            if limit_test is not None and limit_test.pass_condition:
                enriched["expected_behavior"] = limit_test.pass_condition

    return enriched


def _contains_any_keyword(values: Iterable[str], keywords: Iterable[str]) -> bool:
    haystack = " ".join(value for value in values if isinstance(value, str)).lower()
    return any(keyword in haystack for keyword in keywords)


def _set_single_binding_value(binding: dict[str, object], key: str, values: Iterable[str]) -> None:
    unique_values = _unique_strings(values)
    if len(unique_values) == 1:
        binding[key] = unique_values


def _apply_subject_binding(
    binding: dict[str, object],
    contract: ResearchContract,
    subject_id: str,
    *,
    include_observable_binding: bool = False,
) -> None:
    claim_ids = {claim.id for claim in contract.claims}
    if subject_id in claim_ids:
        binding["claim_ids"] = [subject_id]
        if include_observable_binding:
            claim = next((claim for claim in contract.claims if claim.id == subject_id), None)
            if claim is not None:
                _set_single_binding_value(binding, "observable_ids", claim.observables)
        return

    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    if subject_id in deliverable_ids:
        binding["deliverable_ids"] = [subject_id]


def _matching_acceptance_tests(
    contract: ResearchContract,
    *,
    kinds: Iterable[str] = (),
    keywords: Iterable[str] = (),
    evidence_ids: Iterable[str] = (),
) -> list[object]:
    accepted_kinds = set(kinds)
    accepted_evidence_ids = set(evidence_ids)
    matches: list[object] = []
    for test in contract.acceptance_tests:
        if accepted_kinds and test.kind in accepted_kinds:
            matches.append(test)
            continue
        if accepted_evidence_ids and accepted_evidence_ids.intersection(test.evidence_required):
            matches.append(test)
            continue
        if keywords and _contains_any_keyword((test.procedure, test.pass_condition), keywords):
            matches.append(test)
    return matches


def _apply_single_acceptance_test_binding(
    binding: dict[str, object],
    contract: ResearchContract,
    tests: list[object],
    *,
    include_observable_binding: bool = False,
) -> object | None:
    if len(tests) != 1:
        return None

    test = tests[0]
    binding["acceptance_test_ids"] = [test.id]
    _apply_subject_binding(
        binding,
        contract,
        test.subject,
        include_observable_binding=include_observable_binding,
    )
    return test


def _apply_single_acceptance_test_binding_if_consistent(
    binding: dict[str, object],
    contract: ResearchContract,
    tests: list[object],
    *,
    include_observable_binding: bool = False,
) -> object | None:
    candidate_binding = copy.deepcopy(binding)
    test = _apply_single_acceptance_test_binding(
        candidate_binding,
        contract,
        tests,
        include_observable_binding=include_observable_binding,
    )
    if test is None:
        return None

    binding_ids = {target: _binding_values_for_target(candidate_binding, target) for target in _BINDING_TARGETS}
    if _binding_claim_context_issue(binding_ids=binding_ids, contract=contract) is not None:
        return None

    binding.clear()
    binding.update(candidate_binding)
    return test


def _claim_ids_for_regime(contract: ResearchContract, regime_label: str) -> list[str]:
    observables_by_id = {observable.id: observable for observable in contract.observables}
    matching_claim_ids: list[str] = []
    for claim in contract.claims:
        if any(
            (observable := observables_by_id.get(observable_id)) is not None and observable.regime == regime_label
            for observable_id in claim.observables
        ):
            matching_claim_ids.append(claim.id)
    return matching_claim_ids


def _binding_ids_with_regime(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
    regime_label: str | None,
) -> dict[str, list[str]]:
    """Augment binding ids with regime-derived claims/observables when available."""

    resolved_binding_ids = {target: list(values) for target, values in binding_ids.items()}
    if not regime_label:
        return resolved_binding_ids
    if not resolved_binding_ids.get("claim"):
        resolved_binding_ids["claim"] = _claim_ids_for_regime(contract, regime_label)
    if not resolved_binding_ids.get("observable"):
        resolved_binding_ids["observable"] = [
            observable.id for observable in contract.observables if observable.regime == regime_label
        ]
    return resolved_binding_ids


def _validate_limit_expected_behavior_binding(
    *,
    contract: ResearchContract | None,
    binding_ids: dict[str, list[str]],
    regime_label: str | None,
    expected_behavior: object,
) -> tuple[str | None, str | None]:
    """Validate expected limit behavior against the resolved contract context when possible."""

    expected_behavior = _normalize_optional_scalar_str(expected_behavior)
    if not isinstance(expected_behavior, str) or not expected_behavior:
        return None, None
    if contract is None:
        return expected_behavior, None

    resolved_binding_ids = _binding_ids_with_regime(contract, binding_ids, regime_label)
    limit_test = _resolve_single_limit_acceptance_test(contract, resolved_binding_ids)
    if limit_test is None or not limit_test.pass_condition:
        return expected_behavior, None
    if expected_behavior != limit_test.pass_condition:
        return None, (
            "metadata.expected_behavior does not match the resolved contract context; "
            f"expected {limit_test.pass_condition}"
        )
    return expected_behavior, None


@mcp.tool()
def run_contract_check(request: RunContractCheckPayload) -> dict:
    """Run a contract-aware verification check from a single structured ``request`` object.

    ``request.check_key`` or ``request.check_id`` is required and must name a
    contract-aware verification check such as ``contract.limit_recovery`` or
    ``contract.benchmark_reproduction``.

    ``request.contract`` is optional, but when supplied it must be a project or
    phase contract object. ``schema_version`` defaults to ``1`` when omitted
    and must equal ``1`` when provided. The payload is treated as a hard schema
    boundary for authoritative fields: non-object sections,
    coercive scalars, blank strings, and malformed list members are rejected
    instead of being guessed. Recoverable scalar-to-list drift is normalized by
    the shared contract parser before verification, and benchmark prose may
    still surface a warning when direct evidence is incomplete. Contract
    payloads must also satisfy the shared semantic integrity rules: same-kind IDs must be unique.
    references[].carry_forward_to uses workflow scope labels, never contract IDs.
    target IDs must not be reused across claim/deliverable/acceptance-test/reference kinds when that would make resolution ambiguous.
    contract context must stay consistent with metadata defaults and explicit metadata fields, so benchmark anchors, regime labels, and family selections cannot contradict the resolved binding.
    payloads must also satisfy the shared semantic integrity rules: same-kind IDs must be unique, target IDs must not be reused across
    claim/deliverable/acceptance-test/reference kinds when that would make
    resolution ambiguous, and ``references[].carry_forward_to`` is only for
    workflow scope labels, never contract IDs. contract context must stay consistent with metadata defaults and explicit metadata
    fields, so benchmark anchors, regime labels, and family selections cannot
    contradict the resolved binding. Limited recoverable structural drift may
    still be salvaged, and any such recovery is surfaced back as structured
    salvage findings.

    ``request.binding``, ``request.metadata``, and ``request.observed`` are each
    optional objects. Decisive pass/fail verdicts still require the check-specific
    fields inside those objects. When ``request.binding`` is present, its keys
    must come from the per-check ``supported_binding_fields`` surfaced by
    ``suggest_contract_checks(...)``; unsupported or irrelevant binding fields
    are request errors, not soft verification issues. Singular/plural binding
    aliases (for example ``claim_id`` / ``claim_ids``) must match when both are
    provided. If both ``request.check_key`` and ``request.check_id`` are sent,
    they may use either the canonical key or the numeric id, but they must still
    identify the same verification check. ``request.artifact_content`` is
    optional and must be a string when present.

    Use ``suggest_contract_checks(contract, active_checks=...)`` first when you
    need the exact ``required_request_fields``, ``optional_request_fields``,
    ``supported_binding_fields``, and ``request_template`` for a given
    contract-aware check before calling this tool.
    """

    with gpd_span("mcp.verification.run_contract_check"):
        try:
            request, error = _payload_mapping(request, field_name="request")
            if error is not None:
                return error
            request_key_error = _validate_run_contract_check_request_keys(request)
            if request_key_error is not None:
                return _error_result(request_key_error)
            check_key_value = _normalize_optional_scalar_str(request.get("check_key"))
            check_id_value = _normalize_optional_scalar_str(request.get("check_id"))
            has_check_key = isinstance(check_key_value, str) and bool(check_key_value)
            has_check_id = isinstance(check_id_value, str) and bool(check_id_value)
            check_key_meta = get_verification_check(check_key_value) if has_check_key else None
            check_id_meta = get_verification_check(check_id_value) if has_check_id else None
            if has_check_key and has_check_id:
                if check_key_meta is None or check_id_meta is None or check_key_meta.check_id != check_id_meta.check_id:
                    return _error_result("check_key and check_id must identify the same contract check when both are provided")
                check_meta = check_key_meta
            else:
                check_meta = check_key_meta or check_id_meta
            if check_meta is None:
                check_id = str(check_key_value or check_id_value or "").strip()
                if not check_id:
                    return _error_result("Missing check_key or check_id")
                return _error_result(f"Unknown contract check: {check_id}")

            check_id = check_meta.check_id
            if not check_meta.contract_aware:
                return _error_result(f"Check {check_id} is not contract-aware")

            contract_raw, error = _optional_mapping_field(request, "contract")
            if error is not None:
                return error
            binding_raw, error = _optional_mapping_field(request, "binding")
            if error is not None:
                return error
            metadata_raw, error = _optional_mapping_field(request, "metadata")
            if error is not None:
                return error
            observed_raw, error = _optional_mapping_field(request, "observed")
            if error is not None:
                return error

            contract = None
            contract_salvage_errors: list[str] = []
            if contract_raw is not None:
                contract, contract_salvage_errors, error = _parse_contract_payload(contract_raw)
                if error is not None:
                    return error

            binding = binding_raw or {}
            binding_error = _validate_binding_payload(binding, allowed_targets=check_meta.binding_targets)
            if binding_error is not None:
                return _error_result(binding_error)
            binding_supplied = bool(binding_raw)
            metadata, metadata_error = _normalize_contract_metadata(metadata_raw or {})
            if metadata_error is not None:
                return _error_result(metadata_error)
            observed = observed_raw or {}
            artifact_content_raw = request.get("artifact_content")
            artifact_content, artifact_content_error = _validate_optional_string(
                artifact_content_raw,
                field_name="artifact_content",
            )
            if artifact_content_error is not None:
                return _error_result(artifact_content_error)
            artifact_content = artifact_content or ""
            binding_contract_error = _validate_bound_contract_ids(
                binding=binding,
                allowed_targets=check_meta.binding_targets,
                contract=contract,
            )
            if binding_contract_error is not None:
                return _error_result(binding_contract_error)
            binding_ids, binding_issues, contract_impacts = _collect_binding_context(
                check_targets=check_meta.binding_targets,
                binding=binding,
                contract=contract,
                binding_supplied=binding_supplied,
            )
            binding_context_issue = _binding_claim_context_issue(binding_ids=binding_ids, contract=contract)
            if binding_context_issue is not None:
                binding_issues.append(binding_context_issue)
            metadata = _with_contract_policy_defaults(
                check_meta.check_key,
                contract=contract,
                binding_ids=binding_ids,
                binding_supplied=binding_supplied,
                metadata=metadata,
            )

            missing_inputs: list[str] = []
            automated_issues: list[str] = []
            metrics: dict[str, object] = {}
            status = "insufficient_evidence"
            evidence_directness = "metadata_only"
            if contract_salvage_errors:
                automated_issues.append(
                    "Contract payload was salvaged before verification: "
                    + _summarize_contract_salvage_errors(contract_salvage_errors)
                )
            automated_issues.extend(binding_issues)

            if check_meta.check_key == "contract.limit_recovery":
                regime_label = metadata.get("regime_label")
                regime_label, regime_issue = _validate_limit_regime_binding(
                    contract=contract,
                    binding_ids=binding_ids,
                    binding_supplied=binding_supplied,
                    regime_label=regime_label,
                )
                if regime_issue:
                    automated_issues.append(regime_issue)
                expected_behavior, expected_behavior_issue = _validate_limit_expected_behavior_binding(
                    contract=contract,
                    binding_ids=binding_ids,
                    regime_label=regime_label,
                    expected_behavior=metadata.get("expected_behavior"),
                )
                if expected_behavior_issue:
                    automated_issues.append(expected_behavior_issue)
                if not regime_label:
                    missing_inputs.append("metadata.regime_label")
                if not expected_behavior:
                    missing_inputs.append("metadata.expected_behavior")
                limit_passed, error = _validate_boolean(observed.get("limit_passed"), field_name="observed.limit_passed")
                if error is not None:
                    return error
                observed_limit, error_message = _validate_optional_string(
                    observed.get("observed_limit"),
                    field_name="observed.observed_limit",
                )
                if error_message is not None:
                    return _error_result(error_message)
                metrics["regime_label"] = regime_label
                metrics["observed_limit"] = observed_limit
                if limit_passed is True and not missing_inputs:
                    status = "pass"
                    evidence_directness = "direct"
                elif limit_passed is False and not missing_inputs:
                    automated_issues.append("Observed limit behavior does not match the contracted asymptotic expectation")
                    status = "fail"
                    evidence_directness = "direct"
                elif (
                    artifact_content
                    and not missing_inputs
                    and any(token in artifact_content.lower() for token in ["limit", "asymptotic", "scaling", "boundary"])
                ):
                    status = "warning"
                    evidence_directness = "mixed"
                elif not missing_inputs:
                    automated_issues.append("No direct limit or asymptotic evidence was supplied")
                    status = "insufficient_evidence"

            elif check_meta.check_key == "contract.benchmark_reproduction":
                source_reference_id = metadata.get("source_reference_id")
                metric_value, error = _validate_number(observed.get("metric_value"), field_name="observed.metric_value")
                if error is not None:
                    return error
                threshold_value, error = _validate_number(
                    observed.get("threshold_value"),
                    field_name="observed.threshold_value",
                )
                if error is not None:
                    return error
                source_reference_id, source_reference_issue = _validate_benchmark_reference_binding(
                    contract=contract,
                    binding_ids=binding_ids,
                    binding_supplied=binding_supplied,
                    source_reference_id=source_reference_id,
                )
                if source_reference_issue:
                    automated_issues.append(source_reference_issue)
                if not source_reference_id:
                    missing_inputs.append("metadata.source_reference_id")
                if metric_value is None:
                    missing_inputs.append("observed.metric_value")
                if threshold_value is None:
                    missing_inputs.append("observed.threshold_value")
                metrics["source_reference_id"] = source_reference_id
                metrics["metric_value"] = metric_value
                metrics["threshold_value"] = threshold_value
                if (
                    metric_value is not None
                    and threshold_value is not None
                    and source_reference_id
                ):
                    evidence_directness = "direct"
                    if metric_value <= threshold_value:
                        status = "pass"
                    else:
                        automated_issues.append("Benchmark comparison exceeds the allowed tolerance")
                        status = "fail"
                elif artifact_content and any(
                    token in artifact_content.lower() for token in ["benchmark", "baseline", "published", "reference"]
                ):
                    status = "warning"
                    evidence_directness = "mixed"

            elif check_meta.check_key == "contract.direct_proxy_consistency":
                proxy_only, error = _validate_boolean(observed.get("proxy_only"), field_name="observed.proxy_only")
                if error is not None:
                    return error
                direct_available, error = _validate_boolean(
                    observed.get("direct_available"),
                    field_name="observed.direct_available",
                )
                if error is not None:
                    return error
                proxy_available, error = _validate_boolean(
                    observed.get("proxy_available"),
                    field_name="observed.proxy_available",
                )
                if error is not None:
                    return error
                consistency_passed, error = _validate_boolean(
                    observed.get("consistency_passed"),
                    field_name="observed.consistency_passed",
                )
                if error is not None:
                    return error
                metrics.update(
                    {
                        "proxy_only": proxy_only,
                        "direct_available": direct_available,
                        "proxy_available": proxy_available,
                        "consistency_passed": consistency_passed,
                    }
                )
                if proxy_only is True:
                    automated_issues.append("Proxy evidence was supplied without a decisive direct observable")
                    status = "fail"
                    evidence_directness = "proxy"
                elif proxy_available is True and direct_available is None:
                    missing_inputs.append("observed.direct_available")
                    evidence_directness = "proxy"
                elif proxy_available is True and direct_available is False:
                    automated_issues.append("Proxy evidence was supplied without a decisive direct observable")
                    status = "fail"
                    evidence_directness = "proxy"
                elif direct_available is True and proxy_available is True and consistency_passed is None:
                    missing_inputs.append("observed.consistency_passed")
                    evidence_directness = "mixed"
                elif direct_available is True and proxy_available is True and consistency_passed is True:
                    status = "pass"
                    evidence_directness = "mixed"
                elif direct_available is True and proxy_available is True and consistency_passed is False:
                    automated_issues.append("Direct and proxy evidence disagree")
                    status = "fail"
                    evidence_directness = "mixed"
                elif direct_available is True:
                    status = "pass"
                    evidence_directness = "direct"

            elif check_meta.check_key == "contract.fit_family_mismatch":
                declared_family = _normalize_optional_scalar_str(metadata.get("declared_family"))
                selected_family, error_message = _validate_optional_string(
                    observed.get("selected_family"),
                    field_name="observed.selected_family",
                )
                if error_message is not None:
                    return _error_result(error_message)
                allowed = {str(item) for item in metadata.get("allowed_families", []) if isinstance(item, str)}
                forbidden = {str(item) for item in metadata.get("forbidden_families", []) if isinstance(item, str)}
                competing_checked, error = _validate_boolean(
                    observed.get("competing_family_checked"),
                    field_name="observed.competing_family_checked",
                )
                if error is not None:
                    return error
                if not declared_family:
                    missing_inputs.append("metadata.declared_family")
                if selected_family is None:
                    missing_inputs.append("observed.selected_family")
                metrics.update(
                    {
                        "declared_family": declared_family,
                        "selected_family": selected_family,
                        "allowed_families": sorted(allowed),
                        "forbidden_families": sorted(forbidden),
                        "competing_family_checked": competing_checked,
                    }
                )
                evidence_directness = "direct"
                if isinstance(selected_family, str) and selected_family in forbidden:
                    automated_issues.append("Selected fit family is explicitly forbidden")
                    status = "fail"
                elif allowed and isinstance(selected_family, str) and selected_family not in allowed:
                    automated_issues.append("Selected fit family is outside the allowed family set")
                    status = "fail"
                elif isinstance(selected_family, str) and declared_family and selected_family != declared_family:
                    automated_issues.append("Selected fit family does not match the contracted family")
                    status = "fail"
                elif isinstance(selected_family, str) and competing_checked is False:
                    automated_issues.append("Fit family was not compared against competing families")
                    status = "warning"
                elif isinstance(selected_family, str) and declared_family:
                    status = "pass"

            elif check_meta.check_key == "contract.estimator_family_mismatch":
                declared_family = _normalize_optional_scalar_str(metadata.get("declared_family"))
                selected_family, error_message = _validate_optional_string(
                    observed.get("selected_family"),
                    field_name="observed.selected_family",
                )
                if error_message is not None:
                    return _error_result(error_message)
                allowed = {str(item) for item in metadata.get("allowed_families", []) if isinstance(item, str)}
                forbidden = {str(item) for item in metadata.get("forbidden_families", []) if isinstance(item, str)}
                bias_checked, error = _validate_boolean(observed.get("bias_checked"), field_name="observed.bias_checked")
                if error is not None:
                    return error
                calibration_checked, error = _validate_boolean(
                    observed.get("calibration_checked"),
                    field_name="observed.calibration_checked",
                )
                if error is not None:
                    return error
                if not declared_family:
                    missing_inputs.append("metadata.declared_family")
                if selected_family is None:
                    missing_inputs.append("observed.selected_family")
                if bias_checked is None:
                    missing_inputs.append("observed.bias_checked")
                if calibration_checked is None:
                    missing_inputs.append("observed.calibration_checked")
                metrics.update(
                    {
                        "declared_family": declared_family,
                        "selected_family": selected_family,
                        "allowed_families": sorted(allowed),
                        "forbidden_families": sorted(forbidden),
                        "bias_checked": bias_checked,
                        "calibration_checked": calibration_checked,
                    }
                )
                evidence_directness = "direct"
                if isinstance(selected_family, str) and selected_family in forbidden:
                    automated_issues.append("Selected estimator family is explicitly forbidden")
                    status = "fail"
                elif allowed and isinstance(selected_family, str) and selected_family not in allowed:
                    automated_issues.append("Selected estimator family is outside the allowed family set")
                    status = "fail"
                elif isinstance(selected_family, str) and declared_family and selected_family != declared_family:
                    automated_issues.append("Selected estimator family does not match the contracted family")
                    status = "fail"
                elif isinstance(selected_family, str) and (bias_checked is False or calibration_checked is False):
                    automated_issues.append("Estimator family is missing bias or calibration diagnostics")
                    status = "warning"
                elif (
                    isinstance(selected_family, str)
                    and declared_family
                    and bias_checked is True
                    and calibration_checked is True
                ):
                    status = "pass"

            resolved_subject: str | None = None
            if check_meta.check_key == "contract.benchmark_reproduction":
                resolved_subject = source_reference_id
            elif check_meta.check_key == "contract.limit_recovery":
                resolved_subject = regime_label

            binding_requirement_missing_inputs, binding_requirement_issue = _subject_binding_requirement(
                check_meta.check_key,
                contract=contract,
                binding_ids=binding_ids,
                resolved_subject=resolved_subject,
            )
            if binding_requirement_missing_inputs:
                for missing_input in binding_requirement_missing_inputs:
                    if missing_input not in missing_inputs:
                        missing_inputs.append(missing_input)
            if binding_requirement_issue is not None and binding_requirement_issue not in automated_issues:
                automated_issues.append(binding_requirement_issue)
                if status == "pass":
                    status = "insufficient_evidence"
                    evidence_directness = "mixed" if artifact_content else "metadata_only"

            if contract is not None:
                metrics["contract_claim_count"] = len(contract.claims)
                metrics["contract_deliverable_count"] = len(contract.deliverables)
            if binding_issues and status != "insufficient_evidence":
                automated_issues.append("Binding validation issues prevent a decisive contract-aware verdict")
                status = "insufficient_evidence"
                evidence_directness = "mixed" if artifact_content else "metadata_only"
            if not contract_impacts and contract is not None and status != "insufficient_evidence":
                contract_impacts = _decisive_contract_impacts(
                    check_key=check_meta.check_key,
                    contract=contract,
                    binding_ids=binding_ids,
                    binding_supplied=binding_supplied,
                    metadata=metadata,
                )

            return stable_mcp_response(
                {
                "check_id": check_meta.check_id,
                "check_key": check_meta.check_key,
                "check_name": check_meta.name,
                "check_class": check_meta.check_class,
                "contract_aware": check_meta.contract_aware,
                "binding_targets": list(check_meta.binding_targets),
                "supported_binding_fields": _supported_binding_fields_for_targets(check_meta.binding_targets),
                "status": status,
                "evidence_directness": evidence_directness,
                "binding": binding,
                "missing_inputs": missing_inputs,
                "automated_issues": automated_issues,
                "metrics": metrics,
                "contract_impacts": contract_impacts,
                "contract_salvaged": bool(contract_salvage_errors),
                "contract_salvage_findings": list(contract_salvage_errors),
                "guidance": check_meta.oracle_hint,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool()
def suggest_contract_checks(contract: SuggestContractPayload, active_checks: StringListPayload = None) -> dict:
    """Suggest contract-aware checks from a schema-validated project or phase ``contract``.

    ``contract`` must be an object with the normal GPD contract structure.
    ``schema_version`` defaults to ``1`` when omitted and must equal ``1`` when
    provided. The tool keeps authoritative fields strict: non-object
    payloads, coercive scalars, and malformed list members are rejected rather
    than inferred. Recoverable scalar-to-list drift is normalized by the shared
    contract parser before verification. Contract payloads must also satisfy
    the shared semantic integrity rules: same-kind IDs must be unique.
    references[].carry_forward_to uses workflow scope labels, never contract IDs.
    target IDs must not be reused across claim/deliverable/acceptance-test/reference kinds when that would make resolution ambiguous.
    contract context must stay consistent with metadata defaults and explicit metadata fields, so benchmark anchors, regime labels, and family selections cannot contradict the resolved binding.
    the shared semantic integrity rules: same-kind IDs must be unique, target IDs must not be reused across claim/deliverable/acceptance-test/reference
    kinds when that would make resolution ambiguous, and
    ``references[].carry_forward_to`` is only for workflow scope labels, never
    contract IDs. contract context must stay consistent with metadata defaults and explicit metadata fields, so benchmark anchors,
    regime labels, and family selections cannot contradict the resolved
    binding. Limited recoverable structural drift may still be salvaged, and
    any such recovery is carried through the suggestion metadata.

    ``active_checks`` is optional and must be ``list[str]`` when provided. Supply
    already-enabled check ids or check keys so each suggestion can mark
    ``already_active`` precisely.

    Each ``suggested_checks[]`` entry includes ``required_request_fields``,
    ``optional_request_fields``, ``supported_binding_fields``, and a
    ``request_template`` that is safe to use as the starting point for
    ``run_contract_check(request=...)``.
    """

    with gpd_span("mcp.verification.suggest_contract_checks"):
        try:
            contract, error = _payload_mapping(contract, field_name="contract")
            if error is not None:
                return error
            if active_checks is not None:
                active_checks, error = _validate_string_list(active_checks, field_name="active_checks")
                if error is not None:
                    return error
                active_checks = _normalize_active_checks(active_checks)
            parsed, contract_salvage_errors, error = _parse_contract_payload(contract)
            if error is not None or parsed is None:
                return error or _error_result("Invalid contract payload")
            active = set(active_checks or [])
            suggestions: list[dict[str, object]] = []

            def _add(check_key: str, reason: str) -> None:
                meta = get_verification_check(check_key)
                if meta is None:
                    return
                request_hint = _contract_check_request_hint(meta.check_key, contract=parsed)
                suggestions.append(
                    {
                        "check_id": meta.check_id,
                        "check_key": meta.check_key,
                        "name": meta.name,
                        "reason": reason,
                        "already_active": meta.check_id in active or meta.check_key in active,
                        "binding_targets": list(meta.binding_targets),
                        **request_hint,
                    }
                )

            if any(test.kind == "benchmark" for test in parsed.acceptance_tests) or any(
                reference.role == "benchmark" or "compare" in reference.required_actions for reference in parsed.references
            ):
                _add(
                    "contract.benchmark_reproduction",
                    "Benchmark-style acceptance tests or benchmark anchors are present",
                )

            if parsed.forbidden_proxies:
                _add("contract.direct_proxy_consistency", "Forbidden proxies require direct-vs-proxy checks")

            if any(observable.regime for observable in parsed.observables) or any(
                keyword in " ".join([test.procedure, test.pass_condition]).lower()
                for test in parsed.acceptance_tests
                for keyword in ("limit", "asymptotic", "boundary", "scaling")
            ):
                _add("contract.limit_recovery", "Contract mentions regimes or limit-like acceptance behavior")

            if any(
                keyword in " ".join([test.procedure, test.pass_condition]).lower()
                for test in parsed.acceptance_tests
                for keyword in ("fit", "residual", "extrapolat", "ansatz")
            ) or parsed.approach_policy.allowed_fit_families or parsed.approach_policy.forbidden_fit_families:
                _add("contract.fit_family_mismatch", "Acceptance tests mention fitting or extrapolation families")

            if any(
                keyword in " ".join([test.procedure, test.pass_condition]).lower()
                for test in parsed.acceptance_tests
                for keyword in ("estimator", "bootstrap", "jackknife", "posterior", "bias", "variance")
            ) or parsed.approach_policy.allowed_estimator_families or parsed.approach_policy.forbidden_estimator_families:
                _add(
                    "contract.estimator_family_mismatch",
                    "Acceptance tests mention estimator-family assumptions",
                )

            response = {
                "suggested_checks": suggestions,
                "suggested_count": len(suggestions),
                "contract_salvaged": bool(contract_salvage_errors),
                "contract_salvage_findings": list(contract_salvage_errors),
            }
            if contract_salvage_errors:
                response["contract_warnings"] = [
                    "Contract payload was salvaged before check suggestion: "
                    + _summarize_contract_salvage_errors(contract_salvage_errors)
                ]
            return stable_mcp_response(response)
        except Exception as exc:  # pragma: no cover - defensive envelope
            if isinstance(exc, PydanticValidationError):
                return _error_result(f"Invalid contract payload: {exc}")
            return _error_result(exc)


@mcp.tool()
def get_checklist(domain: str) -> dict:
    """Return the domain-specific verification checklist.

    Provides the complete list of checks recommended for a physics domain,
    including which live verifier-registry checks (currently 5.1-5.19) each maps to.
    """
    with gpd_span("mcp.verification.checklist", domain=domain):
        try:
            checklist = DOMAIN_CHECKLISTS.get(domain)
            if checklist is None:
                return stable_mcp_response(
                    {
                    "found": False,
                    "domain": domain,
                    "available_domains": sorted(DOMAIN_CHECKLISTS.keys()),
                    "message": f"No checklist for domain '{domain}'.",
                    }
                )

            # Also include the universal checks
            universal = [_serialize_verification_check_entry(entry) for entry in list_verification_checks()]

            return stable_mcp_response(
                {
                "found": True,
                "domain": domain,
                "domain_checks": copy.deepcopy(checklist),
                "domain_check_count": len(checklist),
                "universal_checks": copy.deepcopy(universal),
                "universal_check_count": len(universal),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool()
def get_bundle_checklist(bundle_ids: list[str]) -> dict:
    """Return additive verifier checklist extensions for selected protocol bundles."""
    with gpd_span("mcp.verification.bundle_checklist", bundle_count=len(bundle_ids)):
        try:
            bundles: list[dict[str, object]] = []
            resolved_bundles: list[ResolvedProtocolBundle] = []
            checklist: list[dict[str, object]] = []
            missing_bundle_ids: list[str] = []

            for bundle_id in bundle_ids:
                bundle = get_protocol_bundle(bundle_id)
                if bundle is None:
                    missing_bundle_ids.append(bundle_id)
                    continue

                verification_domain_paths = [asset.path for asset in bundle.assets.verification_domains]
                bundle_payload = {
                    "bundle_id": bundle.bundle_id,
                    "title": bundle.title,
                    "summary": bundle.summary,
                    "asset_paths": [asset.path for _role, asset in bundle.assets.iter_assets()],
                    "verification_domains": verification_domain_paths,
                    "verifier_extensions": [extension.model_dump(mode="json") for extension in bundle.verifier_extensions],
                }
                bundles.append(bundle_payload)
                resolved_bundles.append(
                    ResolvedProtocolBundle(
                        bundle_id=bundle.bundle_id,
                        title=bundle.title,
                        summary=bundle.summary,
                        score=0,
                        matched_tags=[],
                        matched_terms=[],
                        selection_tags=bundle.selection_tags,
                        assets=bundle.assets,
                        anchor_prompts=bundle.anchor_prompts,
                        reference_prompts=bundle.reference_prompts,
                        estimator_policies=bundle.estimator_policies,
                        decisive_artifact_guidance=bundle.decisive_artifact_guidance,
                        verifier_extensions=bundle.verifier_extensions,
                    )
                )

                for extension in bundle.verifier_extensions:
                    checklist.append(
                        {
                            "bundle_id": bundle.bundle_id,
                            "bundle_title": bundle.title,
                            "name": extension.name,
                            "rationale": extension.rationale,
                            "check_ids": list(extension.check_ids),
                        }
                    )

            return stable_mcp_response(
                {
                    "found": bool(bundles),
                    "bundle_count": len(bundles),
                    "bundles": copy.deepcopy(bundles),
                    "protocol_bundle_context": render_protocol_bundle_context(resolved_bundles),
                    "bundle_check_count": len(checklist),
                    "bundle_checks": copy.deepcopy(checklist),
                    "missing_bundle_ids": missing_bundle_ids,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool()
def dimensional_check(expressions: list[str]) -> dict:
    """Verify dimensional consistency of physics expressions.

    Each expression should be in the format "LHS = RHS" where dimensions
    are annotated with [M], [L], [T], [Q], [Theta] notation.

    Example: "[M][L]^2[T]^-2 = [M][L]^2[T]^-2" (energy = energy)
    """
    with gpd_span("mcp.verification.dimensional_check"):
        validated_expressions, error = _validate_string_list(expressions, field_name="expressions")
        if error is not None:
            return error
        return stable_mcp_response(_dimensional_check_inner(validated_expressions))


def _dimensional_check_inner(expressions: list[str]) -> dict:
    results: list[dict[str, object]] = []

    for expr in expressions:
        if "=" not in expr:
            results.append(
                {
                    "expression": expr,
                    "valid": False,
                    "error": "Expression must contain '=' to compare dimensions",
                }
            )
            continue

        parts = expr.split("=", 1)
        lhs_str = parts[0].strip()
        rhs_str = parts[1].strip()

        lhs_dims = _parse_dimensions(lhs_str)
        rhs_dims = _parse_dimensions(rhs_str)

        no_annotations = all(v == 0 for v in lhs_dims.values()) and all(
            v == 0 for v in rhs_dims.values()
        )
        match = _dims_equal(lhs_dims, rhs_dims)
        result: dict[str, object] = {
            "expression": expr,
            "valid": match and not no_annotations,
            "no_dimensions_found": no_annotations,
            "lhs_dimensions": {k: v for k, v in lhs_dims.items() if v != 0},
            "rhs_dimensions": {k: v for k, v in rhs_dims.items() if v != 0},
        }
        if no_annotations:
            result["note"] = (
                "No dimension annotations found — cannot verify"
            )
        elif not match:
            mismatches = {}
            for dim in set(lhs_dims.keys()) | set(rhs_dims.keys()):
                lv = lhs_dims.get(dim, 0)
                rv = rhs_dims.get(dim, 0)
                if lv != rv:
                    mismatches[dim] = {"lhs": lv, "rhs": rv, "diff": lv - rv}
            result["mismatches"] = mismatches
        results.append(result)

    all_valid = bool(results) and all(r.get("valid", False) for r in results)
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "all_consistent": all_valid,
        "checked_count": len(results),
        "results": results,
    }


@mcp.tool()
def limiting_case_check(expression: str, limits: dict[str, str]) -> dict:
    """Verify that an expression reduces to known results in specified limits.

    This is a structural check -- it validates that the limit analysis
    has been documented. The actual mathematical verification should be
    performed by a CAS (SymPy) via the code execution MCP server.

    Args:
        expression: The general expression being checked
        limits: Dict mapping limit descriptions to expected results.
                E.g., {"hbar -> 0": "classical Hamilton-Jacobi",
                       "c -> infinity": "non-relativistic Schrodinger"}
    """
    with gpd_span("mcp.verification.limiting_case"):
        validated_expression, error = _validate_string(expression, field_name="expression")
        if error is not None:
            return error
        validated_limits, error = _validate_string_mapping(limits, field_name="limits")
        if error is not None:
            return error
        return stable_mcp_response(_limiting_case_inner(validated_expression, validated_limits))


def _limiting_case_inner(expression: str, limits: dict[str, str]) -> dict:
    results: list[dict[str, object]] = []
    standard_limits = {
        "classical": "hbar -> 0",
        "non-relativistic": "v/c -> 0 or c -> infinity",
        "weak-coupling": "g -> 0",
        "high-temperature": "T -> infinity",
        "low-temperature": "T -> 0",
        "continuum": "a -> 0 (lattice spacing)",
        "thermodynamic": "N -> infinity",
        "flat-space": "R_{mu nu} -> 0",
    }

    for limit_desc, expected_result in limits.items():
        # Check if this is a standard limit type
        limit_type = None
        for stype, sdesc in standard_limits.items():
            if stype in limit_desc.lower() or sdesc.lower() in limit_desc.lower():
                limit_type = stype
                break

        results.append(
            {
                "limit": limit_desc,
                "expected": expected_result,
                "limit_type": limit_type,
                "status": "documented",
                "guidance": (
                    f"Verify: apply limit '{limit_desc}' to the expression. "
                    f"Result should reduce to: {expected_result}. "
                    "Use SymPy sympy.limit() or series expansion for rigorous check."
                ),
            }
        )

    # Suggest missing standard limits based on expression content
    suggestions: list[str] = []
    expr_lower = expression.lower()
    if "hbar" in expr_lower or "\\hbar" in expr_lower:
        if not any("classical" in key.lower() or "hbar" in key.lower() for key in limits):
            suggestions.append("Consider checking classical limit (hbar -> 0)")
    if any(kw in expr_lower for kw in ["gamma", "lorentz", "relativistic", "c^2"]):
        if not any("non-rel" in key.lower() or "c ->" in key.lower() for key in limits):
            suggestions.append("Consider checking non-relativistic limit (c -> infinity)")
    if any(kw in expr_lower for kw in ["coupling", "alpha", "g^2", "perturbat"]):
        if not any("weak" in key.lower() or "g ->" in key.lower() for key in limits):
            suggestions.append("Consider checking weak-coupling limit (g -> 0)")

    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "expression_length": len(expression),
        "limits_checked": len(results),
        "results": results,
        "suggestions": suggestions,
    }


@mcp.tool()
def symmetry_check(expression: str, symmetries: list[str]) -> dict:
    """Verify that an expression respects specified symmetries.

    Structural check that symmetry analysis has been documented.
    Actual verification should use CAS or explicit transformation.

    Args:
        expression: The expression to check
        symmetries: List of symmetries to verify. E.g.,
                    ["Lorentz invariance", "gauge invariance", "parity"]
    """
    with gpd_span("mcp.verification.symmetry_check"):
        validated_expression, error = _validate_string(expression, field_name="expression")
        if error is not None:
            return error
        validated_symmetries, error = _validate_string_list(symmetries, field_name="symmetries")
        if error is not None:
            return error
        return stable_mcp_response(_symmetry_check_inner(validated_expression, validated_symmetries))


def _symmetry_check_inner(expression: str, symmetries: list[str]) -> dict:
    # Map common symmetry names to verification strategies
    symmetry_strategies: dict[str, str] = {
        "lorentz": "Express result in manifestly covariant form (4-vectors, invariants s,t,u)",
        "gauge": "Compute same observable in two different gauges; results must agree",
        "parity": "Apply x -> -x and check even/odd behavior matches expectation",
        "time-reversal": "Apply t -> -t and check behavior",
        "cpt": "Apply combined C, P, T transformation; must be invariant in local QFT",
        "conformal": "Check power-law behavior at critical points; verify Ward identities",
        "chiral": "Check left-right decomposition; verify axial current conservation/anomaly",
        "rotational": "Express in spherical harmonics or check angular momentum conservation",
        "translational": "Verify momentum conservation / spatial homogeneity",
        "scale": "Check dimensionless ratios are scale-independent",
        "particle-exchange": "Verify bosonic (symmetric) or fermionic (antisymmetric) behavior",
        "charge-conjugation": "Check particle <-> antiparticle symmetry",
        "su(3)": "Verify color singlet nature of observables",
        "su(2)": "Verify isospin quantum numbers",
        "u(1)": "Verify charge conservation",
    }

    results: list[dict[str, object]] = []
    for sym in symmetries:
        sym_lower = sym.lower().replace(" ", "").replace("-", "").replace("_", "")

        strategy = None
        matched_type = None
        for key, strat in symmetry_strategies.items():
            key_clean = key.replace(" ", "").replace("-", "").replace("_", "")
            if key_clean == sym_lower:
                strategy = strat
                matched_type = key
                break
            if len(sym_lower) >= 3 and (key_clean in sym_lower or sym_lower in key_clean):
                strategy = strat
                matched_type = key
                break

        results.append(
            {
                "symmetry": sym,
                "matched_type": matched_type,
                "strategy": strategy or f"Apply {sym} transformation to expression and verify expected behavior",
                "status": "requires_verification",
            }
        )

    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "expression_length": len(expression),
        "symmetries_checked": len(results),
        "results": results,
    }


@mcp.tool()
def get_verification_coverage(error_class_ids: list[int], active_checks: list[str]) -> dict:
    """Return gap analysis: which error classes are covered by active checks.

    Maps error class IDs against the set of verification checks that are
    currently active (determined by profile). Identifies gaps where error
    classes have no active detection.

    Args:
        error_class_ids: List of error class IDs to check coverage for
        active_checks: List of active check IDs (e.g., ["5.1", "5.2", "5.3"])
    """
    with gpd_span("mcp.verification.coverage"):
        validated_error_class_ids, error = _validate_int_list(error_class_ids, field_name="error_class_ids")
        if error is not None:
            return error
        validated_active_checks, error = _validate_string_list(active_checks, field_name="active_checks")
        if error is not None:
            return error
        normalized_active_checks = _normalize_active_checks(validated_active_checks)
        return stable_mcp_response(_coverage_inner(validated_error_class_ids, normalized_active_checks))


def _coverage_inner(error_class_ids: list[int], active_checks: list[str]) -> dict:
    covered: list[dict[str, object]] = []
    uncovered: list[dict[str, object]] = []
    partial: list[dict[str, object]] = []

    for ec_id in error_class_ids:
        ec_meta = ERROR_CLASS_COVERAGE.get(ec_id)
        if ec_meta is None:
            uncovered.append(
                {
                    "error_class_id": ec_id,
                    "name": "Unknown",
                    "required_checks": [],
                    "active_checks": [],
                    "domains": [],
                    "missing_checks": [],
                    "status": "unknown",
                    "message": f"Error class {ec_id} not in coverage database",
                }
            )
            continue

        primary = ec_meta["primary_checks"]
        active_primary = [c for c in primary if c in active_checks]

        entry: dict[str, object] = {
            "error_class_id": ec_id,
            "name": ec_meta["name"],
            "required_checks": primary,
            "active_checks": active_primary,
            "domains": ec_meta["domains"],
        }

        if len(active_primary) == len(primary):
            entry["status"] = "covered"
            covered.append(entry)
        elif len(active_primary) > 0:
            entry["status"] = "partial"
            entry["missing_checks"] = [c for c in primary if c not in active_checks]
            partial.append(entry)
        else:
            entry["status"] = "uncovered"
            entry["missing_checks"] = primary
            uncovered.append(entry)

    total = len(error_class_ids)
    covered_count = len(covered)
    coverage_percent = round(covered_count / total * 100, 1) if total > 0 else 0.0

    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "total_classes": total,
        "covered": covered_count,
        "partial": len(partial),
        "uncovered": len(uncovered),
        "coverage_percent": coverage_percent,
        "covered_classes": covered,
        "partial_classes": partial,
        "uncovered_classes": uncovered,
        "active_checks": active_checks,
        "recommendation": (
            "Full coverage"
            if len(uncovered) == 0 and len(partial) == 0
            else (
                f"{len(partial)} error classes have partial coverage. "
                f"Consider enabling checks: {sorted({c for p in partial for c in p.get('missing_checks', [])})}"
            )
            if len(uncovered) == 0
            else (
                f"{len(uncovered)} error classes have no active detection. "
                f"Consider enabling checks: {sorted({c for u in uncovered for c in u.get('missing_checks', [])} | {c for p in partial for c in p.get('missing_checks', [])})}"
            )
        ),
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the gpd-verification MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Verification MCP Server")


if __name__ == "__main__":
    main()
