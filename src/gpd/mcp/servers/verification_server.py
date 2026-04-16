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
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, create_model
from pydantic import ValidationError as PydanticValidationError

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
    PROJECT_CONTRACT_COLLECTION_LIST_FIELDS,
    PROJECT_CONTRACT_MAPPING_LIST_FIELDS,
    PROOF_ACCEPTANCE_TEST_KINDS,
    PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES,
    PROOF_AUDIT_QUANTIFIER_STATUS_VALUES,
    PROOF_AUDIT_SCOPE_STATUS_VALUES,
    PROOF_HYPOTHESIS_CATEGORY_VALUES,
    THEOREM_CLAIM_KIND_VALUES,
    THEOREM_STYLE_STATEMENT_REGEX_PATTERNS,
    ResearchContract,
    collect_plan_contract_integrity_errors,
    contract_has_explicit_context_intake,
    parse_project_contract_data_salvage,
    parse_project_contract_data_strict,
    statement_looks_theorem_like,
)
from gpd.core.contract_validation import (
    is_authoritative_project_contract_schema_finding,
    is_repair_relevant_project_contract_schema_finding,
    split_project_contract_schema_findings,
)
from gpd.core.observability import gpd_span
from gpd.core.protocol_bundles import ResolvedProtocolBundle, get_protocol_bundle, render_protocol_bundle_context
from gpd.core.verification_checks import (
    ERROR_CLASS_COVERAGE,
    VERIFICATION_SCHEMA_VERSION,
    get_verification_check,
    list_verification_checks,
)
from gpd.mcp.servers import (
    ABSOLUTE_PROJECT_DIR_SCHEMA,
    configure_mcp_logging,
    resolve_absolute_project_dir,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)
from gpd.mcp.verification_contract_policy import (
    VERIFICATION_BINDING_FIELD_NAMES,
    VERIFICATION_BINDING_TARGETS,
    verification_contract_policy_text,
    verification_contract_surface_summary_text,
)

logger = configure_mcp_logging("gpd-verification")

mcp = FastMCP("gpd-verification")

_CONTRACT_ERROR_PATH_RE = re.compile(
    r"^(schema_version|[A-Za-z_][A-Za-z0-9_]*(?:\.\d+|\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*)(?:: | )"
)
_REFERENCE_ACTIONS = frozenset(CONTRACT_REFERENCE_ACTION_VALUES)
_CONTRACT_ERROR_FIELD_ORDER = {
    "schema_version": 0,
    "scope": 1,
    "context_intake": 2,
    "approach_policy": 3,
    "observables": 4,
    "claims": 5,
    "deliverables": 6,
    "acceptance_tests": 7,
    "references": 8,
    "forbidden_proxies": 9,
    "links": 10,
    "uncertainty_markers": 11,
}

_CONTRACT_CHECK_REQUEST_HINTS: dict[str, dict[str, object]] = {
    "contract.limit_recovery": {
        "required_request_fields": [
            "metadata.regime_label",
            "metadata.expected_behavior",
        ],
        "schema_required_request_fields": [
            "metadata.regime_label",
            "metadata.expected_behavior",
        ],
        "optional_request_fields": [
            "binding.*",
            "observed.limit_passed",
            "observed.observed_limit",
            "artifact_content",
        ],
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
            "artifact_content": "",
        },
    },
    "contract.benchmark_reproduction": {
        "required_request_fields": [
            "metadata.source_reference_id",
            "observed.metric_value",
            "observed.threshold_value",
        ],
        "schema_required_request_fields": [
            "observed.metric_value",
            "observed.threshold_value",
        ],
        "schema_required_request_anyof_fields": [
            ["metadata.source_reference_id"],
            ["contract"],
        ],
        "optional_request_fields": ["metadata.source_reference_id", "binding.*", "artifact_content"],
        "request_template": {
            "binding": {},
            "metadata": {
                "source_reference_id": None,
            },
            "observed": {
                "metric_value": None,
                "threshold_value": None,
            },
            "artifact_content": "",
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
            "artifact_content": "",
        },
    },
    "contract.fit_family_mismatch": {
        "required_request_fields": ["metadata.declared_family", "observed.selected_family"],
        "schema_required_request_fields": ["metadata.declared_family", "observed.selected_family"],
        "optional_request_fields": [
            "binding.*",
            "metadata.allowed_families",
            "metadata.forbidden_families",
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
            "artifact_content": "",
        },
    },
    "contract.estimator_family_mismatch": {
        "required_request_fields": [
            "metadata.declared_family",
            "observed.selected_family",
            "observed.bias_checked",
            "observed.calibration_checked",
        ],
        "schema_required_request_fields": [
            "metadata.declared_family",
            "observed.selected_family",
            "observed.bias_checked",
            "observed.calibration_checked",
        ],
        "optional_request_fields": [
            "binding.*",
            "metadata.allowed_families",
            "metadata.forbidden_families",
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
            "artifact_content": "",
        },
    },
    "contract.proof_hypothesis_coverage": {
        "required_request_fields": [
            "contract",
            "metadata.hypothesis_ids",
            "observed.covered_hypothesis_ids",
        ],
        "schema_required_request_fields": [
            "contract",
            "metadata.hypothesis_ids",
            "observed.covered_hypothesis_ids",
        ],
        "optional_request_fields": ["binding.*", "artifact_content"],
        "request_template": {
            "contract": None,
            "binding": {},
            "metadata": {
                "hypothesis_ids": None,
            },
            "observed": {
                "covered_hypothesis_ids": None,
                "missing_hypothesis_ids": None,
            },
            "artifact_content": "",
        },
    },
    "contract.proof_parameter_coverage": {
        "required_request_fields": [
            "contract",
            "metadata.theorem_parameter_symbols",
            "observed.covered_parameter_symbols",
        ],
        "schema_required_request_fields": [
            "contract",
            "metadata.theorem_parameter_symbols",
            "observed.covered_parameter_symbols",
        ],
        "optional_request_fields": ["binding.*", "artifact_content"],
        "request_template": {
            "contract": None,
            "binding": {},
            "metadata": {
                "theorem_parameter_symbols": None,
            },
            "observed": {
                "covered_parameter_symbols": None,
                "missing_parameter_symbols": None,
            },
            "artifact_content": "",
        },
    },
    "contract.proof_quantifier_domain": {
        "required_request_fields": [
            "contract",
            "observed.quantifier_status",
            "observed.scope_status",
        ],
        "schema_required_request_fields": [
            "contract",
            "observed.quantifier_status",
            "observed.scope_status",
        ],
        "optional_request_fields": ["binding.*", "metadata.quantifiers", "observed.uncovered_quantifiers", "artifact_content"],
        "request_template": {
            "contract": None,
            "binding": {},
            "metadata": {
                "quantifiers": None,
            },
            "observed": {
                "uncovered_quantifiers": None,
                "quantifier_status": None,
                "scope_status": None,
            },
            "artifact_content": "",
        },
    },
    "contract.claim_to_proof_alignment": {
        "required_request_fields": [
            "contract",
            "observed.scope_status",
        ],
        "schema_required_request_fields": ["contract", "observed.scope_status"],
        "schema_required_request_anyof_fields": [
            ["metadata.claim_statement"],
            ["metadata.conclusion_clause_ids", "observed.uncovered_conclusion_clause_ids"],
        ],
        "optional_request_fields": [
            "binding.*",
            "metadata.claim_statement",
            "metadata.conclusion_clause_ids",
            "observed.uncovered_conclusion_clause_ids",
            "artifact_content",
        ],
        "request_template": {
            "contract": None,
            "binding": {},
            "metadata": {
                "claim_statement": None,
                "conclusion_clause_ids": None,
            },
            "observed": {
                "uncovered_conclusion_clause_ids": None,
                "scope_status": None,
            },
            "artifact_content": "",
        },
    },
    "contract.counterexample_search": {
        "required_request_fields": ["contract", "observed.counterexample_status"],
        "schema_required_request_fields": ["contract", "observed.counterexample_status"],
        "optional_request_fields": ["binding.*", "metadata.claim_statement", "artifact_content"],
        "request_template": {
            "contract": None,
            "binding": {},
            "metadata": {
                "claim_statement": None,
            },
            "observed": {
                "counterexample_status": None,
            },
            "artifact_content": "",
        },
    },
}


class _ContractRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _binding_request_field_name(binding_field_name: str) -> str:
    return binding_field_name.removeprefix("binding.")


ContractBindingRequest = create_model(
    "ContractBindingRequest",
    __base__=_ContractRequestBase,
    **{
        _binding_request_field_name(binding_field_name): (
            list[str] | None,
            Field(
                default=None,
                description=f"Binding to one or more {target.replace('_', '-')} ids.",
            ),
        )
        for target, binding_field_name in zip(VERIFICATION_BINDING_TARGETS, VERIFICATION_BINDING_FIELD_NAMES, strict=True)
    },
)
ContractBindingRequest.__doc__ = "Closed binding request surface derived from the canonical verification binding fields."


class ContractMetadataRequest(_ContractRequestBase):
    regime_label: str | None = None
    expected_behavior: str | None = None
    source_reference_id: str | None = None
    declared_family: str | None = None
    allowed_families: list[str] | None = None
    forbidden_families: list[str] | None = None
    theorem_parameter_symbols: list[str] | None = None
    hypothesis_ids: list[str] | None = None
    quantifiers: list[str] | None = None
    conclusion_clause_ids: list[str] | None = None
    claim_statement: str | None = None


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
    covered_hypothesis_ids: list[str] | None = None
    missing_hypothesis_ids: list[str] | None = None
    covered_parameter_symbols: list[str] | None = None
    missing_parameter_symbols: list[str] | None = None
    uncovered_quantifiers: list[str] | None = None
    uncovered_conclusion_clause_ids: list[str] | None = None
    quantifier_status: str | None = None
    scope_status: str | None = None
    counterexample_status: str | None = None


class RunContractCheckRequest(_ContractRequestBase):
    check_key: str | None = Field(
        default=None,
        description=(
            "Canonical contract-aware check key, or a stable numeric id that resolves to the same check. "
            "Must be a non-empty string without leading or trailing whitespace when present."
        ),
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


def _strict_required_schema_fragment(schema_fragment: dict[str, object]) -> dict[str, object]:
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
            strict_branches.append(_strict_required_schema_fragment(branch))
        if len(strict_branches) == 1 and isinstance(strict_branches[0], dict):
            return strict_branches[0]
        schema["anyOf"] = strict_branches
    if schema.get("type") == "array" and (not isinstance(schema.get("minItems"), int) or int(schema["minItems"]) < 1):
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


def _contract_enum_string_or_string_list_schema(
    values: Iterable[str],
    *,
    min_items: int | None = None,
) -> dict[str, object]:
    return {
        "anyOf": [
            _contract_enum_string_schema(values),
            _contract_enum_string_list_schema(values, min_items=min_items),
        ]
    }


def _binding_input_schema_for_targets(targets: Iterable[str]) -> dict[str, object]:
    properties: dict[str, object] = {}
    for target in targets:
        properties[f"{target}_ids"] = _string_list_schema(min_items=1)
    return _object_schema(properties, additional_properties=False)


_PROOF_CLAIM_KIND_VALUES = THEOREM_CLAIM_KIND_VALUES
_PROOF_ACCEPTANCE_TEST_KIND_VALUES = PROOF_ACCEPTANCE_TEST_KINDS
_PROOF_CHECK_TO_ACCEPTANCE_KIND = {
    "contract.proof_hypothesis_coverage": "proof_hypothesis_coverage",
    "contract.proof_parameter_coverage": "proof_parameter_coverage",
    "contract.proof_quantifier_domain": "proof_quantifier_domain",
    "contract.claim_to_proof_alignment": "claim_to_proof_alignment",
    "contract.counterexample_search": "counterexample_search",
}
_PROOF_CHECK_KEYS = frozenset(_PROOF_CHECK_TO_ACCEPTANCE_KIND)
_QUANTIFIER_STATUS_VALUES = PROOF_AUDIT_QUANTIFIER_STATUS_VALUES
_SCOPE_STATUS_VALUES = PROOF_AUDIT_SCOPE_STATUS_VALUES
_COUNTEREXAMPLE_STATUS_VALUES = PROOF_AUDIT_COUNTEREXAMPLE_STATUS_VALUES
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
_RUN_CHECK_IDENTIFIER_VALUES: tuple[str, ...] = tuple(
    dict.fromkeys(
        identifier
        for entry in list_verification_checks()
        for identifier in _check_identifier_values(entry)
    )
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
        "in_scope": _contract_string_list_schema(),
        "out_of_scope": _contract_string_list_schema(),
        "unresolved_questions": _contract_string_list_schema(),
    },
    required=("question",),
    additional_properties=False,
)
_CONTRACT_SCOPE_INPUT_SCHEMA["description"] = (
    "Use `scope.question` for the core research question. Project-scoping contracts must also provide non-empty "
    "`scope.in_scope` naming at least one concrete objective or boundary; downstream project-contract validation "
    "does not infer it."
)
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA: dict[str, object] = _object_schema(
    {
        field_name: _contract_string_list_schema(min_items=1)
        for field_name in CONTRACT_CONTEXT_INTAKE_FIELD_NAMES
    },
    additional_properties=False,
)
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA["minProperties"] = 1
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA["anyOf"] = [
    {"required": [field_name]}
    for field_name in CONTRACT_CONTEXT_INTAKE_FIELD_NAMES
]
_CONTRACT_CONTEXT_INTAKE_INPUT_SCHEMA["description"] = (
    "`context_intake` is required and must stay non-empty. Use it to surface anchors, prior outputs, baselines, "
    "gaps, or other user-stated inputs the model must still see when later contract-aware tools validate the work."
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
    "Do not rely on runtime inference for those cases. Proof-bearing claims must set an explicit proof-oriented `claim_kind`, provide non-empty "
    "`proof_deliverables`, `parameters`, `hypotheses`, and `conclusion_clauses`, and reference at least one "
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
                        {"type": "string", "pattern": pattern}
                        for pattern in _THEOREM_STYLE_STATEMENT_SCHEMA_PATTERNS
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
                {"required": ["proof_deliverables"]},
                {"required": ["parameters"]},
                {"required": ["hypotheses"]},
                {"required": ["conclusion_clauses"]},
            ]
        },
        "then": {
            "required": ["claim_kind", "proof_deliverables", "parameters", "hypotheses", "conclusion_clauses"],
            "properties": {
                "claim_kind": _contract_enum_string_schema(THEOREM_CLAIM_KIND_VALUES),
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
_CONTRACT_PAYLOAD_INPUT_SCHEMA["description"] = (
    verification_contract_policy_text()
)
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


def _request_section_required_schema(section_schema: dict[str, object], required_fields: Iterable[str]) -> dict[str, object]:
    required_list = [field for field in required_fields if field]
    schema = dict(section_schema)
    if required_list:
        schema["required"] = required_list
    properties = schema.get("properties")
    if isinstance(properties, dict) and required_list:
        strict_properties = dict(properties)
        for field_name in required_list:
            field_schema = strict_properties.get(field_name)
            if isinstance(field_schema, dict):
                strict_properties[field_name] = _strict_required_schema_fragment(field_schema)
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
                section_schema,
                section_requirements[section_name],
            )
        elif section_name in top_level_required:
            section_schemas[section_name] = _strict_required_schema_fragment(section_schema)
    if "artifact_content" in top_level_required:
        section_schemas["artifact_content"] = _strict_required_schema_fragment(_non_empty_string_or_null_schema())
    if section_schemas:
        schema["properties"] = section_schemas
    return schema


def _run_contract_request_requirement_condition_schema(check_key: str, hint: dict[str, object]) -> dict[str, object] | None:
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
    "`observed`, and `artifact_content` are optional sections, but each check still enforces "
    "its own `schema_required_request_fields` and `schema_required_request_anyof_fields`. "
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


def _contract_check_request_hint(check_key: str, *, contract: ResearchContract | None = None) -> dict[str, object]:
    hint = _CONTRACT_CHECK_REQUEST_HINTS.get(check_key, {})
    check_meta = get_verification_check(check_key)
    binding_targets = list(check_meta.binding_targets) if check_meta is not None else []
    supported_binding_fields = _supported_binding_fields_for_targets(binding_targets)
    request_template = copy.deepcopy(hint.get("request_template", {}))
    if check_key:
        request_template["check_key"] = check_key
    if request_template.get("artifact_content") == "":
        request_template.pop("artifact_content")
    required_request_fields = list(hint.get("required_request_fields", []))
    schema_required_request_fields = list(hint.get("schema_required_request_fields", required_request_fields))
    schema_required_request_anyof_fields = [
        [field for field in group if isinstance(field, str) and field]
        for group in hint.get("schema_required_request_anyof_fields", [])
        if isinstance(group, (list, tuple))
    ]
    optional_request_fields = [
        *supported_binding_fields,
        *[
            field
            for field in hint.get("optional_request_fields", [])
            if field != "binding.*"
        ],
    ]
    enriched_hint = {
        "required_request_fields": required_request_fields,
        "schema_required_request_fields": schema_required_request_fields,
        "schema_required_request_anyof_fields": schema_required_request_anyof_fields,
        "optional_request_fields": [field for field in optional_request_fields if field not in required_request_fields],
        "supported_binding_fields": supported_binding_fields,
        "request_template": request_template,
    }

    def _demote_required_field(field_name: str) -> None:
        enriched_hint["required_request_fields"] = [
            field for field in enriched_hint["required_request_fields"] if field != field_name
        ]
        if field_name not in enriched_hint["optional_request_fields"]:
            enriched_hint["optional_request_fields"].append(field_name)

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
            _demote_required_field("metadata.source_reference_id")

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
                binding_ids = {target: _binding_values_for_target(binding, target) for target in VERIFICATION_BINDING_TARGETS}
                limit_test = _resolve_single_limit_acceptance_test(contract, binding_ids)
            if limit_test is not None and limit_test.pass_condition:
                metadata["expected_behavior"] = limit_test.pass_condition
            _demote_required_field("metadata.regime_label")
            if limit_test is not None and limit_test.pass_condition:
                _demote_required_field("metadata.expected_behavior")

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
            _demote_required_field("metadata.declared_family")
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
            _demote_required_field("metadata.declared_family")
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

    elif check_key in _PROOF_CHECK_KEYS:
        proof_claim_candidates, proof_claim_issue = _proof_claim_candidates(
            contract,
            {},
            binding_supplied=False,
        )
        if proof_claim_issue is None and len(proof_claim_candidates) == 1:
            proof_claim_id = proof_claim_candidates[0]
            claim = _proof_claim_for_id(contract, proof_claim_id)
            if claim is not None:
                binding["claim_ids"] = [proof_claim_id]
                _set_single_binding_value(
                    binding,
                    "deliverable_ids",
                    claim.proof_deliverables or claim.deliverables,
                )
                _set_single_binding_value(
                    binding,
                    "observable_ids",
                    _proof_observable_ids_for_claim(contract, proof_claim_id),
                )
                _apply_single_acceptance_test_binding_if_consistent(
                    binding,
                    contract,
                    _proof_acceptance_tests_for_claim(contract, proof_claim_id, check_key=check_key),
                )
                for field_name, value in _proof_metadata_defaults_for_claim(check_key, claim).items():
                    if value in (None, [], ""):
                        continue
                    metadata[field_name] = copy.deepcopy(value)
                    if field_name == "hypothesis_ids":
                        _demote_required_field("metadata.hypothesis_ids")
                    elif field_name == "theorem_parameter_symbols":
                        _demote_required_field("metadata.theorem_parameter_symbols")
        elif len(_proof_claim_ids(contract)) > 1 or proof_claim_issue is not None:
            if "binding.claim_ids" not in enriched_hint["required_request_fields"]:
                insert_at = 1 if "contract" in enriched_hint["required_request_fields"] else 0
                enriched_hint["required_request_fields"].insert(insert_at, "binding.claim_ids")
            for field_name in ("metadata.hypothesis_ids", "metadata.theorem_parameter_symbols"):
                if field_name in enriched_hint["required_request_fields"]:
                    _demote_required_field(field_name)

    if check_key == "contract.claim_to_proof_alignment":
        observed = request_template.setdefault("observed", {})
        # Keep the starter template runnable without pre-asserting a clause audit outcome.
        if metadata.get("conclusion_clause_ids") and observed.get("uncovered_conclusion_clause_ids") is None:
            metadata["conclusion_clause_ids"] = None

    if check_key in _PROOF_CHECK_KEYS:
        if "contract" not in enriched_hint["required_request_fields"]:
            enriched_hint["required_request_fields"].insert(0, "contract")
        enriched_hint["request_template"]["contract"] = None
        enriched_hint["optional_request_fields"] = [
            field for field in enriched_hint["optional_request_fields"] if field not in enriched_hint["required_request_fields"]
        ]

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

    if check_key in _PROOF_CHECK_KEYS:
        proof_claim_candidates, proof_claim_issue = _proof_claim_candidates(
            contract,
            binding_ids,
            binding_supplied=bool(binding_ids),
        )
        if proof_claim_issue is not None:
            return ["binding.claim_ids"], proof_claim_issue
        if len(proof_claim_candidates) > 1 or (not binding_ids and len(_proof_claim_ids(contract)) > 1):
            return ["binding.claim_ids"], "Ambiguous proof context requires an explicit proof claim binding"

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


def _validate_optional_enum_string(
    value: object,
    *,
    field_name: str,
    allowed_values: Iterable[str],
) -> tuple[str | None, str | None]:
    normalized, error = _validate_optional_string(value, field_name=field_name)
    if error is not None or normalized is None:
        return normalized, error
    allowed = tuple(allowed_values)
    if normalized not in allowed:
        return None, f"{field_name} must be one of {', '.join(allowed)}"
    return normalized, None


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
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            return f"{field_name}[{index}] must be a non-empty string"
        stripped = item.strip()
        if stripped in seen:
            return f"{field_name} must not contain duplicate values"
        seen.add(stripped)
    return None


def _validate_string_list_field(value: object, *, field_name: str, min_items: int | None = None) -> str | None:
    if not isinstance(value, list):
        return f"{field_name} must be a list of strings"
    if min_items is not None and len(value) < min_items:
        return f"{field_name} must include at least one non-empty string"
    return _validate_string_list_members(value, field_name=field_name)


def _validate_optional_string_list(
    value: object,
    *,
    field_name: str,
    min_items: int | None = None,
) -> tuple[list[str] | None, str | None]:
    if value is None:
        return None, None
    error = _validate_string_list_field(value, field_name=field_name, min_items=min_items)
    if error is not None:
        return None, error
    normalized = _normalize_string_list(value)
    return list(normalized) if isinstance(normalized, list) else None, None


def _validate_binding_field_value(value: object, *, field_name: str) -> str | None:
    if not isinstance(value, list):
        return f"{field_name} must be a list of strings"
    error = _validate_string_list_field(value, field_name=field_name, min_items=1)
    if error is not None:
        return error
    return None


def _validate_binding_payload(
    binding: dict[str, object],
    *,
    allowed_targets: Iterable[str],
) -> tuple[dict[str, list[str]] | None, str | None]:
    allowed_targets = tuple(allowed_targets)
    allowed_keys = {f"{target}_ids" for target in allowed_targets}
    unknown_keys = sorted(str(key) for key in binding if key not in allowed_keys)
    if unknown_keys:
        supported = ", ".join(_supported_binding_fields_for_targets(allowed_targets))
        joined = ", ".join(unknown_keys)
        return None, f"binding contains unsupported keys: {joined}; supported keys are {supported}"

    validated: dict[str, list[str]] = {}
    for key in sorted(binding):
        raw = binding[key]
        error = _validate_binding_field_value(raw, field_name=f"binding.{key}")
        if error is not None:
            return None, error
        validated[key] = list(_normalize_string_list(raw))
    return validated, None


def _normalize_contract_metadata(metadata: dict[str, object]) -> tuple[dict[str, object], str | None]:
    normalized = dict(metadata)
    for key in ("regime_label", "expected_behavior", "source_reference_id", "declared_family", "claim_statement"):
        if key in normalized:
            normalized_value, error = _validate_optional_string(normalized[key], field_name=f"metadata.{key}")
            if error is not None:
                return {}, error
            normalized[key] = normalized_value
    for key in (
        "allowed_families",
        "forbidden_families",
    ):
        if key in normalized:
            error = _validate_string_list_field(normalized[key], field_name=f"metadata.{key}")
            if error is not None:
                return {}, error
            normalized[key] = _normalize_string_list(normalized[key])
    for key in (
        "theorem_parameter_symbols",
        "hypothesis_ids",
        "quantifiers",
        "conclusion_clause_ids",
    ):
        if key in normalized:
            normalized_value, error = _validate_optional_string_list(normalized[key], field_name=f"metadata.{key}")
            if error is not None:
                return {}, error
            normalized[key] = normalized_value
    return normalized, None


def _serialize_verification_check_entry(check_entry: dict[str, object]) -> dict[str, object]:
    serialized = dict(check_entry)
    if bool(serialized.get("contract_aware")):
        serialized.update(_contract_check_request_hint(str(serialized.get("check_key") or "")))
    return serialized


def _run_contract_check_description() -> str:
    return (
        "Run a contract-aware verification check from a single structured ``request`` object. "
        "The full request contract lives on the ``request`` input schema itself. "
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
    stripped = value.strip()
    if not stripped:
        return None, _error_result(f"{field_name} must be a non-empty string")
    return stripped, None


def _validate_optional_project_dir(
    value: object,
    *,
    field_name: str,
) -> tuple[Path | None, dict[str, object] | None]:
    """Return an absolute project root path or ``None`` when the field is omitted."""

    if value is None:
        return None, None
    project_dir, error = _validate_string(value, field_name=field_name)
    if error is not None:
        return None, error
    assert project_dir is not None
    resolved = resolve_absolute_project_dir(project_dir)
    if resolved is None:
        return None, _error_result(f"{field_name} must be an absolute path")
    return resolved.resolve(strict=False), None


def _validate_string_list(value: object, *, field_name: str) -> tuple[list[str] | None, dict[str, object] | None]:
    """Return a validated list[str] or an MCP error envelope."""
    if not isinstance(value, list):
        return None, _error_result(f"{field_name} must be a list of strings")
    validated: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            return None, _error_result(f"{field_name}[{index}] must be a string")
        stripped = item.strip()
        if not stripped:
            return None, _error_result(f"{field_name}[{index}] must be a non-empty string")
        validated.append(stripped)
    return validated, None


def _validate_check_identifier(value: object, *, field_name: str) -> tuple[str | None, dict[str, object] | None]:
    """Return an exact contract-check identifier without canonicalizing whitespace."""

    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, _error_result(f"{field_name} must be a string")
    if not value:
        return None, _error_result(f"{field_name} must be a non-empty string")
    if not value.strip():
        return None, _error_result(f"{field_name} must be a non-empty string")
    if value != value.strip():
        return None, _error_result(f"{field_name} must not include leading or trailing whitespace")
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
    seen_keys: set[str] = set()
    for key, item in value.items():
        if not isinstance(key, str):
            return None, _error_result(f"{field_name} keys must be strings")
        stripped_key = key.strip()
        if not stripped_key:
            return None, _error_result(f"{field_name} keys must be non-empty strings")
        if stripped_key in seen_keys:
            return None, _error_result(
                f"{field_name} must not contain duplicate keys after trimming whitespace"
            )
        seen_keys.add(stripped_key)
        if not isinstance(item, str):
            return None, _error_result(f"{field_name}[{key}] must be a string")
        stripped_item = item.strip()
        if not stripped_item:
            return None, _error_result(f"{field_name}[{stripped_key}] must be a non-empty string")
        validated[stripped_key] = stripped_item
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
def run_check(
    check_id: RunCheckIdentifierInput,
    domain: Annotated[str, Field(min_length=1, pattern=r"\S")],
    artifact_content: Annotated[str, Field(min_length=1, pattern=r"\S")],
) -> dict:
    """Run a specific verification check on an artifact.

    Returns the check result with evidence and confidence.
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
                    f"Unknown check_id: {check_id}. "
                    f"Valid identifiers include: {list(_RUN_CHECK_IDENTIFIER_VALUES)}"
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


_VERIFICATION_BINDING_FIELD_NAMES_BY_TARGET = dict(
    zip(VERIFICATION_BINDING_TARGETS, VERIFICATION_BINDING_FIELD_NAMES, strict=True)
)


def _binding_key_labels_for_targets(targets: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    labels: list[str] = []
    for target in targets:
        label = f"{target}_ids"
        if label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return labels


def _supported_binding_fields_for_targets(targets: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for target in targets:
        field_name = _VERIFICATION_BINDING_FIELD_NAMES_BY_TARGET.get(target)
        if field_name is None:
            continue
        field = field_name
        if field in seen:
            continue
        seen.add(field)
        fields.append(field)
    return fields


def _binding_values_for_target(binding: dict[str, object], target: str) -> list[str]:
    raw = binding.get(f"{target}_ids")
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                values.append(stripped)
    return _unique_strings(values)


def _binding_values_by_field_for_target(binding: dict[str, object], target: str) -> dict[str, list[str]]:
    values_by_field: dict[str, list[str]] = {}
    key = f"{target}_ids"
    raw = binding.get(key)
    if not isinstance(raw, list):
        return values_by_field
    values: list[str] = []
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

    if check_key in {"contract.fit_family_mismatch", "contract.estimator_family_mismatch"}:
        declared_family = _normalize_optional_scalar_str(metadata.get("declared_family"))
        if declared_family:
            return [declared_family]
        selected_family = _normalize_optional_scalar_str(metadata.get("selected_family"))
        if selected_family:
            return [selected_family]

    if check_key in _PROOF_CHECK_KEYS:
        candidates, issue = _proof_claim_candidates(
            contract,
            binding_ids,
            binding_supplied=binding_supplied,
        )
        if issue is None and len(candidates) == 1:
            claim = _proof_claim_for_id(contract, candidates[0])
            if claim is not None:
                impacts = [claim.id, *claim.proof_deliverables, *binding_ids.get("acceptance_test", [])]
                proof_observable_ids = _proof_observable_ids_for_claim(contract, claim.id)
                if len(proof_observable_ids) == 1:
                    impacts.extend(proof_observable_ids)
                return _unique_strings(impacts)
        impacts = [
            *binding_ids.get("observable", []),
            *binding_ids.get("claim", []),
            *binding_ids.get("acceptance_test", []),
            *binding_ids.get("deliverable", []),
        ]
        return _unique_strings(impacts)

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
        for deliverable_id in claim.proof_deliverables:
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


def _proof_claim_ids(contract: ResearchContract) -> list[str]:
    observables_by_id = {observable.id: observable for observable in contract.observables}
    acceptance_test_kind_by_id = {test.id: test.kind for test in contract.acceptance_tests}
    proof_claim_ids: list[str] = []
    for claim in contract.claims:
        if claim.claim_kind in _PROOF_CLAIM_KIND_VALUES:
            proof_claim_ids.append(claim.id)
            continue
        if statement_looks_theorem_like(claim.statement):
            proof_claim_ids.append(claim.id)
            continue
        if any(
            (
                claim.parameters,
                claim.hypotheses,
                claim.quantifiers,
                claim.conclusion_clauses,
                claim.proof_deliverables,
            )
        ):
            proof_claim_ids.append(claim.id)
            continue
        if any(
            observables_by_id.get(observable_id) is not None
            and observables_by_id[observable_id].kind == "proof_obligation"
            for observable_id in claim.observables
        ):
            proof_claim_ids.append(claim.id)
            continue
        if any(
            acceptance_test_kind_by_id.get(test_id) in _PROOF_ACCEPTANCE_TEST_KIND_VALUES
            for test_id in claim.acceptance_tests
        ):
            proof_claim_ids.append(claim.id)
    return _unique_strings(proof_claim_ids)


def _proof_claim_for_id(contract: ResearchContract, claim_id: str) -> object | None:
    return next((claim for claim in contract.claims if claim.id == claim_id), None)


def _proof_observable_ids_for_claim(contract: ResearchContract, claim_id: str) -> list[str]:
    claim = _proof_claim_for_id(contract, claim_id)
    if claim is None:
        return []
    observables_by_id = {observable.id: observable for observable in contract.observables}
    return [
        observable_id
        for observable_id in claim.observables
        if observables_by_id.get(observable_id) is not None
        and observables_by_id[observable_id].kind == "proof_obligation"
    ]


def _proof_acceptance_tests_for_claim(
    contract: ResearchContract,
    claim_id: str,
    *,
    check_key: str,
) -> list[object]:
    claim = _proof_claim_for_id(contract, claim_id)
    if claim is None:
        return []
    tests_by_id = {test.id: test for test in contract.acceptance_tests}
    claim_tests = [tests_by_id[test_id] for test_id in claim.acceptance_tests if test_id in tests_by_id]
    expected_kind = _PROOF_CHECK_TO_ACCEPTANCE_KIND.get(check_key)
    if expected_kind is None:
        return []
    return [test for test in claim_tests if test.kind == expected_kind]


def _proof_claim_candidates(
    contract: ResearchContract,
    binding_ids: dict[str, list[str]],
    *,
    binding_supplied: bool,
) -> tuple[list[str], str | None]:
    proof_claim_id_set = set(_proof_claim_ids(contract))
    if not proof_claim_id_set:
        return [], None

    claims_by_id = {claim.id: claim for claim in contract.claims}
    tests_by_id = {test.id: test for test in contract.acceptance_tests}
    claims_by_deliverable = _claim_ids_by_deliverable(contract)

    context_candidates: dict[str, list[str]] = {}

    claim_candidates = [claim_id for claim_id in binding_ids.get("claim", []) if claim_id in proof_claim_id_set]
    if claim_candidates:
        context_candidates["claim"] = _unique_strings(claim_candidates)

    deliverable_candidates = [
        claim_id
        for deliverable_id in binding_ids.get("deliverable", [])
        for claim_id in claims_by_deliverable.get(deliverable_id, [])
        if claim_id in proof_claim_id_set
    ]
    if deliverable_candidates:
        context_candidates["deliverable"] = _unique_strings(deliverable_candidates)

    acceptance_test_candidates: list[str] = []
    for acceptance_test_id in binding_ids.get("acceptance_test", []):
        test = tests_by_id.get(acceptance_test_id)
        if test is None:
            continue
        acceptance_test_candidates.extend(
            claim_id
            for claim_id in _claim_ids_for_subject(
                test.subject,
                claims_by_id=claims_by_id,
                claims_by_deliverable=claims_by_deliverable,
            )
            if claim_id in proof_claim_id_set
        )
    if acceptance_test_candidates:
        context_candidates["acceptance_test"] = _unique_strings(acceptance_test_candidates)

    observable_candidates = [
        claim.id
        for claim in contract.claims
        if claim.id in proof_claim_id_set and set(claim.observables).intersection(binding_ids.get("observable", []))
    ]
    if observable_candidates:
        context_candidates["observable"] = _unique_strings(observable_candidates)

    candidates, issue = _resolve_binding_candidates(
        label="proof claim candidates",
        context_candidates=context_candidates,
    )
    if candidates or issue:
        return candidates, issue

    if binding_supplied and any(binding_ids.get(target) for target in ("observable", "claim", "deliverable", "acceptance_test")):
        return [], "binding does not resolve to a proof-bearing claim"

    if not binding_supplied and not binding_ids and len(proof_claim_id_set) == 1:
        return list(proof_claim_id_set), None

    return [], None


def _proof_metadata_defaults_for_claim(check_key: str, claim: object) -> dict[str, object]:
    if check_key == "contract.proof_hypothesis_coverage":
        return {
            "hypothesis_ids": [
                hypothesis.id
                for hypothesis in claim.hypotheses
                if getattr(hypothesis, "required_in_proof", True)
            ]
        }
    if check_key == "contract.proof_parameter_coverage":
        return {
            "theorem_parameter_symbols": [
                parameter.symbol
                for parameter in claim.parameters
                if getattr(parameter, "required_in_proof", True)
            ]
        }
    if check_key == "contract.proof_quantifier_domain":
        return {
            "quantifiers": list(claim.quantifiers),
        }
    if check_key == "contract.claim_to_proof_alignment":
        return {
            "claim_statement": claim.statement,
            "conclusion_clause_ids": [clause.id for clause in claim.conclusion_clauses],
        }
    if check_key == "contract.counterexample_search":
        return {
            "claim_statement": claim.statement,
        }
    return {}


def _normalized_unique_strings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        normalized.append(stripped)
    return normalized


def _proof_metadata_contract_mismatch_errors(
    check_key: str,
    *,
    contract: ResearchContract | None,
    proof_claim_id: str | None,
    supplied_metadata: dict[str, object],
) -> list[str]:
    if contract is None or proof_claim_id is None:
        return []
    claim = _proof_claim_for_id(contract, proof_claim_id)
    if claim is None:
        return []
    defaults = _proof_metadata_defaults_for_claim(check_key, claim)
    errors: list[str] = []
    for field_name, expected_value in defaults.items():
        if field_name not in supplied_metadata:
            continue
        supplied_value = supplied_metadata.get(field_name)
        if supplied_value is None:
            continue
        if isinstance(expected_value, list):
            if set(_normalized_unique_strings(supplied_value)) != set(_normalized_unique_strings(expected_value)):
                errors.append(
                    f"metadata.{field_name} does not match the resolved theorem inventory for {proof_claim_id}"
                )
        elif isinstance(expected_value, str):
            if not isinstance(supplied_value, str) or supplied_value.strip() != expected_value:
                errors.append(
                    f"metadata.{field_name} does not match the resolved theorem inventory for {proof_claim_id}"
                )
    return errors


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
        return _unique_strings([*claim.deliverables, *claim.proof_deliverables])
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


def _contract_error_path(error: str) -> str | None:
    match = _CONTRACT_ERROR_PATH_RE.match(error)
    if match is None:
        return None
    return match.group(1)


def _contract_path_tokens(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", path):
        tokens.append(int(token) if token.isdigit() else token)
    return tokens


def _contract_value_at_path(contract_raw: dict[str, object], path: str) -> object | None:
    current: object = contract_raw
    for token in _contract_path_tokens(path):
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return None
            current = current[token]
            continue
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def _normalize_contract_parse_error(error: str, *, contract_raw: dict[str, object]) -> str:
    if error == "schema_version: Input should be 1":
        return "schema_version must be 1"

    path = _contract_error_path(error)
    if path is None:
        return error

    tokens = _contract_path_tokens(path)
    if not tokens or not isinstance(tokens[-1], int):
        return error

    value = _contract_value_at_path(contract_raw, path)
    if value is None:
        parent = ".".join(str(token) for token in tokens[:-1])
        return f"{parent}[{tokens[-1]}] must be a non-empty string"
    if isinstance(value, str) and value.strip() and " is a duplicate" in error:
        return error
    if isinstance(value, str) and value.strip() and "must not be blank" not in error and ": Input should" not in error:
        return error
    if not isinstance(value, str):
        return error

    parent = ".".join(str(token) for token in tokens[:-1])
    return f"{parent}[{tokens[-1]}] must be a non-empty string"


def _contract_error_sort_key(error: str) -> tuple[object, ...]:
    path = _contract_error_path(error)
    if path is None:
        return (1, error)
    tokens = _contract_path_tokens(path)
    if not tokens or not isinstance(tokens[0], str):
        return (1, error)

    order = _CONTRACT_ERROR_FIELD_ORDER.get(tokens[0], len(_CONTRACT_ERROR_FIELD_ORDER))
    parts: list[tuple[int, object]] = []
    for token in tokens[1:]:
        if isinstance(token, int):
            parts.append((0, token))
        else:
            parts.append((1, token))
    return (0, order, tuple(parts), error)


def _contract_payload_error(errors: list[str]) -> dict[str, object]:
    details = sorted(
        dict.fromkeys(errors),
        key=_contract_error_sort_key,
    )
    if not details:
        return _error_result("Invalid contract payload")
    message = f"Invalid contract payload: {_summarize_contract_salvage_errors(details)}"
    if len(details) == 1:
        return _error_result(message)
    return stable_mcp_response({"contract_error_details": details}, error=message)


def _is_authoritative_contract_parse_error(error: str) -> bool:
    return is_authoritative_project_contract_schema_finding(error)


def _is_defaultable_singleton_contract_error(error: str) -> bool:
    del error
    return False


def _recoverable_collection_list_shape_error(error: str, *, contract_raw: dict[str, object]) -> bool:
    if " must be a list, not str" not in error:
        return False
    path = error.removesuffix(" must be a list, not str")
    tokens = _contract_path_tokens(path)
    raw_value = _contract_value_at_path(contract_raw, path)
    if not isinstance(raw_value, str) or not raw_value.strip():
        return False

    if len(tokens) == 3:
        collection_name, index, field_name = tokens
        if (
            not isinstance(collection_name, str)
            or not isinstance(index, int)
            or not isinstance(field_name, str)
            or field_name not in PROJECT_CONTRACT_COLLECTION_LIST_FIELDS.get(collection_name, ())
        ):
            return False
        if collection_name == "references" and field_name == "required_actions":
            return raw_value.strip().casefold() in _REFERENCE_ACTIONS
        return True

    if len(tokens) == 5:
        collection_name, index, nested_collection_name, nested_index, field_name = tokens
        if (
            collection_name,
            nested_collection_name,
            field_name,
        ) not in {
            ("claims", "parameters", "aliases"),
            ("claims", "hypotheses", "symbols"),
        }:
            return False
        return isinstance(index, int) and isinstance(nested_index, int)

    return False


def _recoverable_mapping_list_shape_error(error: str, *, contract_raw: dict[str, object]) -> bool:
    if " must be a list, not str" not in error:
        return False
    path = error.removesuffix(" must be a list, not str")
    tokens = _contract_path_tokens(path)
    if len(tokens) != 2:
        return False
    section_name, field_name = tokens
    if (
        not isinstance(section_name, str)
        or not isinstance(field_name, str)
        or field_name not in PROJECT_CONTRACT_MAPPING_LIST_FIELDS.get(section_name, ())
    ):
        return False

    raw_value = _contract_value_at_path(contract_raw, path)
    return isinstance(raw_value, str) and bool(raw_value.strip())


def _is_case_drift_contract_parse_error(error: str) -> bool:
    recoverable_with_case_drift, _ = split_project_contract_schema_findings(
        [error],
        allow_case_drift_recovery=True,
    )
    if not recoverable_with_case_drift:
        return False
    recoverable_without_case_drift, _ = split_project_contract_schema_findings(
        [error],
        allow_case_drift_recovery=False,
    )
    return not recoverable_without_case_drift


def _is_recoverable_contract_parse_error(error: str, *, contract_raw: dict[str, object]) -> bool:
    return any(
        (
            _recoverable_collection_list_shape_error(error, contract_raw=contract_raw),
            _recoverable_mapping_list_shape_error(error, contract_raw=contract_raw),
            _is_case_drift_contract_parse_error(error),
            _is_defaultable_singleton_contract_error(error),
        )
    )


def _validate_contract_integrity(
    contract: ResearchContract,
    *,
    contract_raw: dict[str, object],
    project_root: Path | None = None,
) -> dict[str, object] | None:
    """Reject plan-contract semantic mismatches after structural validation."""

    errors: list[str] = []
    if "context_intake" not in contract_raw:
        errors.append("missing context_intake")
    elif not contract_has_explicit_context_intake(contract, project_root=project_root):
        errors.append("context_intake must not be empty")
    for error in collect_plan_contract_integrity_errors(contract, project_root=project_root):
        if error not in errors:
            errors.append(error)
    if not errors:
        return None
    return _contract_payload_error(errors)


def _parse_contract_payload(
    contract_raw: dict[str, object],
    *,
    project_root: Path | None = None,
) -> tuple[ResearchContract | None, list[str], dict | None]:
    strict_result = parse_project_contract_data_strict(contract_raw)
    salvage_result = parse_project_contract_data_salvage(contract_raw)
    normalized_strict_errors = [
        _normalize_contract_parse_error(error, contract_raw=contract_raw)
        for error in strict_result.errors
    ]
    normalized_salvage_recoverable_errors = [
        _normalize_contract_parse_error(error, contract_raw=contract_raw)
        for error in salvage_result.recoverable_errors
    ]
    nonblocking_errors = sorted(
        dict.fromkeys(
            error
            for error in [*normalized_strict_errors, *normalized_salvage_recoverable_errors]
            if _is_recoverable_contract_parse_error(error, contract_raw=contract_raw)
        ),
        key=_contract_error_sort_key,
    )
    recoverable_errors = list(nonblocking_errors)
    authoritative_errors = [
        error
        for error in normalized_strict_errors
        if _is_authoritative_contract_parse_error(error)
    ]
    if authoritative_errors:
        return None, [], _contract_payload_error(authoritative_errors)
    if strict_result.contract is None:
        blocking = [
            error
            for error in [*normalized_strict_errors, *normalized_salvage_recoverable_errors]
            if error not in nonblocking_errors
        ]
        if blocking:
            return None, [], _contract_payload_error(blocking)
        contract = salvage_result.contract
        if contract is None or salvage_result.blocking_errors:
            salvage_errors = [
                _normalize_contract_parse_error(error, contract_raw=contract_raw)
                for error in salvage_result.blocking_errors
            ]
            combined_errors = salvage_errors or normalized_strict_errors
            return None, [], _contract_payload_error(combined_errors)
    else:
        contract = strict_result.contract
        blocking = [error for error in normalized_salvage_recoverable_errors if error not in nonblocking_errors]
        if blocking:
            return None, [], _contract_payload_error(blocking)
        if salvage_result.blocking_errors:
            salvage_errors = [
                _normalize_contract_parse_error(error, contract_raw=contract_raw)
                for error in salvage_result.blocking_errors
            ]
            return None, [], _contract_payload_error(salvage_errors)
    integrity_error = _validate_contract_integrity(
        contract,
        contract_raw=contract_raw,
        project_root=project_root,
    )
    if integrity_error is not None:
        return None, [], integrity_error
    return contract, recoverable_errors, None


def _contract_salvage_requires_repair(contract_salvage_errors: list[str]) -> bool:
    """Return whether salvage findings still require repair before proof checks can run."""

    return any(is_repair_relevant_project_contract_schema_finding(error) for error in contract_salvage_errors)


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

    if check_key in _PROOF_CHECK_KEYS:
        proof_claim_candidates, proof_claim_issue = _proof_claim_candidates(
            contract,
            binding_ids,
            binding_supplied=binding_supplied,
        )
        if proof_claim_issue is None and len(proof_claim_candidates) == 1:
            claim = _proof_claim_for_id(contract, proof_claim_candidates[0])
            if claim is not None:
                for field_name, value in _proof_metadata_defaults_for_claim(check_key, claim).items():
                    if field_name not in enriched or enriched.get(field_name) in (None, [], ""):
                        enriched[field_name] = copy.deepcopy(value)

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

    binding_ids = {target: _binding_values_for_target(candidate_binding, target) for target in VERIFICATION_BINDING_TARGETS}
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


@mcp.tool(description=_run_contract_check_description())
def run_contract_check(request: RunContractCheckPayload, project_dir: OptionalAbsoluteProjectDirInput = None) -> dict:
    """Run a contract-aware verification check."""

    with gpd_span("mcp.verification.run_contract_check"):
        try:
            request, error = _payload_mapping(request, field_name="request")
            if error is not None:
                return error
            project_root, error = _validate_optional_project_dir(project_dir, field_name="project_dir")
            if error is not None:
                return error
            request_key_error = _validate_run_contract_check_request_keys(request)
            if request_key_error is not None:
                return _error_result(request_key_error)
            check_key_value, error = _validate_check_identifier(request.get("check_key"), field_name="check_key")
            if error is not None:
                return error
            if not isinstance(check_key_value, str) or not check_key_value:
                return _error_result("Missing check_key")
            check_meta = get_verification_check(check_key_value)
            if check_meta is None:
                return _error_result(f"Unknown contract check: {check_key_value}")

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
                contract, contract_salvage_errors, error = _parse_contract_payload(
                    contract_raw,
                    project_root=project_root,
                )
                if error is not None:
                    return error

            binding = binding_raw or {}
            binding, binding_error = _validate_binding_payload(binding, allowed_targets=check_meta.binding_targets)
            if binding_error is not None:
                return _error_result(binding_error)
            binding = binding or {}
            binding_supplied = bool(binding_raw)
            metadata, metadata_error = _normalize_contract_metadata(metadata_raw or {})
            if metadata_error is not None:
                return _error_result(metadata_error)
            supplied_metadata = dict(metadata)
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
            proof_claim_id: str | None = None
            if contract is not None and check_meta.check_key in _PROOF_CHECK_KEYS:
                proof_claim_candidates, proof_claim_issue = _proof_claim_candidates(
                    contract,
                    binding_ids,
                    binding_supplied=binding_supplied,
                )
                if proof_claim_issue is None and len(proof_claim_candidates) == 1:
                    proof_claim_id = proof_claim_candidates[0]
            if check_meta.check_key in _PROOF_CHECK_KEYS and contract is None:
                return _error_result("Proof checks require an authoritative contract payload")
            if check_meta.check_key in _PROOF_CHECK_KEYS and _contract_salvage_requires_repair(contract_salvage_errors):
                return _error_result("Proof checks require an authoritative contract payload")
            if check_meta.check_key in _PROOF_CHECK_KEYS:
                proof_metadata_errors = _proof_metadata_contract_mismatch_errors(
                    check_meta.check_key,
                    contract=contract,
                    proof_claim_id=proof_claim_id,
                    supplied_metadata=supplied_metadata,
                )
                if proof_metadata_errors:
                    return _error_result("; ".join(proof_metadata_errors))

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

            elif check_meta.check_key == "contract.proof_hypothesis_coverage":
                declared_hypothesis_ids, error_message = _validate_optional_string_list(
                    metadata.get("hypothesis_ids"),
                    field_name="metadata.hypothesis_ids",
                    min_items=1,
                )
                if error_message is not None:
                    return _error_result(error_message)
                covered_hypothesis_ids, error_message = _validate_optional_string_list(
                    observed.get("covered_hypothesis_ids"),
                    field_name="observed.covered_hypothesis_ids",
                    min_items=1,
                )
                if error_message is not None:
                    return _error_result(error_message)
                explicit_missing_hypothesis_ids, error_message = _validate_optional_string_list(
                    observed.get("missing_hypothesis_ids"),
                    field_name="observed.missing_hypothesis_ids",
                )
                if error_message is not None:
                    return _error_result(error_message)
                declared = set(declared_hypothesis_ids or [])
                covered = set(covered_hypothesis_ids or [])
                explicit_missing = set(explicit_missing_hypothesis_ids or [])
                missing = set(explicit_missing)
                if declared and covered_hypothesis_ids is not None:
                    missing.update(declared - covered)
                metrics.update(
                    {
                        "proof_claim_id": proof_claim_id,
                        "declared_hypothesis_ids": sorted(declared),
                        "covered_hypothesis_ids": sorted(covered),
                        "missing_hypothesis_ids": sorted(missing),
                    }
                )
                evidence_directness = "direct"
                if not declared:
                    missing_inputs.append("metadata.hypothesis_ids")
                if covered_hypothesis_ids is None:
                    missing_inputs.append("observed.covered_hypothesis_ids")
                if explicit_missing.intersection(covered):
                    automated_issues.append("Proof hypothesis coverage marks the same hypothesis as both covered and missing")
                    status = "insufficient_evidence"
                elif missing and not missing_inputs:
                    automated_issues.append("Proof audit reports missing hypotheses")
                    status = "fail"
                elif declared and not missing_inputs:
                    status = "pass"

            elif check_meta.check_key == "contract.proof_parameter_coverage":
                declared_parameter_symbols, error_message = _validate_optional_string_list(
                    metadata.get("theorem_parameter_symbols"),
                    field_name="metadata.theorem_parameter_symbols",
                    min_items=1,
                )
                if error_message is not None:
                    return _error_result(error_message)
                covered_parameter_symbols, error_message = _validate_optional_string_list(
                    observed.get("covered_parameter_symbols"),
                    field_name="observed.covered_parameter_symbols",
                    min_items=1,
                )
                if error_message is not None:
                    return _error_result(error_message)
                explicit_missing_parameter_symbols, error_message = _validate_optional_string_list(
                    observed.get("missing_parameter_symbols"),
                    field_name="observed.missing_parameter_symbols",
                )
                if error_message is not None:
                    return _error_result(error_message)
                declared_symbols = list(declared_parameter_symbols or [])
                covered = set(covered_parameter_symbols or [])
                explicit_missing = set(explicit_missing_parameter_symbols or [])
                alias_groups: dict[str, set[str]] = {symbol: {symbol} for symbol in declared_symbols}
                if proof_claim_id is not None and contract is not None:
                    claim = _proof_claim_for_id(contract, proof_claim_id)
                    if claim is not None:
                        alias_groups = {
                            parameter.symbol: {parameter.symbol, *parameter.aliases}
                            for parameter in claim.parameters
                            if getattr(parameter, "required_in_proof", True)
                        } or alias_groups
                missing: set[str] = set()
                for symbol in declared_symbols:
                    aliases = alias_groups.get(symbol, {symbol})
                    if not covered.intersection(aliases):
                        missing.add(symbol)
                for symbol in explicit_missing:
                    canonical = next(
                        (candidate for candidate, aliases in alias_groups.items() if symbol in aliases),
                        symbol,
                    )
                    if canonical in declared_symbols:
                        missing.add(canonical)
                metrics.update(
                    {
                        "proof_claim_id": proof_claim_id,
                        "declared_parameter_symbols": declared_symbols,
                        "covered_parameter_symbols": sorted(covered),
                        "missing_parameter_symbols": sorted(missing),
                    }
                )
                evidence_directness = "direct"
                if not declared_symbols:
                    missing_inputs.append("metadata.theorem_parameter_symbols")
                if covered_parameter_symbols is None:
                    missing_inputs.append("observed.covered_parameter_symbols")
                if explicit_missing.intersection(covered):
                    automated_issues.append("Proof parameter coverage marks the same parameter as both covered and missing")
                    status = "insufficient_evidence"
                elif missing and not missing_inputs:
                    automated_issues.append("Proof audit reports missing theorem parameters")
                    status = "fail"
                elif declared_symbols and not missing_inputs:
                    status = "pass"

            elif check_meta.check_key == "contract.proof_quantifier_domain":
                quantifiers, error_message = _validate_optional_string_list(
                    metadata.get("quantifiers"),
                    field_name="metadata.quantifiers",
                )
                if error_message is not None:
                    return _error_result(error_message)
                uncovered_quantifiers, error_message = _validate_optional_string_list(
                    observed.get("uncovered_quantifiers"),
                    field_name="observed.uncovered_quantifiers",
                )
                if error_message is not None:
                    return _error_result(error_message)
                quantifier_status, error_message = _validate_optional_enum_string(
                    observed.get("quantifier_status"),
                    field_name="observed.quantifier_status",
                    allowed_values=_QUANTIFIER_STATUS_VALUES,
                )
                if error_message is not None:
                    return _error_result(error_message)
                scope_status, error_message = _validate_optional_enum_string(
                    observed.get("scope_status"),
                    field_name="observed.scope_status",
                    allowed_values=_SCOPE_STATUS_VALUES,
                )
                if error_message is not None:
                    return _error_result(error_message)
                metrics.update(
                    {
                        "proof_claim_id": proof_claim_id,
                        "declared_quantifiers": sorted(quantifiers or []),
                        "uncovered_quantifiers": sorted(uncovered_quantifiers or []),
                        "quantifier_status": quantifier_status,
                        "scope_status": scope_status,
                    }
                )
                evidence_directness = "direct"
                if quantifier_status is None:
                    missing_inputs.append("observed.quantifier_status")
                if scope_status is None:
                    missing_inputs.append("observed.scope_status")
                if (
                    quantifier_status == "matched"
                    and scope_status == "matched"
                    and not (uncovered_quantifiers or [])
                    and not missing_inputs
                ):
                    status = "pass"
                elif (
                    quantifier_status in {"narrowed", "mismatched"}
                    or scope_status in {"narrower_than_claim", "mismatched"}
                    or bool(uncovered_quantifiers)
                ) and not missing_inputs:
                    automated_issues.append("Proof audit reports narrowed or uncovered quantifiers/domains")
                    status = "fail"
                elif not missing_inputs and (quantifier_status == "unclear" or scope_status == "unclear"):
                    automated_issues.append("Proof audit could not establish quantifier/domain fidelity decisively")
                    status = "warning"

            elif check_meta.check_key == "contract.claim_to_proof_alignment":
                supplied_conclusion_clause_ids = _normalized_unique_strings(supplied_metadata.get("conclusion_clause_ids"))
                claim_statement, error_message = _validate_optional_string(
                    metadata.get("claim_statement"),
                    field_name="metadata.claim_statement",
                )
                if error_message is not None:
                    return _error_result(error_message)
                conclusion_clause_ids, error_message = _validate_optional_string_list(
                    metadata.get("conclusion_clause_ids"),
                    field_name="metadata.conclusion_clause_ids",
                    min_items=1,
                )
                if error_message is not None:
                    return _error_result(error_message)
                uncovered_conclusion_clause_ids, error_message = _validate_optional_string_list(
                    observed.get("uncovered_conclusion_clause_ids"),
                    field_name="observed.uncovered_conclusion_clause_ids",
                    min_items=1,
                )
                if error_message is not None:
                    return _error_result(error_message)
                scope_status, error_message = _validate_optional_enum_string(
                    observed.get("scope_status"),
                    field_name="observed.scope_status",
                    allowed_values=_SCOPE_STATUS_VALUES,
                )
                if error_message is not None:
                    return _error_result(error_message)
                metrics.update(
                    {
                        "proof_claim_id": proof_claim_id,
                        "claim_statement": claim_statement,
                        "declared_conclusion_clause_ids": sorted(conclusion_clause_ids or []),
                        "uncovered_conclusion_clause_ids": sorted(uncovered_conclusion_clause_ids or []),
                        "scope_status": scope_status,
                    }
                )
                evidence_directness = "direct"
                if not claim_statement and not conclusion_clause_ids:
                    missing_inputs.append("metadata.claim_statement")
                if scope_status is None:
                    missing_inputs.append("observed.scope_status")
                if supplied_conclusion_clause_ids and uncovered_conclusion_clause_ids is None:
                    missing_inputs.append("observed.uncovered_conclusion_clause_ids")
                if scope_status == "matched" and not (uncovered_conclusion_clause_ids or []) and not missing_inputs:
                    status = "pass"
                elif (
                    scope_status in {"narrower_than_claim", "mismatched"}
                    or bool(uncovered_conclusion_clause_ids)
                ) and not missing_inputs:
                    automated_issues.append("Proof establishes a narrower claim or leaves conclusion clauses uncovered")
                    status = "fail"
                elif not missing_inputs and scope_status == "unclear":
                    automated_issues.append("Proof-to-claim alignment remains unclear")
                    status = "warning"

            elif check_meta.check_key == "contract.counterexample_search":
                counterexample_status, error_message = _validate_optional_enum_string(
                    observed.get("counterexample_status"),
                    field_name="observed.counterexample_status",
                    allowed_values=_COUNTEREXAMPLE_STATUS_VALUES,
                )
                if error_message is not None:
                    return _error_result(error_message)
                claim_statement, error_message = _validate_optional_string(
                    metadata.get("claim_statement"),
                    field_name="metadata.claim_statement",
                )
                if error_message is not None:
                    return _error_result(error_message)
                metrics["proof_claim_id"] = proof_claim_id
                metrics["claim_statement"] = claim_statement
                metrics["counterexample_status"] = counterexample_status
                evidence_directness = "direct"
                if counterexample_status is None:
                    missing_inputs.append("observed.counterexample_status")
                elif counterexample_status == "none_found":
                    status = "pass"
                elif counterexample_status in {"counterexample_found", "narrowed_claim"}:
                    automated_issues.append("Adversarial proof review found a counterexample or narrowed claim")
                    status = "fail"
                else:
                    automated_issues.append("No adversarial counterexample attempt was recorded")
                    status = "insufficient_evidence"

            resolved_subject: str | None = None
            if check_meta.check_key == "contract.benchmark_reproduction":
                resolved_subject = source_reference_id
            elif check_meta.check_key == "contract.limit_recovery":
                resolved_subject = regime_label
            elif check_meta.check_key in _PROOF_CHECK_KEYS:
                resolved_subject = proof_claim_id

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


@mcp.tool(description=_suggest_contract_checks_description())
def suggest_contract_checks(
    contract: SuggestContractPayload,
    active_checks: StringListPayload = None,
    project_dir: OptionalAbsoluteProjectDirInput = None,
) -> dict:
    """Suggest contract-aware checks from a schema-validated contract."""

    with gpd_span("mcp.verification.suggest_contract_checks"):
        try:
            contract, error = _payload_mapping(contract, field_name="contract")
            if error is not None:
                return error
            project_root, error = _validate_optional_project_dir(project_dir, field_name="project_dir")
            if error is not None:
                return error
            if active_checks is not None:
                active_checks, error = _validate_string_list(active_checks, field_name="active_checks")
                if error is not None:
                    return error
                active_checks = _normalize_active_checks(active_checks)
            parsed, contract_salvage_errors, error = _parse_contract_payload(
                contract,
                project_root=project_root,
            )
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
                        "check": meta.check_key,
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

            proof_bearing_claims = _proof_claim_ids(parsed)
            proof_test_kinds = {test.kind for test in parsed.acceptance_tests}
            if proof_bearing_claims or "proof_hypothesis_coverage" in proof_test_kinds:
                _add(
                    "contract.proof_hypothesis_coverage",
                    "Proof-bearing claims require explicit hypothesis coverage",
                )
            if proof_bearing_claims or "proof_parameter_coverage" in proof_test_kinds:
                _add(
                    "contract.proof_parameter_coverage",
                    "Proof-bearing claims require parameter/symbol coverage",
                )
            if proof_bearing_claims or "proof_quantifier_domain" in proof_test_kinds:
                _add(
                    "contract.proof_quantifier_domain",
                    "Proof-bearing claims require quantifier and domain fidelity checks",
                )
            if proof_bearing_claims or "claim_to_proof_alignment" in proof_test_kinds:
                _add(
                    "contract.claim_to_proof_alignment",
                    "Proof-bearing claims require theorem-to-proof alignment checks",
                )
            if proof_bearing_claims or "counterexample_search" in proof_test_kinds:
                _add(
                    "contract.counterexample_search",
                    "Proof-bearing claims require adversarial counterexample attempts",
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
                return _error_result(exc)
            return _error_result(exc)


@mcp.tool()
def get_checklist(domain: Annotated[str, Field(min_length=1, pattern=r"\S")]) -> dict:
    """Return the domain-specific verification checklist.

    Provides the complete list of checks recommended for a physics domain,
    including which live verifier-registry checks (currently 5.1-5.24) each maps to.
    """
    if not isinstance(domain, str) or not domain.strip():
        return _error_result("domain must be a non-empty string")

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
def get_bundle_checklist(bundle_ids: BundleIdListInput) -> dict:
    """Return additive verifier checklist extensions for selected protocol bundles."""
    validated_bundle_ids, error = _validate_string_list(bundle_ids, field_name="bundle_ids")
    if error is not None:
        return error
    normalized_bundle_ids = _unique_strings(validated_bundle_ids or [])

    with gpd_span("mcp.verification.bundle_checklist", bundle_count=len(normalized_bundle_ids)):
        try:
            bundles: list[dict[str, object]] = []
            resolved_bundles: list[ResolvedProtocolBundle] = []
            checklist: list[dict[str, object]] = []
            missing_bundle_ids: list[str] = []

            for bundle_id in normalized_bundle_ids:
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


tighten_registered_tool_contracts(mcp)


if __name__ == "__main__":
    main()
