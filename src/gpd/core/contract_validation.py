"""Validation helpers for contract-backed workflow gates."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
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
)

__all__ = ["ProjectContractValidationResult", "salvage_project_contract", "validate_project_contract"]


_ANCHOR_UNKNOWN_DIRECT_PATTERNS = (
    re.compile(r"\bneed(?:s)? grounding\b"),
    re.compile(r"\b(?:(?:decisive|benchmark|comparison)\s+)?target not (?:yet )?chosen\b"),
)
_ANCHOR_UNKNOWN_TOPIC_PATTERNS = (
    re.compile(r"\banchor\b"),
    re.compile(r"\bbenchmark\b"),
    re.compile(r"\bbaseline\b"),
    re.compile(r"\bcomparison source\b"),
    re.compile(r"\bdecisive source\b"),
    re.compile(r"\bground[- ]truth\b"),
    re.compile(r"\bsmoking gun\b"),
)
_ANCHOR_UNKNOWN_BLOCKER_PATTERNS = (
    re.compile(r"\bunknown\b"),
    re.compile(r"\bundecided\b"),
    re.compile(r"\bunclear\b"),
    re.compile(r"\bmissing\b"),
    re.compile(r"\bnot (?:yet )?established\b"),
    re.compile(r"\bnot (?:yet )?selected\b"),
    re.compile(r"\bstill to identify\b"),
    re.compile(r"\btbd\b"),
    re.compile(r"\bto be determined\b"),
    re.compile(r"\bmust establish\b"),
    re.compile(r"\bestablish later\b"),
    re.compile(r"\bno\b.+\byet\b"),
)
_ANCHOR_UNKNOWN_QUESTION_PATTERNS = (
    re.compile(r"^\s*(?:which|what)\b"),
    re.compile(r"\?$"),
)
_ANCHOR_UNKNOWN_SELECTION_PATTERNS = (
    re.compile(r"\bserve as\b"),
    re.compile(r"\btreat as\b"),
    re.compile(r"\buse as\b"),
    re.compile(r"\bchoose\b"),
    re.compile(r"\bselect\b"),
    re.compile(r"\bpick\b"),
    re.compile(r"\bdecisive\b"),
)
_USER_ASSERTED_ANCHOR_PLACEHOLDER_PATTERNS = (
    re.compile(r"^\s*(?:tbd|todo|unknown|unclear|none|n/?a|placeholder)\s*$"),
    re.compile(r"\btbd\b"),
    re.compile(r"\btodo\b"),
    re.compile(r"\bplaceholder\b"),
    re.compile(r"\bto be determined\b"),
)
_REFERENCE_LOCATOR_PLACEHOLDER_PATTERNS = (
    re.compile(r"^\s*(?:tbd|todo|unknown|unclear|none|n/?a|placeholder)\s*$"),
    re.compile(r"\btbd\b"),
    re.compile(r"\btodo\b"),
    re.compile(r"\bunknown\b"),
    re.compile(r"\bunclear\b"),
    re.compile(r"\bplaceholder\b"),
    re.compile(r"\bto be determined\b"),
)
_CONCRETE_TEXT_ANCHOR_PATTERNS = (
    re.compile(r"\bbenchmark\b"),
    re.compile(r"\bbaseline\b"),
    re.compile(r"\breference\b"),
    re.compile(r"\bpaper\b"),
    re.compile(r"\bdataset\b"),
    re.compile(r"\bnotebook\b"),
    re.compile(r"\bfigure\b"),
    re.compile(r"\btable\b"),
    re.compile(r"\bcurve\b"),
    re.compile(r"\bplot\b"),
    re.compile(r"\bresult\b"),
    re.compile(r"\boutput\b"),
    re.compile(r"\bderivation\b"),
    re.compile(r"\banalysis\b"),
    re.compile(r"\bliterature\b"),
    re.compile(r"\bpublished\b"),
    re.compile(r"\barxiv\b"),
    re.compile(r"\bdoi\b"),
    re.compile(r"\bcritical\b"),
    re.compile(r"\blimit\b"),
    re.compile(r"\blimiting\b"),
    re.compile(r"\basymptotic\b"),
    re.compile(r"\bobservable\b"),
    re.compile(r"\bcomparison\b"),
    re.compile(r"\banchor\b"),
)
_REFERENCE_LOCATOR_CONCRETE_PATTERNS = (
    re.compile(r"\b(?:doi\s*[:/]|https?://(?:doi\.org/|arxiv\.org/abs/)|arxiv\s*:)\S+"),
    re.compile(r"\b(?:fig(?:ure)?|table|eq(?:uation)?|section|sec\.?|chapter|ch\.?|appendix)\.?\s*\d+[a-z]?\b"),
    re.compile(r"\b(?:19|20)\d{2}\b"),
)
_CONCRETE_TEXT_ATTACHMENT_PATTERNS = (
    re.compile(r"\bfrom\b"),
    re.compile(r"\bvia\b"),
    re.compile(r"\busing\b"),
    re.compile(r"\bagainst\b"),
    re.compile(r"\bin\b"),
    re.compile(r"\bon\b"),
    re.compile(r"\bof\b"),
)
_PROJECT_ARTIFACT_PATH_PATTERNS = (
    re.compile(r"[\\/]+"),
    re.compile(r"^(?:\.{1,2}|~)(?:[\\/]|$)"),
    re.compile(r"\.[A-Za-z0-9]{1,8}$"),
)
_RECOVERABLE_SCHEMA_WARNING_PATTERNS = (
    re.compile(r"^.+: Extra inputs are not permitted$"),
)
_DEFAULTABLE_SINGLETON_SCHEMA_WARNING_PATTERNS = (
    re.compile(r"^(?:context_intake|approach_policy|uncertainty_markers) must be an object, not .+$"),
)
_AUTHORITATIVE_SCALAR_FINDING_PATTERNS = (
    re.compile(r"^schema_version must be the integer 1$"),
    re.compile(r"^schema_version: Input should be 1$"),
    re.compile(r"^.+\.must_surface must be a boolean$"),
)
_TOP_LEVEL_LIST_FIELDS = (
    "observables",
    "claims",
    "deliverables",
    "acceptance_tests",
    "references",
    "forbidden_proxies",
    "links",
)
_SCOPE_LIST_FIELDS = ("in_scope", "out_of_scope", "unresolved_questions")
_CONTEXT_INTAKE_LIST_FIELDS = (
    "must_read_refs",
    "must_include_prior_outputs",
    "user_asserted_anchors",
    "known_good_baselines",
    "context_gaps",
    "crucial_inputs",
)
_APPROACH_POLICY_LIST_FIELDS = (
    "formulations",
    "allowed_estimator_families",
    "forbidden_estimator_families",
    "allowed_fit_families",
    "forbidden_fit_families",
    "stop_and_rethink_conditions",
)
_CLAIM_LIST_FIELDS = ("observables", "deliverables", "acceptance_tests", "references")
_DELIVERABLE_LIST_FIELDS = ("must_contain",)
_ACCEPTANCE_TEST_LIST_FIELDS = ("evidence_required",)
_REFERENCE_LIST_FIELDS = ("aliases", "applies_to", "carry_forward_to", "required_actions")
_LINK_LIST_FIELDS = ("verified_by",)
_UNCERTAINTY_MARKER_LIST_FIELDS = (
    "weakest_anchors",
    "unvalidated_assumptions",
    "competing_explanations",
    "disconfirming_observations",
)


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


def _dedupe_findings(findings: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        if finding in seen:
            continue
        seen.add(finding)
        deduped.append(finding)
    return deduped


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

    return f"{location}: {message}"


def _schema_error_result(
    exc: PydanticValidationError,
    *,
    mode: Literal["draft", "approved"],
) -> ProjectContractValidationResult:
    """Convert Pydantic validation errors into a machine-readable contract result."""

    errors: list[str] = []
    seen: set[str] = set()
    for error in exc.errors():
        formatted = _format_schema_error(error)
        if formatted in seen:
            continue
        seen.add(formatted)
        errors.append(formatted)
    return ProjectContractValidationResult(valid=False, errors=errors, mode=mode)


def _sanitize_contract_scalars(
    value: object,
    *,
    path_prefix: str = "",
    errors: list[str] | None = None,
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
                if type(raw_item) is not int:
                    sink.append("schema_version must be the integer 1")
                    continue
                if raw_item != 1:
                    sink.append("schema_version: Input should be 1")
                    continue
                cleaned[raw_key] = raw_item
                continue

            if re.fullmatch(r"references\.\d+\.must_surface", location):
                if type(raw_item) is not bool:
                    sink.append(f"{location} must be a boolean")
                    continue
                cleaned[raw_key] = raw_item
                continue

            cleaned[raw_key] = _sanitize_contract_scalars(
                raw_item,
                path_prefix=location,
                errors=sink,
            )
        return cleaned

    if isinstance(value, list):
        return [
            _sanitize_contract_scalars(
                item,
                path_prefix=f"{path_prefix}.{index}" if path_prefix else str(index),
                errors=sink,
            )
            for index, item in enumerate(value)
        ]

    return copy.deepcopy(value)


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
        errors.append(f"{location}: Extra inputs are not permitted")
        cleaned.pop(key, None)
    return cleaned


def _salvage_model_mapping(
    value: object,
    *,
    path_prefix: str,
    model: type[BaseModel],
    errors: list[str],
    default_value: dict[str, object] | None = None,
) -> dict[str, object] | None:
    if not isinstance(value, dict):
        actual_type = type(value).__name__
        if default_value is not None:
            errors.append(f"{path_prefix} must be an object, not {actual_type}")
            return copy.deepcopy(default_value)
        errors.append(f"{path_prefix} must be an object, not {actual_type}")
        return None

    cleaned = _strip_unknown_model_keys(value, path_prefix=path_prefix, model=model, errors=errors)
    while True:
        try:
            return model.model_validate(cleaned).model_dump()
        except PydanticValidationError as exc:
            progress = False
            for error in exc.errors():
                loc = tuple(error.get("loc", ()))
                if not loc:
                    continue
                key = str(loc[0])
                field = model.model_fields.get(key)
                if field is None:
                    continue
                formatted = _format_schema_error(
                    {
                        "loc": (path_prefix, *loc),
                        "msg": error.get("msg"),
                        "input": error.get("input"),
                    }
                )
                if field.is_required():
                    errors.append(formatted)
                    return copy.deepcopy(default_value) if default_value is not None else None
                if key in cleaned:
                    errors.append(formatted)
                    cleaned.pop(key, None)
                    progress = True
            if not progress:
                return copy.deepcopy(default_value) if default_value is not None else None


def _salvage_contract_collection(
    value: object,
    *,
    field_name: str,
    item_model: type[BaseModel],
    errors: list[str],
) -> list[dict[str, object]]:
    path_prefix = field_name
    if not isinstance(value, list):
        errors.append(f"{path_prefix} must be a list, not {type(value).__name__}")
        return []

    normalized_items: list[dict[str, object]] = []
    for index, item in enumerate(value):
        item_prefix = f"{path_prefix}.{index}"
        if not isinstance(item, dict):
            errors.append(f"{item_prefix} must be an object, not {type(item).__name__}")
            continue
        normalized = _salvage_model_mapping(
            item,
            path_prefix=item_prefix,
            model=item_model,
            errors=errors,
        )
        if normalized is not None:
            normalized_items.append(normalized)
    return normalized_items


def salvage_project_contract(contract: dict[str, object]) -> tuple[ResearchContract | None, list[str]]:
    errors: list[str] = []
    scalar_sanitized = _sanitize_contract_scalars(contract, errors=errors)
    if not isinstance(scalar_sanitized, dict):
        return None, errors

    working = _strip_unknown_model_keys(scalar_sanitized, path_prefix="", model=ResearchContract, errors=errors)
    normalized_contract = copy.deepcopy(working)

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
        normalized_contract[field_name] = _salvage_contract_collection(
            normalized_contract.get(field_name),
            field_name=field_name,
            item_model=item_model,
            errors=errors,
        )

    scope = _salvage_model_mapping(
        normalized_contract.get("scope"),
        path_prefix="scope",
        model=ContractScope,
        errors=errors,
    )
    if scope is None:
        return None, errors
    normalized_contract["scope"] = scope

    defaultable_singletons: dict[str, type[BaseModel]] = {
        "context_intake": ContractContextIntake,
        "approach_policy": ContractApproachPolicy,
        "uncertainty_markers": ContractUncertaintyMarkers,
    }
    for field_name, model in defaultable_singletons.items():
        if field_name not in normalized_contract:
            continue
        default_value = model.model_validate({}).model_dump()
        normalized_contract[field_name] = _salvage_model_mapping(
            normalized_contract.get(field_name),
            path_prefix=field_name,
            model=model,
            errors=errors,
            default_value=default_value,
        )

    if "schema_version" in normalized_contract:
        try:
            normalized_contract["schema_version"] = ResearchContract.model_validate(
                {"scope": scope, "schema_version": normalized_contract["schema_version"]}
            ).schema_version
        except PydanticValidationError:
            errors.append("schema_version: Input should be 1")
            normalized_contract.pop("schema_version", None)

    try:
        return ResearchContract.model_validate(normalized_contract), errors
    except PydanticValidationError as exc:
        for error in exc.errors():
            formatted = _format_schema_error(error)
            if formatted not in errors:
                errors.append(formatted)
        return None, errors


def _split_project_contract_schema_findings(
    errors: list[str],
    *,
    allow_singleton_defaults: bool = True,
) -> tuple[list[str], list[str]]:
    """Partition salvage findings into recoverable warnings and blocking errors."""

    recoverable: list[str] = []
    blocking: list[str] = []
    recoverable_patterns = _RECOVERABLE_SCHEMA_WARNING_PATTERNS
    if allow_singleton_defaults:
        recoverable_patterns += _DEFAULTABLE_SINGLETON_SCHEMA_WARNING_PATTERNS
    for error in errors:
        if any(pattern.fullmatch(error) for pattern in recoverable_patterns):
            recoverable.append(error)
        else:
            blocking.append(error)
    return recoverable, blocking


def _has_authoritative_scalar_schema_findings(errors: list[str]) -> bool:
    """Return whether salvage findings touched authoritative scalar fields."""

    return any(
        pattern.fullmatch(error) for error in errors for pattern in _AUTHORITATIVE_SCALAR_FINDING_PATTERNS
    )


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

    _check_mapping_lists(contract, path_prefix="", field_names=_TOP_LEVEL_LIST_FIELDS)
    _check_mapping_lists(contract.get("scope"), path_prefix="scope", field_names=_SCOPE_LIST_FIELDS)
    _check_mapping_lists(
        contract.get("context_intake"),
        path_prefix="context_intake",
        field_names=_CONTEXT_INTAKE_LIST_FIELDS,
    )
    _check_mapping_lists(
        contract.get("approach_policy"),
        path_prefix="approach_policy",
        field_names=_APPROACH_POLICY_LIST_FIELDS,
    )
    _check_mapping_lists(
        contract.get("uncertainty_markers"),
        path_prefix="uncertainty_markers",
        field_names=_UNCERTAINTY_MARKER_LIST_FIELDS,
    )
    _check_collection_item_lists("claims", _CLAIM_LIST_FIELDS)
    _check_collection_item_lists("deliverables", _DELIVERABLE_LIST_FIELDS)
    _check_collection_item_lists("acceptance_tests", _ACCEPTANCE_TEST_LIST_FIELDS)
    _check_collection_item_lists("references", _REFERENCE_LIST_FIELDS)
    _check_collection_item_lists("links", _LINK_LIST_FIELDS)

    return _dedupe_findings(errors)


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

def _is_project_artifact_path(value: str) -> bool:
    """Return whether *value* names a concrete prior-output artifact path."""

    candidate = value.strip()
    if not candidate:
        return False
    return any(pattern.search(candidate) for pattern in _PROJECT_ARTIFACT_PATH_PATTERNS)


def _is_concrete_text_grounding(value: str) -> bool:
    """Return whether *value* names a substantive text anchor rather than filler."""

    lowered = value.casefold().strip()
    if not lowered:
        return False
    if any(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_DIRECT_PATTERNS):
        return False
    if any(pattern.search(lowered) for pattern in _USER_ASSERTED_ANCHOR_PLACEHOLDER_PATTERNS):
        return False
    if any(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_BLOCKER_PATTERNS):
        return False
    if (
        all(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_QUESTION_PATTERNS)
        and any(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_SELECTION_PATTERNS)
    ):
        return False
    words = [word for word in re.split(r"\s+", lowered) if word]
    if len(words) < 3:
        return False
    return any(pattern.search(lowered) for pattern in _CONCRETE_TEXT_ANCHOR_PATTERNS)


def _is_concrete_reference_locator(value: str) -> bool:
    """Return whether *value* names a concrete reference locator rather than a placeholder."""

    lowered = value.casefold().strip()
    if not lowered:
        return False
    if any(pattern.search(lowered) for pattern in _REFERENCE_LOCATOR_CONCRETE_PATTERNS):
        return True
    if re.search(r"\b(?:et al\.|journal|proceedings?|conference|chapter|sec\.?|section|table|fig(?:ure)?|eq(?:uation)?)\b", lowered) and re.search(
        r"\b\d+\b", lowered
    ):
        return True
    if any(pattern.search(lowered) for pattern in _PROJECT_ARTIFACT_PATH_PATTERNS):
        candidate = Path(value.strip()).expanduser()
        if not candidate.is_absolute() and len(candidate.parts) > 1 and ".." not in candidate.parts:
            return True
        return False
    return False


def _is_placeholder_reference_locator(value: str) -> bool:
    """Return whether *value* is a placeholder locator that cannot ground approval."""

    lowered = value.casefold().strip()
    if not lowered:
        return True
    return any(pattern.search(lowered) for pattern in _REFERENCE_LOCATOR_PLACEHOLDER_PATTERNS)


def _has_concrete_grounding_entries(values: list[str], *, field_name: str) -> bool:
    """Return whether any grounding entry is concrete for the requested field."""

    if field_name == "must_include_prior_outputs":
        return any(_is_project_artifact_path(value) for value in values)
    if field_name in {"user_asserted_anchors", "known_good_baselines"}:
        return any(_is_concrete_text_grounding(value) for value in values)
    raise ValueError(f"Unsupported grounding field {field_name!r}")


def _has_concrete_must_surface_reference(contract: ResearchContract) -> bool:
    """Return whether the contract includes a concrete must_surface reference."""

    for reference in contract.references:
        if reference.must_surface and _is_concrete_reference_locator(reference.locator):
            return True
    return False


def _has_approved_grounding_signal(contract: ResearchContract) -> bool:
    """Return whether approved-mode grounding is explicitly captured.

    Prior outputs count here because the new-project scoping gate allows a
    concrete carry-forward output to serve as the grounding anchor for early
    planning, even before a literature benchmark or baseline is confirmed.
    """

    return any(
        (
            _has_concrete_must_surface_reference(contract),
            _has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
            ),
        )
    )


def _has_non_reference_grounding_signal(contract: ResearchContract) -> bool:
    """Return whether grounding is explicitly supplied outside references."""

    return any(
        (
            _has_concrete_grounding_entries(
                contract.context_intake.must_include_prior_outputs,
                field_name="must_include_prior_outputs",
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.user_asserted_anchors,
                field_name="user_asserted_anchors",
            ),
            _has_concrete_grounding_entries(
                contract.context_intake.known_good_baselines,
                field_name="known_good_baselines",
            ),
        )
    )


def validate_project_contract(
    contract: ResearchContract | dict[str, object],
    *,
    mode: Literal["draft", "approved"] = "draft",
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
        parsed = contract
        schema_warnings: list[str] = []
        schema_errors: list[str] = []
    else:
        if not isinstance(contract, dict):
            return ProjectContractValidationResult(
                valid=False,
                errors=["project contract must be a JSON object"],
                mode=mode,
            )
        list_shape_drift_errors = _collect_list_shape_drift_errors(contract)
        parsed, schema_findings = salvage_project_contract(contract)
        schema_warnings, schema_errors = _split_project_contract_schema_findings(
            schema_findings,
            allow_singleton_defaults=False,
        )
        schema_warnings = _dedupe_findings([*schema_warnings, *list_shape_drift_errors])
        schema_errors = _dedupe_findings(schema_errors)
        if parsed is None:
            if schema_errors:
                return ProjectContractValidationResult(valid=False, errors=schema_errors, mode=mode)
            try:
                parsed = ResearchContract.model_validate(contract)
            except PydanticValidationError as exc:
                return _schema_error_result(exc, mode=mode)
    errors: list[str] = list(schema_errors)
    warnings: list[str] = list(schema_warnings)

    question = parsed.scope.question.strip()
    decisive_target_count = len(parsed.observables) + len(parsed.claims) + len(parsed.deliverables)
    guidance_signal_count = sum(
        bool(items)
        for items in (
            parsed.context_intake.must_read_refs,
            parsed.context_intake.must_include_prior_outputs,
            parsed.context_intake.user_asserted_anchors,
            parsed.context_intake.known_good_baselines,
            parsed.context_intake.context_gaps,
            parsed.context_intake.crucial_inputs,
        )
    )

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

    has_non_reference_grounding = _has_non_reference_grounding_signal(parsed)

    if parsed.references and not any(reference.must_surface for reference in parsed.references):
        finding = "references must include at least one must_surface=true anchor"
        if mode == "approved" and not has_non_reference_grounding:
            errors.append(finding)
        else:
            warnings.append(finding)

    if mode == "approved" and decisive_target_count > 0 and not _has_approved_grounding_signal(parsed):
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
        warnings.append(
            "no user guidance signals recorded yet (must_read_refs, prior outputs, anchors, baselines, gaps, or crucial inputs)"
        )

    return ProjectContractValidationResult(
        valid=not errors,
        errors=_dedupe_findings(errors),
        warnings=_dedupe_findings(warnings),
        question=question or None,
        decisive_target_count=decisive_target_count,
        guidance_signal_count=guidance_signal_count,
        reference_count=len(parsed.references),
        mode=mode,
    )
