"""Validation helpers for contract-backed workflow gates."""

from __future__ import annotations

import copy
import re
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, get_args, get_origin

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
    CONTRACT_ACCEPTANCE_AUTOMATION_VALUES,
    CONTRACT_ACCEPTANCE_TEST_KIND_VALUES,
    CONTRACT_CLAIM_KIND_VALUES,
    CONTRACT_DELIVERABLE_KIND_VALUES,
    CONTRACT_LINK_RELATION_VALUES,
    CONTRACT_OBSERVABLE_KIND_VALUES,
    CONTRACT_REFERENCE_ACTION_VALUES,
    CONTRACT_REFERENCE_KIND_VALUES,
    CONTRACT_REFERENCE_ROLE_VALUES,
    PROJECT_CONTRACT_COLLECTION_LIST_FIELDS,
    PROJECT_CONTRACT_MAPPING_LIST_FIELDS,
    PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS,
    ContractAcceptanceTest,
    ContractApproachPolicy,
    ContractClaim,
    ContractContextIntake,
    ContractDeliverable,
    ContractForbiddenProxy,
    ContractLink,
    ContractObservable,
    ContractReference,
    ContractScope,
    ContractUncertaintyMarkers,
    ResearchContract,
    collect_contract_integrity_errors,
    collect_proof_bearing_claim_integrity_errors,
    has_concrete_grounding_entries,
    has_concrete_must_surface_reference,
    is_concrete_reference_locator,
    is_context_intake_locator_grounding,
    is_placeholder_only_guidance_text,
    is_project_artifact_path,
    parse_project_contract_data_salvage,
    parse_project_contract_data_strict,
)
from gpd.core.utils import dedupe_preserve_order

__all__ = [
    "ProjectContractValidationResult",
    "is_authoritative_project_contract_schema_finding",
    "is_repair_relevant_project_contract_schema_finding",
    "salvage_project_contract",
    "split_project_contract_schema_findings",
    "validate_project_contract",
]


@dataclass(frozen=True)
class _SchemaFindingMetadata:
    loc: tuple[str | int, ...]
    msg: str
    error_type: str | None
    ctx: dict[str, object]
    input_value_type: str | None


def _schema_finding_metadata_from_error(error: dict[str, object]) -> _SchemaFindingMetadata:
    input_value = error.get("input")
    return _SchemaFindingMetadata(
        loc=tuple(error.get("loc", ())),
        msg=str(error.get("msg", "")).strip(),
        error_type=str(error.get("type")) if error.get("type") is not None else None,
        ctx=dict(error.get("ctx", {})) if isinstance(error.get("ctx"), dict) else {},
        input_value_type=type(input_value).__name__ if "input" in error else None,
    )


def _metadata_location_string(metadata: _SchemaFindingMetadata) -> str:
    parts = [str(part) for part in metadata.loc if str(part)]
    if parts and parts[0] == "project_contract":
        parts = parts[1:]
    return ".".join(parts) or "project_contract"


def _categories_from_metadata(metadata: _SchemaFindingMetadata) -> set[_ProjectContractSchemaFindingCategory]:
    categories: set[_ProjectContractSchemaFindingCategory] = set()
    location = _metadata_location_string(metadata)
    if _is_canonical_authoritative_scalar_location(location):
        categories.add(_ProjectContractSchemaFindingCategory.AUTHORITATIVE_SCALAR)
    error_type = metadata.error_type or ""
    if error_type in {"extra_forbidden", "value_error.extra"} or error_type.endswith(".extra"):
        categories.add(_ProjectContractSchemaFindingCategory.RECOVERABLE)
    if error_type in {
        "list_type",
        "dict_type",
        "model_type",
        "type_error.list",
        "value_error.list",
        "type_error.dict",
        "value_error.dict",
    }:
        categories.add(_ProjectContractSchemaFindingCategory.LOSSY_LIST_NORMALIZATION)
    if error_type == "value_error" and str(metadata.ctx.get("error", "")).lower() in {
        "must be a list",
        "must be an object",
        "must be a valid list member",
    }:
        categories.add(_ProjectContractSchemaFindingCategory.LOSSY_LIST_NORMALIZATION)
    message = metadata.msg.lower()
    if "must be a list" in message or "must be a valid list member" in message or "must be an object" in message:
        categories.add(_ProjectContractSchemaFindingCategory.LOSSY_LIST_NORMALIZATION)
    canonical_value = metadata.ctx.get("canonical_value")
    if isinstance(canonical_value, str) and canonical_value.strip():
        categories.add(_ProjectContractSchemaFindingCategory.CASE_DRIFT)
    return categories


_RECOVERABLE_SCHEMA_WARNING_PATTERNS = (
    re.compile(r"^.+: Extra inputs are not permitted$"),
    re.compile(r"^.+ was normalized from blank string to empty list$"),
    re.compile(r"^.+\.\d+ must be a valid list member$"),
    re.compile(r"^.+\.\d+: Input should .+$"),
    re.compile(r"^.+: Input should be a valid string$"),
)
_LOSSY_LIST_NORMALIZATION_WARNING_PATTERNS = (
    re.compile(r"^.+ must be a list, not .+$"),
    re.compile(r"^.+ must be an object, not .+$"),
    re.compile(r"^.+ must not be blank$"),
    re.compile(r"^.+ is a duplicate$"),
    re.compile(r"^.+\.\d+ must not be blank$"),
    re.compile(r"^.+\.\d+ is a duplicate$"),
)
_CASE_DRIFT_SCHEMA_WARNING_PATTERNS = (re.compile(r"^.+ must use exact canonical value: .+$"),)
_AUTHORITATIVE_SCALAR_FINDING_PATTERNS = (
    re.compile(r"^schema_version must be 1$"),
    re.compile(r"^schema_version must be the integer 1$"),
    re.compile(r"^schema_version: Input should be 1$"),
    re.compile(r"^.+\.must_surface must be a boolean$"),
    re.compile(r"^.+\.must_surface: Input should be a valid boolean.*$"),
)

_SCHEMA_VERSION_REQUIRED_ERROR = "schema_version is required"


class _ProjectContractSchemaFindingCategory(StrEnum):
    RECOVERABLE = "recoverable"
    LOSSY_LIST_NORMALIZATION = "lossy_list_normalization"
    NESTED_COLLECTION_ITEM_TRUNCATION = "nested_collection_item_truncation"
    CASE_DRIFT = "case_drift"
    AUTHORITATIVE_SCALAR = "authoritative_scalar"


_SCHEMA_FINDING_CATEGORY_PATTERNS: tuple[
    tuple[_ProjectContractSchemaFindingCategory, tuple[re.Pattern[str], ...]], ...
] = (
    (_ProjectContractSchemaFindingCategory.RECOVERABLE, _RECOVERABLE_SCHEMA_WARNING_PATTERNS),
    (_ProjectContractSchemaFindingCategory.LOSSY_LIST_NORMALIZATION, _LOSSY_LIST_NORMALIZATION_WARNING_PATTERNS),
    (_ProjectContractSchemaFindingCategory.CASE_DRIFT, _CASE_DRIFT_SCHEMA_WARNING_PATTERNS),
    (_ProjectContractSchemaFindingCategory.AUTHORITATIVE_SCALAR, _AUTHORITATIVE_SCALAR_FINDING_PATTERNS),
)


def _split_schema_finding_location_and_message(error: str) -> tuple[str | None, str]:
    """Return ``(location, message)`` when an error is in ``location: message`` form."""

    location, separator, message = error.partition(": ")
    if separator and location and " " not in location:
        return location, message
    return None, error


def _matches_equivalent_authoritative_schema_finding(*, location: str | None, message: str) -> bool:
    """Return whether one finding is an equivalent authoritative scalar variant."""

    normalized_message = message.strip().casefold()
    if location == "schema_version":
        return normalized_message.startswith("input should be 1")
    if isinstance(location, str) and location.endswith(".must_surface"):
        return normalized_message.startswith("input should be a valid boolean")
    return False


def _matches_equivalent_recoverable_schema_finding(*, message: str) -> bool:
    """Return whether one finding is an equivalent recoverable schema-warning variant."""

    return message.strip().startswith("Extra inputs are not permitted")


def _schema_finding_location_depth(location: str | None) -> int:
    """Return the number of list-index segments in one dotted schema location."""

    if location is None:
        return 0
    return sum(1 for part in location.split(".") if part.isdigit())


def _schema_finding_location(error: str) -> str | None:
    """Return a best-effort dotted location for one formatted schema finding."""

    location, _message = _split_schema_finding_location_and_message(error)
    if location is not None:
        return location

    nested_location = re.match(
        r"^(?P<location>.+?) (?:must not be blank|is a duplicate|must be a valid list member|must be a list, not .+|must be an object, not .+)$",
        error.strip(),
    )
    if nested_location is not None:
        return nested_location.group("location")
    return None


def _is_nested_collection_item_location(location: str | None) -> bool:
    """Return whether one location is inside a nested collection item."""

    return _schema_finding_location_depth(location) >= 2


def _project_contract_schema_finding_categories(
    error: str,
    *,
    metadata: _SchemaFindingMetadata | None = None,
) -> frozenset[_ProjectContractSchemaFindingCategory]:
    """Classify one schema finding into semantic categories."""

    normalized_error = error.strip()
    if not normalized_error:
        return frozenset()

    categories: set[_ProjectContractSchemaFindingCategory] = set()
    location, message = _split_schema_finding_location_and_message(normalized_error)
    if metadata is not None:
        location = _metadata_location_string(metadata)
        message = metadata.msg
        categories.update(_categories_from_metadata(metadata))
    else:
        for category, patterns in _SCHEMA_FINDING_CATEGORY_PATTERNS:
            if any(pattern.fullmatch(normalized_error) for pattern in patterns):
                categories.add(category)
    if _matches_equivalent_recoverable_schema_finding(message=message):
        categories.add(_ProjectContractSchemaFindingCategory.RECOVERABLE)
    if _matches_equivalent_authoritative_schema_finding(location=location, message=message):
        categories.add(_ProjectContractSchemaFindingCategory.AUTHORITATIVE_SCALAR)

    nested_location = location or _schema_finding_location(normalized_error)
    if nested_location is not None and _is_nested_collection_item_location(nested_location):
        if categories & {
            _ProjectContractSchemaFindingCategory.RECOVERABLE,
            _ProjectContractSchemaFindingCategory.LOSSY_LIST_NORMALIZATION,
        }:
            categories.add(_ProjectContractSchemaFindingCategory.NESTED_COLLECTION_ITEM_TRUNCATION)

    return frozenset(categories)


def _project_contract_schema_version_missing_error(contract_payload: object) -> str | None:
    if isinstance(contract_payload, dict) and "schema_version" not in contract_payload:
        return _SCHEMA_VERSION_REQUIRED_ERROR
    return None


def _validate_direct_project_contract_schema_version(value: object) -> str | None:
    if type(value) is not int:
        return "schema_version must be the integer 1"
    if value != 1:
        return "schema_version: Input should be 1"
    return None


class ProjectContractValidationResult(BaseModel):
    """Executable validation result for a project-scoping contract."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    question: str | None = None
    decisive_target_count: int = 0
    guidance_signal_count: int = 0
    reference_count: int = 0
    mode: Literal["draft", "approved"] = "draft"


def _format_schema_error(error: dict[str, object]) -> str:
    """Return a concise, user-facing contract schema error."""

    location = ".".join(str(part) for part in error.get("loc", ())) or "project_contract"
    message = str(error.get("msg", "validation failed")).strip() or "validation failed"
    input_value = error.get("input")

    if message == "Field required":
        return f"{location} is required"

    if "valid dictionary" in message.lower():
        actual_type = type(input_value).__name__
        return f"{location} must be an object, not {actual_type}"

    if message == "Value error, must not be blank":
        return f"{location} must not be blank"

    if message in {"Value error, must be a non-empty string", "Value error, value must not be blank"}:
        return f"{location} must be a non-empty string"

    return f"{location}: {message}"


def _format_schema_finding(error: dict[str, object]) -> tuple[str, _SchemaFindingMetadata]:
    """Return a formatted schema finding and one-call structured metadata."""

    return _format_schema_error(error), _schema_finding_metadata_from_error(error)


def _schema_error_location(error: dict[str, object], *, path_prefix: str = "") -> str:
    """Return the fully qualified dotted location for one Pydantic error."""

    loc = tuple(error.get("loc", ()))
    parts = [path_prefix, *(str(part) for part in loc if str(part))]
    return ".".join(part for part in parts if part)


_BOOLEAN_TEXT_CHOICES: dict[str, bool] = {
    "1": True,
    "true": True,
    "yes": True,
    "y": True,
    "on": True,
    "0": False,
    "false": False,
    "no": False,
    "n": False,
    "off": False,
}


def _coerce_common_bool_spelling(value: object) -> bool | None:
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized:
            return _BOOLEAN_TEXT_CHOICES.get(normalized)
    return None


def _is_canonical_authoritative_scalar_location(location: str) -> bool:
    """Return whether one location is governed by a canonical authoritative scalar error."""

    return location == "schema_version" or re.fullmatch(r"references\.\d+\.must_surface", location) is not None


def _sanitize_contract_scalars(
    value: object,
    *,
    path_prefix: str = "",
    errors: list[str] | None = None,
    canonical_authoritative_scalar_locations: set[str] | None = None,
    metadata_by_error: dict[str, _SchemaFindingMetadata] | None = None,
) -> object:
    """Remove malformed coercive scalars so callers can reject them explicitly.

    Pydantic intentionally accepts a few coercions that are convenient for loose
    inputs but brittle for contract authority data, notably:

    - ``schema_version: true`` -> ``1``
    - ``must_surface: "yes"`` -> ``True``

    Validation entrypoints should reject those values rather than quietly
    canonicalizing them.
    """

    sink = errors if errors is not None else []

    if isinstance(value, dict):
        cleaned: dict[object, object] = {}
        for raw_key, raw_item in value.items():
            key = str(raw_key)
            location = f"{path_prefix}.{key}" if path_prefix else key

            if location == "schema_version":
                schema_version_error = _validate_direct_project_contract_schema_version(raw_item)
                if schema_version_error is not None:
                    sink.append(schema_version_error)
                    if canonical_authoritative_scalar_locations is not None:
                        canonical_authoritative_scalar_locations.add(location)
                    continue
                cleaned[raw_key] = raw_item
                continue

            if re.fullmatch(r"references\.\d+\.must_surface", location):
                if type(raw_item) is bool:
                    cleaned[raw_key] = raw_item
                    continue
                coerced_bool = _coerce_common_bool_spelling(raw_item)
                if coerced_bool is not None:
                    location_parts = tuple(part for part in location.split(".") if part)
                    formatted, metadata = _format_schema_finding(
                        {
                            "loc": location_parts,
                            "msg": f"must be a boolean (coerced from {raw_item!r})",
                            "type": "value_error.boolean_coercion",
                            "input": raw_item,
                            "ctx": {"coerced_value": coerced_bool},
                        }
                    )
                    sink.append(formatted)
                    if metadata_by_error is not None:
                        metadata_by_error[formatted] = metadata
                    cleaned[raw_key] = coerced_bool
                    continue
                sink.append(f"{location} must be a boolean")
                if canonical_authoritative_scalar_locations is not None:
                    canonical_authoritative_scalar_locations.add(location)
                cleaned[raw_key] = raw_item
                continue

            cleaned[raw_key] = _sanitize_contract_scalars(
                raw_item,
                path_prefix=location,
                errors=sink,
                canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
                metadata_by_error=metadata_by_error,
            )
        return cleaned

    if isinstance(value, list):
        return [
            _sanitize_contract_scalars(
                item,
                path_prefix=f"{path_prefix}.{index}" if path_prefix else str(index),
                errors=sink,
                canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
                metadata_by_error=metadata_by_error,
            )
            for index, item in enumerate(value)
        ]

    return copy.deepcopy(value)


def _required_project_contract_section_error(field_name: str) -> str:
    return f"{field_name} is required"


def _strip_unknown_model_keys(
    value: dict[str, object],
    *,
    path_prefix: str,
    model: type[BaseModel],
    errors: list[str],
) -> dict[str, object]:
    cleaned = copy.deepcopy(value)
    for key in list(cleaned):
        if key in model.model_fields:
            continue
        location = f"{path_prefix}.{key}" if path_prefix else key
        errors.append(f"{location}: Extra inputs are not permitted (draft/salvage warning; strict authoritative validation still rejects unknown keys)")
        cleaned.pop(key, None)
    return cleaned


def _list_item_model(field: object) -> type[BaseModel] | None:
    """Return the BaseModel item type for a typed list field when available."""

    annotation = getattr(field, "annotation", None)
    if annotation is None:
        return None
    origin = get_origin(annotation)
    if origin is not list:
        return None
    item_types = get_args(annotation)
    if len(item_types) != 1:
        return None
    item_type = item_types[0]
    if isinstance(item_type, type) and issubclass(item_type, BaseModel):
        return item_type
    return None


def _salvage_model_mapping(
    value: object,
    *,
    path_prefix: str,
    model: type[BaseModel],
    errors: list[str],
    canonical_authoritative_scalar_locations: set[str] | None = None,
    default_value: dict[str, object] | None = None,
    required_fields: tuple[str, ...] = (),
    missing_is_default: bool = False,
) -> tuple[dict[str, object] | None, bool]:
    if value is None:
        if missing_is_default and default_value is not None:
            return copy.deepcopy(default_value), False
        actual_type = type(value).__name__
        errors.append(f"{path_prefix} must be an object, not {actual_type}")
        return (copy.deepcopy(default_value), True) if default_value is not None else (None, True)
    if not isinstance(value, dict):
        actual_type = type(value).__name__
        errors.append(f"{path_prefix} must be an object, not {actual_type}")
        return (copy.deepcopy(default_value), True) if default_value is not None else (None, True)

    cleaned = _strip_unknown_model_keys(value, path_prefix=path_prefix, model=model, errors=errors)
    missing_required_fields = [field_name for field_name in required_fields if field_name not in cleaned]
    if missing_required_fields:
        for field_name in missing_required_fields:
            errors.append(f"{path_prefix}.{field_name} is required")
        return None, True

    while True:
        try:
            return model.model_validate(cleaned).model_dump(), False
        except PydanticValidationError as exc:
            progress = False
            blocked = False
            for error in exc.errors():
                loc = tuple(error.get("loc", ()))
                if not loc:
                    continue
                key = str(loc[0])
                field = model.model_fields.get(key)
                if field is None:
                    continue
                location = _schema_error_location({"loc": loc}, path_prefix=path_prefix)
                if (
                    canonical_authoritative_scalar_locations is not None
                    and _is_canonical_authoritative_scalar_location(location)
                    and location in canonical_authoritative_scalar_locations
                ):
                    blocked = True
                    progress = True
                    continue
                formatted = _format_schema_error(
                    {
                        "loc": (path_prefix, *loc),
                        "msg": error.get("msg"),
                        "input": error.get("input"),
                        "type": error.get("type"),
                    }
                )
                field_value = cleaned.get(key)
                item_model = _list_item_model(field)
                if item_model is not None and isinstance(field_value, dict):
                    nested_errors: list[str] = []
                    salvaged_item, item_blocked = _salvage_model_mapping(
                        field_value,
                        path_prefix=f"{path_prefix}.{key}",
                        model=item_model,
                        errors=nested_errors,
                        canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
                    )
                    if salvaged_item is not None and not item_blocked:
                        cleaned[key] = [salvaged_item]
                        progress = True
                        for nested_error in nested_errors:
                            if nested_error not in errors:
                                errors.append(nested_error)
                        continue
                    if field.is_required():
                        for nested_error in nested_errors:
                            if nested_error not in errors:
                                errors.append(nested_error)
                        errors.append(formatted)
                        blocked = True
                    else:
                        cleaned.pop(key, None)
                        progress = True
                    continue
                if isinstance(field_value, list) and len(loc) > 1 and isinstance(loc[1], int):
                    item_indexes: set[int] = set()
                    item_errors_by_index: dict[int, list[str]] = defaultdict(list)
                    for item_error in exc.errors():
                        item_loc = tuple(item_error.get("loc", ()))
                        if len(item_loc) > 1 and str(item_loc[0]) == key and isinstance(item_loc[1], int):
                            item_index = int(item_loc[1])
                            item_indexes.add(item_index)
                            formatted_item_error = _format_schema_error(
                                {
                                    "loc": (path_prefix, *item_loc),
                                    "msg": item_error.get("msg"),
                                    "input": item_error.get("input"),
                                    "type": item_error.get("type"),
                                }
                            )
                            if formatted_item_error not in item_errors_by_index[item_index]:
                                item_errors_by_index[item_index].append(formatted_item_error)
                    salvaged_items = copy.deepcopy(field_value)
                    for index in sorted(item_indexes, reverse=True):
                        if not (0 <= index < len(salvaged_items)):
                            continue
                        item_value = salvaged_items[index]
                        if item_model is not None and isinstance(item_value, dict):
                            salvaged_item, item_blocking = _salvage_model_mapping(
                                item_value,
                                path_prefix=f"{path_prefix}.{key}.{index}",
                                model=item_model,
                                errors=errors,
                                canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
                            )
                            if item_blocking:
                                blocked = True
                                continue
                            if salvaged_item is not None:
                                salvaged_items[index] = salvaged_item
                                progress = True
                                continue
                        item_errors = item_errors_by_index.get(index) or [
                            f"{path_prefix}.{key}.{index} must be a valid list member"
                        ]
                        for item_error in item_errors:
                            if item_error not in errors:
                                errors.append(item_error)
                        del salvaged_items[index]
                        progress = True
                    cleaned[key] = salvaged_items
                    continue
                if field.is_required():
                    errors.append(formatted)
                    blocked = True
                    continue
                if key in cleaned:
                    errors.append(formatted)
                    cleaned.pop(key, None)
                    progress = True
            if blocked:
                return None, True
            if not progress:
                return (copy.deepcopy(default_value), True) if default_value is not None else (None, True)


def _salvage_contract_collection(
    value: object,
    *,
    field_name: str,
    item_model: type[BaseModel],
    errors: list[str],
    canonical_authoritative_scalar_locations: set[str] | None = None,
) -> tuple[list[dict[str, object]], bool]:
    path_prefix = field_name
    if not isinstance(value, list):
        errors.append(f"{path_prefix} must be a list, not {type(value).__name__}")
        return [], False

    normalized_items: list[dict[str, object]] = []
    blocked = False
    for index, item in enumerate(value):
        item_prefix = f"{path_prefix}.{index}"
        if not isinstance(item, dict):
            errors.append(f"{item_prefix} must be an object, not {type(item).__name__}")
            continue
        normalized, item_blocked = _salvage_model_mapping(
            item,
            path_prefix=item_prefix,
            model=item_model,
            errors=errors,
            canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
        )
        if item_blocked:
            blocked = True
            continue
        if normalized is not None:
            normalized_items.append(normalized)
    return normalized_items, blocked


def _normalize_blank_list_fields(contract: dict[str, object]) -> None:
    """Coerce blank-string list fields to empty lists during salvage."""

    def _blank_string(value: object) -> bool:
        return isinstance(value, str) and not value.strip()

    for field_name in PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS:
        if field_name in contract and _blank_string(contract[field_name]):
            contract[field_name] = []

    for section_name, field_names in PROJECT_CONTRACT_MAPPING_LIST_FIELDS.items():
        section = contract.get(section_name)
        if not isinstance(section, dict):
            continue
        for field_name in field_names:
            if field_name in section and _blank_string(section[field_name]):
                section[field_name] = []

    for collection_name, field_names in PROJECT_CONTRACT_COLLECTION_LIST_FIELDS.items():
        collection = contract.get(collection_name)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            for field_name in field_names:
                if field_name in item and _blank_string(item[field_name]):
                    item[field_name] = []
            if collection_name != "claims":
                continue
            parameters = item.get("parameters")
            if isinstance(parameters, list):
                for parameter in parameters:
                    if isinstance(parameter, dict) and _blank_string(parameter.get("aliases")):
                        parameter["aliases"] = []
            hypotheses = item.get("hypotheses")
            if isinstance(hypotheses, list):
                for hypothesis in hypotheses:
                    if isinstance(hypothesis, dict) and _blank_string(hypothesis.get("symbols")):
                        hypothesis["symbols"] = []


def _collect_blank_list_normalization_findings(
    raw_contract: dict[str, object],
    normalized_contract: dict[str, object],
) -> list[str]:
    """Return recoverable findings for blank string list fields that were normalized away."""

    findings: list[str] = []

    def _record(path: str) -> None:
        findings.append(f"{path} was normalized from blank string to empty list")

    for field_name in PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS:
        raw_value = raw_contract.get(field_name)
        normalized_value = normalized_contract.get(field_name)
        if isinstance(raw_value, str) and not raw_value.strip() and isinstance(normalized_value, list):
            _record(field_name)

    for section_name, field_names in PROJECT_CONTRACT_MAPPING_LIST_FIELDS.items():
        raw_section = raw_contract.get(section_name)
        normalized_section = normalized_contract.get(section_name)
        if not isinstance(raw_section, dict) or not isinstance(normalized_section, dict):
            continue
        for field_name in field_names:
            raw_value = raw_section.get(field_name)
            normalized_value = normalized_section.get(field_name)
            if isinstance(raw_value, str) and not raw_value.strip() and isinstance(normalized_value, list):
                _record(f"{section_name}.{field_name}")

    for collection_name, field_names in PROJECT_CONTRACT_COLLECTION_LIST_FIELDS.items():
        raw_collection = raw_contract.get(collection_name)
        normalized_collection = normalized_contract.get(collection_name)
        if not isinstance(raw_collection, list) or not isinstance(normalized_collection, list):
            continue
        for index, raw_item in enumerate(raw_collection):
            if not isinstance(raw_item, dict) or index >= len(normalized_collection):
                continue
            normalized_item = normalized_collection[index]
            if not isinstance(normalized_item, dict):
                continue
            for field_name in field_names:
                raw_value = raw_item.get(field_name)
                normalized_value = normalized_item.get(field_name)
                if isinstance(raw_value, str) and not raw_value.strip() and isinstance(normalized_value, list):
                    _record(f"{collection_name}.{index}.{field_name}")

            if collection_name != "claims":
                continue

            raw_parameters = raw_item.get("parameters")
            normalized_parameters = normalized_item.get("parameters")
            if isinstance(raw_parameters, list) and isinstance(normalized_parameters, list):
                for parameter_index, raw_parameter in enumerate(raw_parameters):
                    if not isinstance(raw_parameter, dict) or parameter_index >= len(normalized_parameters):
                        continue
                    normalized_parameter = normalized_parameters[parameter_index]
                    if not isinstance(normalized_parameter, dict):
                        continue
                    raw_value = raw_parameter.get("aliases")
                    normalized_value = normalized_parameter.get("aliases")
                    if isinstance(raw_value, str) and not raw_value.strip() and isinstance(normalized_value, list):
                        _record(f"claims.{index}.parameters.{parameter_index}.aliases")

            raw_hypotheses = raw_item.get("hypotheses")
            normalized_hypotheses = normalized_item.get("hypotheses")
            if isinstance(raw_hypotheses, list) and isinstance(normalized_hypotheses, list):
                for hypothesis_index, raw_hypothesis in enumerate(raw_hypotheses):
                    if not isinstance(raw_hypothesis, dict) or hypothesis_index >= len(normalized_hypotheses):
                        continue
                    normalized_hypothesis = normalized_hypotheses[hypothesis_index]
                    if not isinstance(normalized_hypothesis, dict):
                        continue
                    raw_value = raw_hypothesis.get("symbols")
                    normalized_value = normalized_hypothesis.get("symbols")
                    if isinstance(raw_value, str) and not raw_value.strip() and isinstance(normalized_value, list):
                        _record(f"claims.{index}.hypotheses.{hypothesis_index}.symbols")

    return findings


def salvage_project_contract(
    contract: dict[str, object],
) -> tuple[ResearchContract | None, list[str], dict[str, _SchemaFindingMetadata]]:
    errors: list[str] = []
    canonical_authoritative_scalar_locations: set[str] = set()
    metadata_by_error: dict[str, _SchemaFindingMetadata] = {}
    errors.extend(_collect_literal_case_drift_errors(contract))
    raw_required_section_presence = {
        field_name: field_name in contract
        for field_name in ("schema_version", "scope", "context_intake", "uncertainty_markers")
    }
    scalar_sanitized = _sanitize_contract_scalars(
        contract,
        errors=errors,
        canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
        metadata_by_error=metadata_by_error,
    )
    if not isinstance(scalar_sanitized, dict):
        return None, errors, metadata_by_error

    working = _strip_unknown_model_keys(scalar_sanitized, path_prefix="", model=ResearchContract, errors=errors)
    normalized_contract = copy.deepcopy(working)
    _normalize_blank_list_fields(normalized_contract)
    errors.extend(_collect_blank_list_normalization_findings(working, normalized_contract))

    missing_required_section_errors: list[str] = []
    for field_name in ("schema_version", "scope", "context_intake", "uncertainty_markers"):
        if field_name not in normalized_contract and not raw_required_section_presence[field_name]:
            missing_required_section_errors.append(_required_project_contract_section_error(field_name))
    if missing_required_section_errors:
        return None, [*errors, *missing_required_section_errors], metadata_by_error

    collection_models: dict[str, type[BaseModel]] = {
        "observables": ContractObservable,
        "claims": ContractClaim,
        "deliverables": ContractDeliverable,
        "acceptance_tests": ContractAcceptanceTest,
        "references": ContractReference,
        "forbidden_proxies": ContractForbiddenProxy,
        "links": ContractLink,
    }
    for field_name, item_model in collection_models.items():
        if field_name not in normalized_contract:
            continue
        normalized_items, _collection_blocked = _salvage_contract_collection(
            normalized_contract.get(field_name),
            field_name=field_name,
            item_model=item_model,
            errors=errors,
            canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
        )
        normalized_contract[field_name] = normalized_items

    scope, scope_blocked = _salvage_model_mapping(
        normalized_contract.get("scope"),
        path_prefix="scope",
        model=ContractScope,
        errors=errors,
        canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
    )
    if scope_blocked or scope is None:
        return None, errors, metadata_by_error
    normalized_contract["scope"] = scope

    context_intake, context_intake_blocked = _salvage_model_mapping(
        normalized_contract.get("context_intake"),
        path_prefix="context_intake",
        model=ContractContextIntake,
        errors=errors,
        canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
    )
    if context_intake_blocked or context_intake is None:
        return None, errors, metadata_by_error
    normalized_contract["context_intake"] = context_intake

    if "approach_policy" in normalized_contract:
        approach_policy_errors: list[str] = []
        approach_policy, approach_policy_blocked = _salvage_model_mapping(
            normalized_contract.get("approach_policy"),
            path_prefix="approach_policy",
            model=ContractApproachPolicy,
            errors=approach_policy_errors,
            canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
        )
        errors.extend(error for error in approach_policy_errors if error not in errors)
        if approach_policy_blocked or approach_policy is None:
            normalized_contract.pop("approach_policy", None)
        else:
            normalized_contract["approach_policy"] = approach_policy

    uncertainty_markers, uncertainty_markers_blocked = _salvage_model_mapping(
        normalized_contract.get("uncertainty_markers"),
        path_prefix="uncertainty_markers",
        model=ContractUncertaintyMarkers,
        errors=errors,
        canonical_authoritative_scalar_locations=canonical_authoritative_scalar_locations,
        required_fields=("weakest_anchors", "disconfirming_observations"),
    )
    if uncertainty_markers_blocked or uncertainty_markers is None:
        return None, errors, metadata_by_error
    normalized_contract["uncertainty_markers"] = uncertainty_markers

    if "schema_version" in normalized_contract:
        schema_version_error = _validate_direct_project_contract_schema_version(normalized_contract["schema_version"])
        if schema_version_error is not None:
            if schema_version_error not in errors:
                errors.append(schema_version_error)
            normalized_contract.pop("schema_version", None)

    try:
        return ResearchContract.model_validate(normalized_contract), errors, metadata_by_error
    except PydanticValidationError as exc:
        for error in exc.errors():
            formatted = _format_schema_error(error)
            if formatted not in errors:
                errors.append(formatted)
        return None, errors, metadata_by_error


def split_project_contract_schema_findings(
    errors: list[str],
    *,
    allow_case_drift_recovery: bool = True,
    metadata_by_error: dict[str, _SchemaFindingMetadata] | None = None,
) -> tuple[list[str], list[str]]:
    """Partition salvage findings into recoverable case-drift warnings and blocking errors."""

    recoverable: list[str] = []
    blocking: list[str] = []
    for error in errors:
        metadata = None if metadata_by_error is None else metadata_by_error.get(error)
        if metadata is not None and metadata.error_type == "value_error.boolean_coercion":
            if allow_case_drift_recovery:
                recoverable.append(error)
            else:
                blocking.append(error)
            continue
        categories = _project_contract_schema_finding_categories(
            error,
            metadata=metadata,
        )
        if _ProjectContractSchemaFindingCategory.NESTED_COLLECTION_ITEM_TRUNCATION in categories:
            blocking.append(error)
            continue
        recoverable_finding = _ProjectContractSchemaFindingCategory.RECOVERABLE in categories
        case_drift_finding = _ProjectContractSchemaFindingCategory.CASE_DRIFT in categories
        if recoverable_finding or (allow_case_drift_recovery and case_drift_finding):
            recoverable.append(error)
            continue
        blocking.append(error)
    return recoverable, blocking


def is_authoritative_project_contract_schema_finding(error: str) -> bool:
    """Return whether one schema finding touches an authoritative scalar field."""

    categories = _project_contract_schema_finding_categories(error)
    return _ProjectContractSchemaFindingCategory.AUTHORITATIVE_SCALAR in categories


def is_repair_relevant_project_contract_schema_finding(error: str) -> bool:
    """Return whether one recoverable schema finding still requires repair."""

    categories = _project_contract_schema_finding_categories(error)
    if _ProjectContractSchemaFindingCategory.CASE_DRIFT in categories:
        return False
    return bool(
        {
            _ProjectContractSchemaFindingCategory.RECOVERABLE,
            _ProjectContractSchemaFindingCategory.LOSSY_LIST_NORMALIZATION,
        }
        & categories
    )


def _has_authoritative_scalar_schema_findings(errors: list[str]) -> bool:
    """Return whether salvage findings touched authoritative scalar fields."""

    return any(is_authoritative_project_contract_schema_finding(error) for error in errors)


def _collect_list_shape_drift_errors(contract: dict[str, object]) -> list[str]:
    """Return list-typed field mismatches for raw contract payload boundaries."""

    errors: list[str] = []

    def _check_mapping_lists(
        mapping: object,
        *,
        path_prefix: str,
        field_names: tuple[str, ...],
    ) -> None:
        if not isinstance(mapping, dict):
            return
        for field_name in field_names:
            if field_name not in mapping:
                continue
            raw_value = mapping.get(field_name)
            if isinstance(raw_value, list):
                continue
            location = f"{path_prefix}.{field_name}" if path_prefix else field_name
            if isinstance(raw_value, str) and not raw_value.strip():
                errors.append(f"{location} must not be blank")
                continue
            errors.append(f"{location} must be a list, not {type(raw_value).__name__}")

    def _check_collection_item_lists(collection_name: str, field_names: tuple[str, ...]) -> None:
        raw_collection = contract.get(collection_name)
        if not isinstance(raw_collection, list):
            return
        for index, item in enumerate(raw_collection):
            if not isinstance(item, dict):
                continue
            _check_mapping_lists(
                item,
                path_prefix=f"{collection_name}.{index}",
                field_names=field_names,
            )

    for field_name in PROJECT_CONTRACT_TOP_LEVEL_LIST_FIELDS:
        if field_name in contract:
            raw_value = contract.get(field_name)
            if isinstance(raw_value, list):
                continue
            if isinstance(raw_value, str) and not raw_value.strip():
                errors.append(f"{field_name} must not be blank")
                continue
            errors.append(f"{field_name} must be a list, not {type(raw_value).__name__}")

    for section_name, field_names in PROJECT_CONTRACT_MAPPING_LIST_FIELDS.items():
        _check_mapping_lists(contract.get(section_name), path_prefix=section_name, field_names=field_names)
    for collection_name, field_names in PROJECT_CONTRACT_COLLECTION_LIST_FIELDS.items():
        _check_collection_item_lists(collection_name, field_names)

    return dedupe_preserve_order(errors)


_LITERAL_CASE_DRIFT_FIELD_PATTERNS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"^observables\.\d+\.kind$"), CONTRACT_OBSERVABLE_KIND_VALUES),
    (re.compile(r"^claims\.\d+\.claim_kind$"), CONTRACT_CLAIM_KIND_VALUES),
    (
        re.compile(r"^claims\.\d+\.hypotheses\.\d+\.category$"),
        ("assumption", "precondition", "regime", "definition", "lemma", "other"),
    ),
    (re.compile(r"^deliverables\.\d+\.kind$"), CONTRACT_DELIVERABLE_KIND_VALUES),
    (re.compile(r"^acceptance_tests\.\d+\.kind$"), CONTRACT_ACCEPTANCE_TEST_KIND_VALUES),
    (re.compile(r"^acceptance_tests\.\d+\.automation$"), CONTRACT_ACCEPTANCE_AUTOMATION_VALUES),
    (re.compile(r"^references\.\d+\.kind$"), CONTRACT_REFERENCE_KIND_VALUES),
    (re.compile(r"^references\.\d+\.role$"), CONTRACT_REFERENCE_ROLE_VALUES),
    (re.compile(r"^references\.\d+\.required_actions\.\d+$"), CONTRACT_REFERENCE_ACTION_VALUES),
    (re.compile(r"^links\.\d+\.relation$"), CONTRACT_LINK_RELATION_VALUES),
)


def _collect_literal_case_drift_errors(contract: object) -> list[str]:
    """Return recoverable findings for case-insensitive literal drift."""

    if not isinstance(contract, dict):
        return []

    errors: list[str] = []

    def _walk(value: object, *, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                _walk(item, path=next_path)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                next_path = f"{path}.{index}" if path else str(index)
                _walk(item, path=next_path)
            return
        if not isinstance(value, str):
            return

        stripped = value.strip()
        if not stripped:
            return

        for pattern, choices in _LITERAL_CASE_DRIFT_FIELD_PATTERNS:
            if not pattern.fullmatch(path):
                continue
            canonical_choice = next((choice for choice in choices if stripped.casefold() == choice.casefold()), None)
            if canonical_choice is not None and value != canonical_choice:
                errors.append(f"{path} must use exact canonical value: {canonical_choice}")
            return

    _walk(contract, path="")
    return errors


def _light_contract_consistency_errors(contract: ResearchContract) -> list[str]:
    """Return cross-link errors without forcing mature-phase completeness."""

    errors: list[str] = collect_contract_integrity_errors(contract)

    observable_ids = {observable.id for observable in contract.observables}
    claim_ids = {claim.id for claim in contract.claims}
    deliverable_ids = {deliverable.id for deliverable in contract.deliverables}
    acceptance_test_ids = {test.id for test in contract.acceptance_tests}
    reference_ids = {reference.id for reference in contract.references}
    known_subject_ids = claim_ids | deliverable_ids
    known_ids = known_subject_ids | acceptance_test_ids | reference_ids

    for must_read_ref in contract.context_intake.must_read_refs:
        if must_read_ref not in reference_ids:
            errors.append(f"context_intake.must_read_refs references unknown reference {must_read_ref}")

    for claim in contract.claims:
        for observable_id in claim.observables:
            if observable_id not in observable_ids:
                errors.append(f"claim {claim.id} references unknown observable {observable_id}")
        for deliverable_id in claim.deliverables:
            if deliverable_id not in deliverable_ids:
                errors.append(f"claim {claim.id} references unknown deliverable {deliverable_id}")
        for test_id in claim.acceptance_tests:
            if test_id not in acceptance_test_ids:
                errors.append(f"claim {claim.id} references unknown acceptance test {test_id}")
        for reference_id in claim.references:
            if reference_id not in reference_ids:
                errors.append(f"claim {claim.id} references unknown reference {reference_id}")

    for test in contract.acceptance_tests:
        if test.subject not in known_subject_ids:
            errors.append(f"acceptance test {test.id} targets unknown subject {test.subject}")
        for evidence_id in test.evidence_required:
            if evidence_id not in known_ids:
                errors.append(f"acceptance test {test.id} references unknown evidence {evidence_id}")

    for reference in contract.references:
        if reference.must_surface and not reference.required_actions:
            errors.append(f"reference {reference.id} is must_surface but missing required_actions")
        if reference.must_surface and not reference.applies_to:
            errors.append(f"reference {reference.id} is must_surface but missing applies_to")
        for applies_to_id in reference.applies_to:
            if applies_to_id not in known_subject_ids:
                errors.append(f"reference {reference.id} applies_to unknown target {applies_to_id}")

    for forbidden_proxy in contract.forbidden_proxies:
        if forbidden_proxy.subject not in known_subject_ids:
            errors.append(f"forbidden proxy {forbidden_proxy.id} targets unknown subject {forbidden_proxy.subject}")

    for link in contract.links:
        if link.source not in known_ids:
            errors.append(f"link {link.id} references unknown source {link.source}")
        if link.target not in known_ids:
            errors.append(f"link {link.id} references unknown target {link.target}")
        for verification_id in link.verified_by:
            if verification_id not in acceptance_test_ids:
                errors.append(f"link {link.id} references unknown acceptance test {verification_id}")

    return errors


def _must_read_ref_counts_as_guidance(
    contract: ResearchContract,
    reference_id: str,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether one must-read reference is concrete enough to guide planning."""

    for reference in contract.references:
        if reference.id != reference_id:
            continue
        return is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        )
    return False


def _has_approved_grounding_signal(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether approved-mode grounding is explicitly captured.

    Prior outputs count here because the new-project scoping gate allows a
    concrete carry-forward output to serve as the grounding anchor for early
    planning, even before a literature benchmark or baseline is confirmed.
    """

    return any(
        (
            has_concrete_must_surface_reference(
                contract,
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
        )
    )


def _has_non_reference_grounding_signal(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether grounding is explicitly supplied outside references."""

    return any(
        (
            has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
            has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
                project_root=project_root,
                require_existing_project_artifacts=True,
            ),
        )
    )


def _prior_output_counts_as_guidance(
    value: str,
    *,
    project_root: Path | None = None,
) -> bool:
    """Return whether *value* is durable prior-output guidance."""

    return is_project_artifact_path(value, project_root=project_root)


def _has_meaningful_guidance_text(values: list[str]) -> bool:
    """Return whether *values* contain non-placeholder textual guidance."""

    return any(not is_placeholder_only_guidance_text(value) for value in values)


def _guidance_signal_flags(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> dict[str, bool]:
    """Return per-field guidance presence using semantic, not merely non-empty, signals."""

    return {
        "must_read_refs": any(
            _must_read_ref_counts_as_guidance(contract, reference_id, project_root=project_root)
            for reference_id in contract.context_intake.must_read_refs
        ),
        "must_include_prior_outputs": any(
            _prior_output_counts_as_guidance(value, project_root=project_root)
            for value in contract.context_intake.must_include_prior_outputs
        ),
        "user_asserted_anchors": any(
            is_context_intake_locator_grounding(
                value, project_root=project_root, require_existing_project_artifacts=True
            )
            for value in contract.context_intake.user_asserted_anchors
        ),
        "known_good_baselines": any(
            is_context_intake_locator_grounding(
                value, project_root=project_root, require_existing_project_artifacts=True
            )
            for value in contract.context_intake.known_good_baselines
        ),
        "context_gaps": _has_meaningful_guidance_text(contract.context_intake.context_gaps),
        "crucial_inputs": _has_meaningful_guidance_text(contract.context_intake.crucial_inputs),
    }


def _context_intake_guidance_warnings(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return targeted warnings for non-durable context-intake guidance entries."""

    warnings: list[str] = []

    for value in contract.context_intake.must_include_prior_outputs:
        if _prior_output_counts_as_guidance(value, project_root=project_root):
            continue
        if project_root is not None:
            warnings.append(
                f"context_intake.must_include_prior_outputs entry does not resolve to a project-local artifact: {value}"
            )
            continue
        warnings.append(
            f"context_intake.must_include_prior_outputs entry is not an explicit project artifact path: {value}"
        )

    for field_name, values in (
        ("user_asserted_anchors", contract.context_intake.user_asserted_anchors),
        ("known_good_baselines", contract.context_intake.known_good_baselines),
    ):
        for value in values:
            if is_context_intake_locator_grounding(
                value,
                project_root=project_root,
                require_existing_project_artifacts=True,
            ):
                continue
            if is_project_artifact_path(value, project_root=None):
                if project_root is None:
                    warnings.append(
                        f"context_intake.{field_name} entry requires a resolved project_root "
                        f"to verify artifact grounding: {value}"
                    )
                else:
                    warnings.append(
                        f"context_intake.{field_name} entry does not resolve to a project-local artifact: {value}"
                    )
                continue
            warnings.append(
                f"context_intake.{field_name} entry is not concrete enough to preserve as durable guidance: {value}"
            )

    for field_name, values in (
        ("context_gaps", contract.context_intake.context_gaps),
        ("crucial_inputs", contract.context_intake.crucial_inputs),
    ):
        for value in values:
            if not is_placeholder_only_guidance_text(value):
                continue
            warnings.append(
                f"context_intake.{field_name} entry is only a placeholder and does not preserve actionable guidance: {value}"
            )

    return warnings


def _must_surface_locator_warnings(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> list[str]:
    """Return targeted warnings for non-concrete must-surface reference locators."""

    warnings: list[str] = []
    for reference in contract.references:
        if not reference.must_surface:
            continue
        if is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue
        warnings.append(
            f"reference {reference.id} is must_surface but locator is not concrete enough to ground validation"
        )
    return warnings


def _concrete_must_surface_targets(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> set[str]:
    """Return subject ids covered by concrete must-surface references."""

    targets: set[str] = set()
    for reference in contract.references:
        if not reference.must_surface:
            continue
        if not is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue
        targets.update(reference.applies_to)
    return targets


def _split_approved_mode_must_surface_locator_findings(
    contract: ResearchContract,
    *,
    project_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Return approved-mode must-surface locator errors and warnings.

    Placeholder must-surface references stay warnings only when another
    approved grounding path already covers the same scoped obligation or a
    non-reference grounding signal makes the contract globally grounded.
    """

    errors: list[str] = []
    warnings: list[str] = []
    has_global_non_reference_grounding = _has_non_reference_grounding_signal(contract, project_root=project_root)
    concrete_targets = _concrete_must_surface_targets(contract, project_root=project_root)

    for reference in contract.references:
        if not reference.must_surface:
            continue
        if is_concrete_reference_locator(
            reference.locator,
            reference_kind=reference.kind,
            project_root=project_root,
        ):
            continue

        finding = f"reference {reference.id} is must_surface but locator is not concrete enough to ground validation"
        if has_global_non_reference_grounding:
            warnings.append(finding)
            continue
        if not reference.applies_to:
            errors.append(finding)
            continue
        if any(target not in concrete_targets for target in reference.applies_to):
            errors.append(finding)
            continue
        warnings.append(finding)

    return errors, warnings


def validate_project_contract(
    contract: ResearchContract | dict[str, object],
    *,
    mode: Literal["draft", "approved"] = "draft",
    project_root: Path | None = None,
) -> ProjectContractValidationResult:
    """Validate that a project-level contract is strong enough to guide planning.

    This gate is intentionally lighter than full PLAN contract validation. It
    focuses on the project-setup failure modes from FEEDBACK.md:

    - no clear question
    - no decisive target or deliverable
    - no skeptical/disconfirming path
    - user guidance not captured anywhere durable
    """

    if isinstance(contract, ResearchContract):
        contract_payload: object = contract.model_dump(mode="python", warnings=False)
    else:
        contract_payload = contract

    strict_result = parse_project_contract_data_strict(contract_payload)
    salvage_result = parse_project_contract_data_salvage(contract_payload)
    parsed = strict_result.contract if mode == "approved" else salvage_result.contract
    schema_errors = dedupe_preserve_order(
        strict_result.blocking_errors if mode == "approved" else salvage_result.blocking_errors
    )
    schema_version_error = _project_contract_schema_version_missing_error(contract_payload)
    if schema_version_error is not None:
        schema_errors = dedupe_preserve_order([schema_version_error, *schema_errors])
    if parsed is None:
        schema_warnings = dedupe_preserve_order(salvage_result.recoverable_errors)
        return ProjectContractValidationResult(
            valid=False,
            errors=schema_errors or ["project contract could not be normalized"],
            warnings=schema_warnings,
            mode=mode,
        )
    schema_warnings = dedupe_preserve_order(salvage_result.recoverable_errors)

    question = parsed.scope.question.strip()
    decisive_target_count = len(parsed.observables) + len(parsed.claims) + len(parsed.deliverables)
    guidance_signal_count = sum(_guidance_signal_flags(parsed, project_root=project_root).values())
    reference_count = len(parsed.references)

    if schema_errors:
        return ProjectContractValidationResult(
            valid=False,
            errors=schema_errors,
            warnings=schema_warnings,
            question=question or None,
            decisive_target_count=decisive_target_count,
            guidance_signal_count=guidance_signal_count,
            reference_count=reference_count,
            mode=mode,
        )

    errors: list[str] = []
    warnings: list[str] = list(schema_warnings)

    if not question:
        errors.append("scope.question is required")
    if not parsed.scope.in_scope:
        errors.append("scope.in_scope must name at least one project boundary or objective")
    if decisive_target_count == 0:
        errors.append("project contract must include at least one observable, claim, or deliverable")
    if not parsed.uncertainty_markers.weakest_anchors:
        errors.append("uncertainty_markers.weakest_anchors must identify what is least certain")
    if not parsed.uncertainty_markers.disconfirming_observations:
        errors.append("uncertainty_markers.disconfirming_observations must identify what would force a rethink")

    errors.extend(_light_contract_consistency_errors(parsed))
    errors.extend(collect_proof_bearing_claim_integrity_errors(parsed))

    warnings.extend(_context_intake_guidance_warnings(parsed, project_root=project_root))
    if mode == "approved":
        must_surface_locator_errors, must_surface_locator_warnings = _split_approved_mode_must_surface_locator_findings(
            parsed,
            project_root=project_root,
        )
        errors.extend(must_surface_locator_errors)
        warnings.extend(must_surface_locator_warnings)
    else:
        warnings.extend(_must_surface_locator_warnings(parsed, project_root=project_root))

    has_non_reference_grounding = _has_non_reference_grounding_signal(parsed, project_root=project_root)

    if parsed.references and not any(reference.must_surface for reference in parsed.references):
        finding = "references must include at least one must_surface=true anchor"
        if mode == "approved" and not has_non_reference_grounding:
            errors.append(finding)
        else:
            warnings.append(finding)

    if (
        mode == "approved"
        and decisive_target_count > 0
        and not _has_approved_grounding_signal(
            parsed,
            project_root=project_root,
        )
    ):
        errors.append(
            "approved project contract requires at least one concrete anchor/reference/prior-output/baseline; explicit missing-anchor notes preserve uncertainty but do not satisfy approval on their own"
        )

    if not parsed.acceptance_tests:
        warnings.append("no acceptance_tests recorded yet")
    if not parsed.references:
        warnings.append("no references recorded yet")
    if not parsed.forbidden_proxies:
        warnings.append("no forbidden_proxies recorded yet")
    if guidance_signal_count == 0:
        errors.append("context_intake must not be empty")

    return ProjectContractValidationResult(
        valid=not errors,
        errors=dedupe_preserve_order(errors),
        warnings=dedupe_preserve_order(warnings),
        question=question or None,
        decisive_target_count=decisive_target_count,
        guidance_signal_count=guidance_signal_count,
        reference_count=reference_count,
        mode=mode,
    )
