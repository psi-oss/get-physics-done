"""MCP server for GPD physics verification.

Exposes verification checks as MCP tools for solver agents to run
dimensional analysis, limiting case checks, symmetry verification,
and domain-specific checklists.

Contract-aware execution itself lives in ``gpd.core.contract_checks``; this
module owns the published MCP input schemas, tool registration, and the static
triage/documentation tools.

Usage:
    python -m gpd.mcp.servers.verification_server
    # or via entry point:
    gpd-mcp-verification
"""

import copy
import re
from collections.abc import Iterable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field, WithJsonSchema

from gpd.contracts import (
    CONTRACT_ACCEPTANCE_AUTOMATION_VALUES,
    CONTRACT_ACCEPTANCE_TEST_KIND_VALUES,
    CONTRACT_APPROACH_POLICY_FIELD_NAMES,
    CONTRACT_CLAIM_KIND_VALUES,
    CONTRACT_CONTEXT_INTAKE_FIELD_NAMES,
    CONTRACT_DELIVERABLE_KIND_VALUES,
    CONTRACT_LINK_RELATION_VALUES,
    CONTRACT_OBSERVABLE_KIND_VALUES,
    CONTRACT_REFERENCE_ACTION_VALUES,
    CONTRACT_REFERENCE_KIND_VALUES,
    CONTRACT_REFERENCE_ROLE_VALUES,
    CONTRACT_UNCERTAINTY_MARKER_FIELD_NAMES,
    PROOF_HYPOTHESIS_CATEGORY_VALUES,
    THEOREM_CLAIM_KIND_VALUES,
    THEOREM_STYLE_STATEMENT_REGEX_PATTERNS,
)
from gpd.core import contract_checks

# Contract-check names are re-exported here so this module stays the stable
# import surface for the gpd-verification server and its regression tests; the
# implementations live in gpd.core.contract_checks.
from gpd.core.contract_checks import (  # noqa: F401
    _CONTRACT_CHECK_REQUEST_HINTS,
    _COUNTEREXAMPLE_STATUS_VALUES,
    _PROOF_CHECK_KEYS,
    _QUANTIFIER_STATUS_VALUES,
    _SCOPE_STATUS_VALUES,
    DOMAIN_CHECKLISTS,
    ContractBindingRequest,
    ContractMetadataRequest,
    ContractObservedRequest,
    RunContractCheckRequest,
    _contract_check_request_hint,
    _error_result,
    _is_recoverable_contract_parse_error,
    _serialize_verification_check_entry,
    _unique_strings,
    _validate_string,
    _validate_string_list,
)
from gpd.core.observability import gpd_span
from gpd.core.protocol_bundles import get_protocol_bundle
from gpd.core.verification_checks import (
    VERIFICATION_SCHEMA_VERSION,
    get_verification_check,
    list_verification_checks,
)
from gpd.mcp.servers import (
    ABSOLUTE_PROJECT_DIR_SCHEMA,
    configure_mcp_logging,
    read_only_tool_annotations,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)
from gpd.mcp.verification_contract_policy import (
    VERIFICATION_BINDING_TARGETS,
    verification_contract_policy_text,
    verification_contract_surface_summary_text,
)

logger = configure_mcp_logging("gpd-verification")

mcp = FastMCP("gpd-verification")

RUN_CONTRACT_CHECK_SCHEMA_SIZE_BUDGET_BYTES = 80_000


def _non_empty_string_schema() -> dict[str, object]:
    return {"type": "string", "minLength": 1, "pattern": r"\S"}


def _trimmed_non_empty_string_schema() -> dict[str, object]:
    return {
        "type": "string",
        "minLength": 1,
        "pattern": r"^\S(?:[\s\S]*\S)?$",
    }


def _string_schema() -> dict[str, object]:
    return {"type": "string"}


def _non_empty_string_or_null_schema() -> dict[str, object]:
    return {"anyOf": [dict(_non_empty_string_schema()), {"type": "null"}]}


def _string_list_schema(*, min_items: int | None = None) -> dict[str, object]:
    schema: dict[str, object] = {"type": "array", "items": _non_empty_string_schema(), "uniqueItems": True}
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def _string_list_or_null_schema(*, min_items: int | None = None) -> dict[str, object]:
    return {
        "anyOf": [
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


def _enum_string_list_schema(values: Iterable[str], *, min_items: int | None = None) -> dict[str, object]:
    schema: dict[str, object] = {"type": "array", "items": _enum_string_schema(values), "uniqueItems": True}
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def _enum_string_or_string_list_schema(values: Iterable[str], *, min_items: int | None = None) -> dict[str, object]:
    return {
        "anyOf": [
            _enum_string_schema(values),
            _enum_string_list_schema(values, min_items=min_items),
        ]
    }


def _enum_string_or_null_schema(values: Iterable[str]) -> dict[str, object]:
    return {
        "anyOf": [
            _enum_string_schema(values),
            {"type": "null"},
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


_REQUIRED_FIELD_ALLOW_EMPTY_ARRAY: frozenset[tuple[str, str]] = frozenset(
    {
        ("observed", "uncovered_conclusion_clause_ids"),
    }
)


def _strict_required_schema_fragment(
    schema_fragment: dict[str, object],
    *,
    allow_empty_array: bool = False,
) -> dict[str, object]:
    schema = copy.deepcopy(schema_fragment)
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        strict_branches: list[object] = []
        for branch in any_of:
            if not isinstance(branch, dict):
                strict_branches.append(branch)
                continue
            if branch.get("type") == "null":
                continue
            strict_branches.append(
                _strict_required_schema_fragment(
                    branch,
                    allow_empty_array=allow_empty_array,
                )
            )
        if len(strict_branches) == 1 and isinstance(strict_branches[0], dict):
            return strict_branches[0]
        schema["anyOf"] = strict_branches
    if (
        not allow_empty_array
        and schema.get("type") == "array"
        and (not isinstance(schema.get("minItems"), int) or int(schema["minItems"]) < 1)
    ):
        schema["minItems"] = 1
    return schema


def _enum_string_schema(values: Iterable[str]) -> dict[str, object]:
    return {
        "type": "string",
        "enum": list(values),
    }


def _case_insensitive_exact_enum_pattern(values: Iterable[str]) -> str:
    patterns: list[str] = []
    for value in values:
        token_parts: list[str] = []
        for char in str(value):
            if char.isalpha():
                lowered = re.escape(char.lower())
                uppered = re.escape(char.upper())
                token_parts.append(f"[{lowered}{uppered}]")
            else:
                token_parts.append(re.escape(char))
        patterns.append("".join(token_parts))
    return r"^(?:" + "|".join(patterns) + r")$"


def _contract_string_schema() -> dict[str, object]:
    return dict(_trimmed_non_empty_string_schema())


def _contract_string_list_schema(*, min_items: int | None = None) -> dict[str, object]:
    schema: dict[str, object] = {"type": "array", "items": _contract_string_schema(), "uniqueItems": True}
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def _contract_string_or_string_list_schema(*, min_items: int | None = None) -> dict[str, object]:
    return {
        "anyOf": [
            _contract_string_schema(),
            _contract_string_list_schema(min_items=min_items),
        ]
    }


def _contract_enum_string_schema(values: Iterable[str]) -> dict[str, object]:
    canonical_values = list(values)
    return {
        "anyOf": [
            {"type": "string", "enum": canonical_values},
            {"type": "string", "pattern": _case_insensitive_exact_enum_pattern(canonical_values)},
        ],
        "description": (
            "Use the exact canonical value when possible. Case-only drift is accepted and normalized to the "
            "canonical value."
        ),
    }


def _contract_enum_string_list_schema(values: Iterable[str], *, min_items: int | None = None) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "array",
        "items": _contract_enum_string_schema(values),
        "uniqueItems": True,
    }
    if min_items is not None:
        schema["minItems"] = min_items
    return schema


def _binding_input_schema_for_targets(targets: Iterable[str]) -> dict[str, object]:
    properties: dict[str, object] = {}
    for target in targets:
        properties[f"{target}_ids"] = _string_list_schema(min_items=1)
    return _object_schema(properties, additional_properties=False)


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
    identifier for entry in _CONTRACT_AWARE_CHECK_ENTRIES for identifier in _check_identifier_values(entry)
)
_RUN_CHECK_IDENTIFIER_VALUES: tuple[str, ...] = tuple(
    dict.fromkeys(identifier for entry in list_verification_checks() for identifier in _check_identifier_values(entry))
)
_RUN_CHECK_IDENTIFIER_SCHEMA: dict[str, object] = {
    **dict(_trimmed_non_empty_string_schema()),
    "enum": list(_RUN_CHECK_IDENTIFIER_VALUES),
}


_CONTRACT_BINDING_INPUT_SCHEMA: dict[str, object] = _binding_input_schema_for_targets(VERIFICATION_BINDING_TARGETS)
_CONTRACT_METADATA_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "regime_label": _non_empty_string_or_null_schema(),
        "expected_behavior": _non_empty_string_or_null_schema(),
        "source_reference_id": _non_empty_string_or_null_schema(),
        "declared_family": _non_empty_string_or_null_schema(),
        "allowed_families": _string_list_schema(),
        "forbidden_families": _string_list_schema(),
        "theorem_parameter_symbols": _string_list_or_null_schema(),
        "hypothesis_ids": _string_list_or_null_schema(),
        "quantifiers": _string_list_or_null_schema(),
        "conclusion_clause_ids": _string_list_or_null_schema(),
        "claim_statement": _non_empty_string_or_null_schema(),
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
        "covered_hypothesis_ids": _string_list_or_null_schema(),
        "missing_hypothesis_ids": _string_list_or_null_schema(),
        "covered_parameter_symbols": _string_list_or_null_schema(),
        "missing_parameter_symbols": _string_list_or_null_schema(),
        "uncovered_quantifiers": _string_list_or_null_schema(),
        "uncovered_conclusion_clause_ids": _string_list_or_null_schema(),
        "quantifier_status": _enum_string_or_null_schema(_QUANTIFIER_STATUS_VALUES),
        "scope_status": _enum_string_or_null_schema(_SCOPE_STATUS_VALUES),
        "counterexample_status": _enum_string_or_null_schema(_COUNTEREXAMPLE_STATUS_VALUES),
    },
    additional_properties=False,
)
_CONTRACT_SCOPE_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "question": _non_empty_string_schema(),
        "in_scope": _contract_string_list_schema(min_items=1),
        "out_of_scope": _contract_string_list_schema(),
        "unresolved_questions": _contract_string_list_schema(),
    },
    required=("question", "in_scope"),
    additional_properties=False,
)
_CONTRACT_SCOPE_INPUT_SCHEMA["description"] = (
    "Use `scope.question` for the core research question. Project-scoping contracts must also provide non-empty "
    "`scope.in_scope` naming at least one concrete objective or boundary; downstream project-contract validation "
    "does not infer it."
)
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {field_name: _contract_string_list_schema() for field_name in CONTRACT_CONTEXT_INTAKE_FIELD_NAMES},
    additional_properties=False,
)
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA["minProperties"] = 1
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA["anyOf"] = [
    {"required": [field_name]} for field_name in CONTRACT_CONTEXT_INTAKE_FIELD_NAMES
]
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA["description"] = (
    "`context_intake` is required and must stay explicit. Use it to surface anchors, prior outputs, baselines, "
    "gaps, or other user-stated inputs the model must still see when later contract-aware tools validate the work. "
    "Early contracts may carry empty arrays while the concrete guidance is still being recovered."
)
_CONTRACT_APPROACH_POLICY_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {field_name: _contract_string_list_schema() for field_name in CONTRACT_APPROACH_POLICY_FIELD_NAMES},
    additional_properties=False,
)
_CONTRACT_OBSERVABLE_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "name": _non_empty_string_schema(),
        "kind": _contract_enum_string_schema(CONTRACT_OBSERVABLE_KIND_VALUES),
        "definition": _non_empty_string_schema(),
        "regime": _non_empty_string_or_null_schema(),
        "units": _non_empty_string_or_null_schema(),
    },
    required=("id", "name", "definition"),
    additional_properties=False,
)
_CONTRACT_PROOF_PARAMETER_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "symbol": _non_empty_string_schema(),
        "domain_or_type": _string_schema(),
        "aliases": _contract_string_list_schema(),
        "required_in_proof": {"type": "boolean"},
        "notes": _non_empty_string_or_null_schema(),
    },
    required=("symbol",),
    additional_properties=False,
)
_CONTRACT_PROOF_HYPOTHESIS_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "text": _non_empty_string_schema(),
        "symbols": _contract_string_list_schema(),
        "category": _contract_enum_string_schema(PROOF_HYPOTHESIS_CATEGORY_VALUES),
        "required_in_proof": {"type": "boolean"},
    },
    required=("id", "text"),
    additional_properties=False,
)
_CONTRACT_PROOF_CONCLUSION_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "text": _non_empty_string_schema(),
    },
    required=("id", "text"),
    additional_properties=False,
)
_PROOF_FIELD_CLAIM_KIND_VALUES = tuple(value for value in CONTRACT_CLAIM_KIND_VALUES if value != "other")
_CONTRACT_CLAIM_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "statement": _non_empty_string_schema(),
        "claim_kind": _contract_enum_string_schema(CONTRACT_CLAIM_KIND_VALUES),
        "observables": _contract_string_list_schema(),
        "deliverables": _contract_string_list_schema(min_items=1),
        "acceptance_tests": _contract_string_list_schema(min_items=1),
        "references": _contract_string_list_schema(),
        "parameters": {"type": "array", "items": dict(_CONTRACT_PROOF_PARAMETER_INPUT_SCHEMA)},
        "hypotheses": {"type": "array", "items": dict(_CONTRACT_PROOF_HYPOTHESIS_INPUT_SCHEMA)},
        "quantifiers": _contract_string_list_schema(),
        "conclusion_clauses": {"type": "array", "items": dict(_CONTRACT_PROOF_CONCLUSION_INPUT_SCHEMA)},
        "proof_deliverables": _contract_string_list_schema(),
    },
    required=("id", "statement", "deliverables", "acceptance_tests"),
    additional_properties=False,
)
_CONTRACT_CLAIM_INPUT_SCHEMA["description"] = (
    "For non-scoping plans, every claim must link to concrete `deliverables` and `acceptance_tests`. "
    "Scoping-only contracts should omit claims entirely instead of leaving those links implicit. "
    "Claims are proof-bearing not only when `claim_kind` is theorem-like, but also when the statement is theorem-like, "
    "when proof-specific fields are already populated, or when `observables` references a `proof_obligation` target. "
    "Do not rely on runtime inference for those cases. Proof-bearing claims must set an explicit proof-oriented "
    "`claim_kind`, provide non-empty `proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses`, "
    "preserve `quantifiers` when explicit quantifier or domain obligations exist, and reference at least one "
    "proof-specific acceptance test id."
)
_THEOREM_STYLE_STATEMENT_SCHEMA_PATTERNS = THEOREM_STYLE_STATEMENT_REGEX_PATTERNS
_CONTRACT_CLAIM_INPUT_SCHEMA["allOf"] = [
    {
        "if": {
            "required": ["claim_kind"],
            "properties": {"claim_kind": _contract_enum_string_schema(THEOREM_CLAIM_KIND_VALUES)},
        },
        "then": {
            "required": ["proof_deliverables", "parameters", "hypotheses", "conclusion_clauses"],
            "properties": {
                "proof_deliverables": _contract_string_list_schema(min_items=1),
                "parameters": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_PARAMETER_INPUT_SCHEMA),
                },
                "hypotheses": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_HYPOTHESIS_INPUT_SCHEMA),
                },
                "conclusion_clauses": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_CONCLUSION_INPUT_SCHEMA),
                },
            },
        },
    },
    {
        "if": {
            "properties": {
                "statement": {
                    "anyOf": [
                        {"type": "string", "pattern": pattern} for pattern in _THEOREM_STYLE_STATEMENT_SCHEMA_PATTERNS
                    ]
                }
            }
        },
        "then": {
            "required": ["proof_deliverables", "parameters", "hypotheses", "conclusion_clauses"],
            "properties": {
                "proof_deliverables": _contract_string_list_schema(min_items=1),
                "parameters": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_PARAMETER_INPUT_SCHEMA),
                },
                "hypotheses": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_HYPOTHESIS_INPUT_SCHEMA),
                },
                "conclusion_clauses": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_CONCLUSION_INPUT_SCHEMA),
                },
            },
        },
    },
    {
        "if": {
            "anyOf": [
                {
                    "required": [field_name],
                    "properties": {field_name: {"type": "array", "minItems": 1}},
                }
                for field_name in (
                    "proof_deliverables",
                    "parameters",
                    "hypotheses",
                    "quantifiers",
                    "conclusion_clauses",
                )
            ]
        },
        "then": {
            "required": ["claim_kind", "proof_deliverables", "parameters", "hypotheses", "conclusion_clauses"],
            "properties": {
                "claim_kind": _contract_enum_string_schema(_PROOF_FIELD_CLAIM_KIND_VALUES),
                "proof_deliverables": _contract_string_list_schema(min_items=1),
                "parameters": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_PARAMETER_INPUT_SCHEMA),
                },
                "hypotheses": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_HYPOTHESIS_INPUT_SCHEMA),
                },
                "conclusion_clauses": {
                    "type": "array",
                    "minItems": 1,
                    "items": dict(_CONTRACT_PROOF_CONCLUSION_INPUT_SCHEMA),
                },
            },
        },
    },
]
_CONTRACT_DELIVERABLE_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "kind": _contract_enum_string_schema(CONTRACT_DELIVERABLE_KIND_VALUES),
        "path": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "description": _non_empty_string_schema(),
        "must_contain": _contract_string_list_schema(),
    },
    required=("id", "description"),
    additional_properties=False,
)
_CONTRACT_ACCEPTANCE_TEST_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "subject": _non_empty_string_schema(),
        "kind": _contract_enum_string_schema(CONTRACT_ACCEPTANCE_TEST_KIND_VALUES),
        "procedure": _non_empty_string_schema(),
        "pass_condition": _non_empty_string_schema(),
        "evidence_required": _contract_string_list_schema(),
        "automation": _contract_enum_string_schema(CONTRACT_ACCEPTANCE_AUTOMATION_VALUES),
    },
    required=("id", "subject", "procedure", "pass_condition"),
    additional_properties=False,
)
_CONTRACT_REFERENCE_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "kind": _contract_enum_string_schema(CONTRACT_REFERENCE_KIND_VALUES),
        "locator": _non_empty_string_schema(),
        "aliases": _contract_string_list_schema(),
        "role": _contract_enum_string_schema(CONTRACT_REFERENCE_ROLE_VALUES),
        "why_it_matters": _non_empty_string_schema(),
        "applies_to": _contract_string_list_schema(),
        "carry_forward_to": _contract_string_list_schema(),
        "must_surface": {"type": "boolean"},
        "required_actions": _contract_enum_string_list_schema(CONTRACT_REFERENCE_ACTION_VALUES),
    },
    required=("id", "locator", "why_it_matters"),
    additional_properties=False,
)
_CONTRACT_REFERENCE_INPUT_SCHEMA["description"] = (
    "Closed reference-anchor object. `must_surface` must stay boolean; when it is `true`, "
    "`applies_to` and `required_actions` must both be non-empty lists. "
    "`carry_forward_to` names workflow scope labels, never contract ids."
)
_CONTRACT_REFERENCE_INPUT_SCHEMA["allOf"] = [
    {
        "if": {
            "required": ["must_surface"],
            "properties": {"must_surface": {"const": True}},
        },
        "then": {
            "required": ["applies_to", "required_actions"],
            "properties": {
                "applies_to": _contract_string_list_schema(min_items=1),
                "required_actions": _contract_enum_string_list_schema(
                    CONTRACT_REFERENCE_ACTION_VALUES,
                    min_items=1,
                ),
            },
        },
    }
]
_CONTRACT_FORBIDDEN_PROXY_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "subject": _non_empty_string_schema(),
        "proxy": _non_empty_string_schema(),
        "reason": _non_empty_string_schema(),
    },
    required=("id", "subject", "proxy", "reason"),
    additional_properties=False,
)
_CONTRACT_LINK_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        "id": _non_empty_string_schema(),
        "source": _non_empty_string_schema(),
        "target": _non_empty_string_schema(),
        "relation": _contract_enum_string_schema(CONTRACT_LINK_RELATION_VALUES),
        "verified_by": _contract_string_list_schema(),
    },
    required=("id", "source", "target"),
    additional_properties=False,
)
_CONTRACT_UNCERTAINTY_MARKERS_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        field_name: _contract_string_or_string_list_schema(
            min_items=1 if field_name in {"weakest_anchors", "disconfirming_observations"} else None
        )
        for field_name in CONTRACT_UNCERTAINTY_MARKER_FIELD_NAMES
    },
    required=("weakest_anchors", "disconfirming_observations"),
    additional_properties=False,
)
_CONTRACT_UNCERTAINTY_MARKERS_INPUT_SCHEMA["description"] = (
    "Keep unresolved risk explicit. `weakest_anchors` and `disconfirming_observations` are required and must stay "
    "non-empty so later validation does not treat uncertainty as silently resolved."
)
_CONTRACT_PAYLOAD_INPUT_SCHEMA: dict[str, object] = _object_schema(
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
    required=("schema_version", "scope", "context_intake", "uncertainty_markers"),
    additional_properties=False,
)
_CONTRACT_PAYLOAD_INPUT_SCHEMA["description"] = verification_contract_policy_text()
_CONTRACT_PAYLOAD_INPUT_SCHEMA["allOf"] = [
    {
        "if": {"required": ["claims"], "properties": {"claims": {"type": "array", "minItems": 1}}},
        "then": {"required": ["deliverables", "acceptance_tests"]},
    }
]


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
                    "required": ["check_key"],
                    "properties": {"check_key": {"enum": list(identifiers)}},
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


def _compact_contract_payload_requirement_schema() -> dict[str, object]:
    return {
        "type": "object",
        "required": ["schema_version", "scope", "context_intake", "uncertainty_markers"],
        "additionalProperties": True,
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "scope": {"type": "object"},
            "context_intake": {"type": "object"},
            "uncertainty_markers": {"type": "object"},
        },
    }


def _request_section_required_schema(
    section_name: str,
    section_schema: dict[str, object],
    required_fields: Iterable[str],
) -> dict[str, object]:
    required_list = [field for field in required_fields if field]
    if section_name == "contract":
        schema = _compact_contract_payload_requirement_schema()
        if required_list:
            schema["required"] = list(dict.fromkeys([*schema["required"], *required_list]))
        return schema

    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": True,
    }
    if required_list:
        schema["required"] = required_list
    source_properties = section_schema.get("properties")
    if isinstance(source_properties, dict) and required_list:
        strict_properties: dict[str, object] = {}
        for field_name in required_list:
            field_schema = source_properties.get(field_name)
            if isinstance(field_schema, dict):
                strict_properties[field_name] = _strict_required_schema_fragment(
                    field_schema,
                    allow_empty_array=(section_name, field_name) in _REQUIRED_FIELD_ALLOW_EMPTY_ARRAY,
                )
        if strict_properties:
            schema["properties"] = strict_properties
    return schema


def _request_requirement_schema(required_fields: Iterable[str]) -> dict[str, object]:
    section_requirements: dict[str, list[str]] = {}
    top_level_required: list[str] = []
    for field_path in required_fields:
        if not isinstance(field_path, str) or not field_path:
            continue
        section, separator, nested_field = field_path.partition(".")
        if not separator:
            if section not in top_level_required:
                top_level_required.append(section)
            continue
        section_requirements.setdefault(section, [])
        if nested_field not in section_requirements[section]:
            section_requirements[section].append(nested_field)

    schema: dict[str, object] = {}
    required_top_level = list(dict.fromkeys([*top_level_required, *section_requirements.keys()]))
    if required_top_level:
        schema["required"] = required_top_level

    section_schemas: dict[str, object] = {}
    section_schema_sources: dict[str, dict[str, object]] = {
        "metadata": _CONTRACT_METADATA_INPUT_SCHEMA,
        "observed": _CONTRACT_OBSERVED_INPUT_SCHEMA,
        "binding": _CONTRACT_BINDING_INPUT_SCHEMA,
        "contract": _CONTRACT_PAYLOAD_INPUT_SCHEMA,
    }
    for section_name, section_schema in section_schema_sources.items():
        if section_name in section_requirements:
            section_schemas[section_name] = _request_section_required_schema(
                section_name,
                section_schema,
                section_requirements[section_name],
            )
        elif section_name in top_level_required:
            if section_name == "contract":
                section_schemas[section_name] = _compact_contract_payload_requirement_schema()
            else:
                section_schemas[section_name] = {"type": "object", "minProperties": 1}
    if "artifact_content" in top_level_required:
        section_schemas["artifact_content"] = _strict_required_schema_fragment(_non_empty_string_or_null_schema())
    if section_schemas:
        schema["properties"] = section_schemas
    return schema


def _run_contract_request_requirement_condition_schema(
    check_key: str, hint: dict[str, object]
) -> dict[str, object] | None:
    check_meta = get_verification_check(check_key)
    if check_meta is None:
        return None
    identifiers = _check_identifier_values({"check_key": check_meta.check_key, "check_id": check_meta.check_id})
    if not identifiers:
        return None

    required_fields = list(hint.get("schema_required_request_fields", hint.get("required_request_fields", [])))
    anyof_groups = [
        [field for field in group if isinstance(field, str) and field]
        for group in hint.get("schema_required_request_anyof_fields", [])
        if isinstance(group, (list, tuple))
    ]
    if not required_fields and not anyof_groups:
        return None

    then_schema: dict[str, object] = {}
    if required_fields:
        then_schema.update(_request_requirement_schema(required_fields))
    if anyof_groups:
        then_schema["anyOf"] = [_request_requirement_schema(group) for group in anyof_groups]

    if not then_schema:
        return None

    return {
        "if": {
            "required": ["check_key"],
            "properties": {"check_key": {"type": "string", "enum": list(identifiers)}},
        },
        "then": then_schema,
    }


_RUN_CONTRACT_CHECK_BINDING_CONDITIONS = _run_contract_binding_condition_schema()
_RUN_CONTRACT_CHECK_REQUIRED_FIELD_CONDITIONS = [
    condition
    for check_key, hint in _CONTRACT_CHECK_REQUEST_HINTS.items()
    if (condition := _run_contract_request_requirement_condition_schema(check_key, hint)) is not None
]
_RUN_CONTRACT_CHECK_IDENTIFIER_SCHEMA: dict[str, object] = {
    **dict(_trimmed_non_empty_string_schema()),
    "enum": list(_CONTRACT_CHECK_IDENTIFIER_VALUES),
}
_RUN_CONTRACT_CHECK_IDENTIFIER_OR_NULL_SCHEMA: dict[str, object] = {
    "anyOf": [dict(_RUN_CONTRACT_CHECK_IDENTIFIER_SCHEMA), {"type": "null"}]
}
_RUN_CONTRACT_CHECK_REQUEST_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "anyOf": [
        {
            "required": ["check_key"],
            "properties": {"check_key": dict(_RUN_CONTRACT_CHECK_IDENTIFIER_SCHEMA)},
        },
    ],
    "properties": {
        "check_key": dict(_RUN_CONTRACT_CHECK_IDENTIFIER_OR_NULL_SCHEMA),
        "contract": {"anyOf": [dict(_CONTRACT_PAYLOAD_INPUT_SCHEMA), {"type": "null"}]},
        "binding": {"anyOf": [dict(_CONTRACT_BINDING_INPUT_SCHEMA), {"type": "null"}]},
        "metadata": {"anyOf": [dict(_CONTRACT_METADATA_INPUT_SCHEMA), {"type": "null"}]},
        "observed": {"anyOf": [dict(_CONTRACT_OBSERVED_INPUT_SCHEMA), {"type": "null"}]},
        "artifact_content": _non_empty_string_or_null_schema(),
    },
}
_RUN_CONTRACT_CHECK_REQUEST_SCHEMA["description"] = (
    "Closed `run_contract_check` request object. `check_key` is required and accepts the "
    "canonical check key or a stable numeric id. `contract`, `binding`, `metadata`, "
    "`observed`, and `artifact_content` are optional sections. The compact published schema keeps "
    "per-check required-field guards while runtime validation and verdict construction remain "
    "authoritative. "
    "When `binding` is present, use only the canonical plural `*_ids` arrays surfaced in "
    "`supported_binding_fields`. Use `suggest_contract_checks(contract, active_checks=...)` "
    "first to inspect `required_request_fields`, `schema_required_request_fields`, "
    "`schema_required_request_anyof_fields`, `optional_request_fields`, "
    "`supported_binding_fields`, and a safe `request_template`."
)
all_of_conditions: list[dict[str, object]] = []
if _RUN_CONTRACT_CHECK_BINDING_CONDITIONS:
    all_of_conditions.extend(_RUN_CONTRACT_CHECK_BINDING_CONDITIONS)
all_of_conditions.extend(_RUN_CONTRACT_CHECK_REQUIRED_FIELD_CONDITIONS)
if all_of_conditions:
    _RUN_CONTRACT_CHECK_REQUEST_SCHEMA["allOf"] = all_of_conditions

RunContractCheckPayload = Annotated[object, WithJsonSchema(_RUN_CONTRACT_CHECK_REQUEST_SCHEMA)]
SuggestContractPayload = Annotated[object, WithJsonSchema(_CONTRACT_PAYLOAD_INPUT_SCHEMA)]
StringListPayload = Annotated[
    object | None,
    WithJsonSchema({"anyOf": [{"type": "array", "items": _non_empty_string_schema()}, {"type": "null"}]}),
]
OptionalAbsoluteProjectDirInput = Annotated[
    str | None,
    WithJsonSchema({"anyOf": [dict(ABSOLUTE_PROJECT_DIR_SCHEMA), {"type": "null"}]}),
]
RunCheckIdentifierInput = Annotated[
    str,
    Field(min_length=1, pattern=r"\S"),
    WithJsonSchema(dict(_RUN_CHECK_IDENTIFIER_SCHEMA)),
]
BundleIdListInput = Annotated[
    list[str],
    WithJsonSchema(_string_list_schema()),
]


def _run_contract_check_description() -> str:
    return (
        "Run a contract-aware verification check from a single structured ``request`` object. "
        "The published ``request`` input schema is compact and closed; use ``suggest_contract_checks`` "
        "for per-check required-request metadata before execution. "
        "``request.contract`` is optional, but proof-oriented checks still require an authoritative "
        "contract payload. ``project_dir`` is optional, but when the contract uses project-local anchors "
        "or prior-output paths it should be the absolute project root so those references are validated "
        "against the correct filesystem context. "
        f"{verification_contract_surface_summary_text()}"
    )


def _suggest_contract_checks_description() -> str:
    return (
        "Suggest contract-aware checks from a schema-validated project or phase ``contract``. "
        "``contract`` must be an object with the normal GPD contract structure. "
        "``project_dir`` is optional, but supply the absolute project root whenever the contract uses "
        "project-local anchors or prior-output paths so grounding-sensitive checks see the same root "
        "the model is reasoning about. "
        f"{verification_contract_surface_summary_text()} "
        "Use the canonical plan-contract schema for plan-style payloads; this tool returns the exact "
        "request-shape metadata, including ``schema_required_request_fields``, "
        "``schema_required_request_anyof_fields``, ``supported_binding_fields``, and a ``request_template`` safe "
        "to pass to ``run_contract_check(request=...)``. "
        "``active_checks`` is optional and must be ``list[str]`` with non-empty entries when provided. "
        "Supply already-enabled check ids or check keys so each suggestion can mark ``already_active`` "
        "precisely. Proof-check templates still surface an explicit ``contract`` placeholder because "
        "runtime execution requires an authoritative contract payload."
    )


def _validate_string_mapping(
    value: object,
    *,
    field_name: str,
) -> tuple[dict[str, str] | None, dict[str, object] | None]:
    """Return a validated dict[str, str] or an MCP error envelope."""
    if not isinstance(value, dict):
        return None, _error_result(f"{field_name} must be an object with string keys and string values")

    validated: dict[str, str] = {}
    seen_keys: set[str] = set()
    for key, item in value.items():
        if not isinstance(key, str):
            return None, _error_result(f"{field_name} keys must be strings")
        stripped_key = key.strip()
        if not stripped_key:
            return None, _error_result(f"{field_name} keys must be non-empty strings")
        if stripped_key in seen_keys:
            return None, _error_result(f"{field_name} must not contain duplicate keys after trimming whitespace")
        seen_keys.add(stripped_key)
        if not isinstance(item, str):
            return None, _error_result(f"{field_name}[{key}] must be a string")
        stripped_item = item.strip()
        if not stripped_item:
            return None, _error_result(f"{field_name}[{stripped_key}] must be a non-empty string")
        validated[stripped_key] = stripped_item
    return validated, None


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


@mcp.tool(annotations=read_only_tool_annotations())
def run_check(
    check_id: RunCheckIdentifierInput,
    domain: Annotated[str, Field(min_length=1, pattern=r"\S")],
    artifact_content: Annotated[str, Field(min_length=1, pattern=r"\S")],
) -> dict:
    """Run static triage for a verification check on an artifact.

    Returns check metadata, static pattern findings, and caller guidance.
    This tool is non-authoritative: it does not perform physics verification,
    does not pass or certify the artifact, and cannot grant final verification
    status. Empty ``automated_issues`` means only that this static scan found
    no matching pattern issue.
    The actual physics verification is performed by the calling agent;
    this tool provides the check specification, what to look for,
    and structured result formatting.

    ``check_id`` accepts the stable numeric check ids (for example ``"5.1"``)
    and the canonical check keys (for example ``"contract.limit_recovery"``).
    For contract-aware checks, the response also surfaces
    ``required_request_fields``, ``schema_required_request_fields``,
    ``schema_required_request_anyof_fields``, ``optional_request_fields``,
    ``supported_binding_fields``, and a ``request_template`` so callers can
    build a valid ``run_contract_check`` request before executing it.

    Args:
        check_id: Check identifier or canonical check key
        domain: Physics domain for domain-specific guidance
        artifact_content: The content to verify (derivation, code, etc.)
    """
    if not isinstance(check_id, str) or not check_id.strip():
        return _error_result("check_id must be a non-empty string")
    if not isinstance(domain, str) or not domain.strip():
        return _error_result("domain must be a non-empty string")
    if not isinstance(artifact_content, str) or not artifact_content.strip():
        return _error_result("artifact_content must be a non-empty string")

    with gpd_span("mcp.verification.run_check", check_type=check_id, domain=domain):
        try:
            check_meta = get_verification_check(check_id)
            if check_meta is None:
                return _error_result(
                    f"Unknown check_id: {check_id}. Valid identifiers include: {list(_RUN_CHECK_IDENTIFIER_VALUES)}"
                )

            # Get domain-specific guidance
            domain_checks = DOMAIN_CHECKLISTS.get(domain, [])
            relevant_domain_checks = [
                c
                for c in domain_checks
                if check_meta.check_id
                in [token.strip() for token in c.get("check_ids", "").split(",") if token.strip()]
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
                if any(kw in artifact_lower for kw in fit_keywords) and not any(
                    kw in artifact_lower for kw in diagnostics
                ):
                    issues.append("Fit family is present without residual or family-selection diagnostics")

            elif check_meta.check_id == "5.19":
                estimator_keywords = ["estimator", "bootstrap", "jackknife", "posterior", "bayesian", "reweight"]
                diagnostics = ["bias", "variance", "consistency", "calibration", "ess", "autocorrelation"]
                if any(kw in artifact_lower for kw in estimator_keywords) and not any(
                    kw in artifact_lower for kw in diagnostics
                ):
                    issues.append("Estimator family is present without bias/variance or calibration diagnostics")

            elif check_meta.check_id == "5.20":
                proof_keywords = ["hypothesis", "assumption", "suppose", "regime", "under the conditions"]
                if not any(kw in artifact_lower for kw in proof_keywords):
                    issues.append("No explicit hypothesis coverage ledger found for the proof-bearing claim")

            elif check_meta.check_id == "5.21":
                if not any(kw in artifact_lower for kw in ["parameter", "symbol", "for all", "r_0", "r0"]):
                    issues.append("No explicit theorem-parameter coverage audit found in the proof artifact")

            elif check_meta.check_id == "5.22":
                quantifier_keywords = ["for all", "exists", "domain", "regime", "scope", "quantifier"]
                if not any(kw in artifact_lower for kw in quantifier_keywords):
                    issues.append("No explicit quantifier/domain fidelity audit found in the proof artifact")

            elif check_meta.check_id == "5.23":
                alignment_keywords = ["claim", "theorem", "conclusion", "therefore", "thus", "proved"]
                if not any(kw in artifact_lower for kw in alignment_keywords):
                    issues.append("No explicit claim-to-proof alignment evidence found in the artifact")

            elif check_meta.check_id == "5.24":
                counterexample_keywords = ["counterexample", "adversarial", "red-team", "narrowed claim", "edge case"]
                if not any(kw in artifact_lower for kw in counterexample_keywords):
                    issues.append("No explicit counterexample or adversarial search evidence found in the artifact")

            result = _serialize_verification_check_entry(check_meta.model_dump())
            result.update(
                {
                    "check_name": check_meta.name,
                    "domain": domain,
                    "domain_specific_checks": relevant_domain_checks,
                    "automated_issues": issues,
                    "result_kind": "static_triage",
                    "triage_status": "schema_only" if not issues else "failed_or_tension",
                    "passes_physics": False,
                    "requires_caller_verification": True,
                    "grants_final_verification_pass": False,
                    "empty_automated_issues_means": (
                        "No static pattern issue was detected; this is not a pass verdict."
                    ),
                    "artifact_length": len(artifact_content),
                    "guidance": (
                        f"Run check {check_meta.check_id} ({check_meta.name}) for domain '{domain}'. "
                        f"This static triage check catches: {check_meta.catches}. "
                        "Caller-owned verification is still required before assigning any final status."
                    ),
                }
            )
            return stable_mcp_response(result)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return _error_result(exc)


@mcp.tool(description=_run_contract_check_description(), annotations=read_only_tool_annotations())
def run_contract_check(request: RunContractCheckPayload, project_dir: OptionalAbsoluteProjectDirInput = None) -> dict:
    """Run a contract-aware verification check."""

    with gpd_span("mcp.verification.run_contract_check"):
        return contract_checks.run_contract_check(request, project_dir, check_lookup=get_verification_check)


@mcp.tool(description=_suggest_contract_checks_description(), annotations=read_only_tool_annotations())
def suggest_contract_checks(
    contract: SuggestContractPayload,
    active_checks: StringListPayload = None,
    project_dir: OptionalAbsoluteProjectDirInput = None,
) -> dict:
    """Suggest contract-aware checks from a schema-validated contract."""

    with gpd_span("mcp.verification.suggest_contract_checks"):
        return contract_checks.suggest_contract_checks(
            contract,
            active_checks,
            project_dir,
            check_lookup=get_verification_check,
        )


@mcp.tool(annotations=read_only_tool_annotations())
def get_checklist(domain: Annotated[str, Field(min_length=1, pattern=r"\S")]) -> dict:
    """Return the domain-specific verification checklist.

    Provides the complete list of checks recommended for a physics domain,
    including which live verifier-registry checks (currently 5.1-5.24) each maps to.
    """
    with gpd_span("mcp.verification.checklist", domain=domain):
        return contract_checks.get_checklist(domain, check_lister=list_verification_checks)


@mcp.tool(annotations=read_only_tool_annotations())
def get_bundle_checklist(bundle_ids: BundleIdListInput) -> dict:
    """Return additive verifier checklist extensions for selected protocol bundles."""
    validated_bundle_ids, _rejection = _validate_string_list(bundle_ids, field_name="bundle_ids")
    normalized_bundle_ids = _unique_strings(validated_bundle_ids or [])
    with gpd_span("mcp.verification.bundle_checklist", bundle_count=len(normalized_bundle_ids)):
        return contract_checks.get_bundle_checklist(bundle_ids, bundle_lookup=get_protocol_bundle)


@mcp.tool(annotations=read_only_tool_annotations())
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

        no_annotations = all(v == 0 for v in lhs_dims.values()) and all(v == 0 for v in rhs_dims.values())
        match = _dims_equal(lhs_dims, rhs_dims)
        result: dict[str, object] = {
            "expression": expr,
            "valid": match and not no_annotations,
            "no_dimensions_found": no_annotations,
            "lhs_dimensions": {k: v for k, v in lhs_dims.items() if v != 0},
            "rhs_dimensions": {k: v for k, v in rhs_dims.items() if v != 0},
        }
        if no_annotations:
            result["note"] = "No dimension annotations found — cannot verify"
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


@mcp.tool(annotations=read_only_tool_annotations())
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


@mcp.tool(annotations=read_only_tool_annotations())
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


@mcp.tool(annotations=read_only_tool_annotations())
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
        return contract_checks.get_verification_coverage(error_class_ids, active_checks)


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the gpd-verification MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Verification MCP Server")


tighten_registered_tool_contracts(mcp)


if __name__ == "__main__":
    main()
