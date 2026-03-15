"""Validation helpers for contract-backed workflow gates."""

from __future__ import annotations

import copy
import re
from collections import Counter
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
)

__all__ = ["ProjectContractValidationResult", "salvage_project_contract", "validate_project_contract"]


_APPROVED_REFERENCE_ROLES = frozenset({"benchmark", "definition", "method", "must_consider"})
_ANCHOR_UNKNOWN_TOPIC_PATTERNS = (
    re.compile(r"\banchor\b"),
    re.compile(r"\bbenchmark\b"),
    re.compile(r"\bbaseline\b"),
    re.compile(r"\breference\b"),
    re.compile(r"\bground[- ]truth\b"),
    re.compile(r"\bsmoking gun\b"),
)
_ANCHOR_UNKNOWN_BLOCKER_PATTERNS = (
    re.compile(r"\bunknown\b"),
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


def _append_duplicates(errors: list[str], kind: str, ids: list[str]) -> None:
    for item_id, count in Counter(ids).items():
        if count > 1:
            errors.append(f"duplicate {kind} id {item_id}")


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
    working = _strip_unknown_model_keys(contract, path_prefix="", model=ResearchContract, errors=errors)
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


def _light_contract_consistency_errors(contract: ResearchContract) -> list[str]:
    """Return cross-link errors without forcing mature-phase completeness."""

    errors: list[str] = []
    _append_duplicates(errors, "claim", [claim.id for claim in contract.claims])
    _append_duplicates(errors, "deliverable", [deliverable.id for deliverable in contract.deliverables])
    _append_duplicates(errors, "acceptance_test", [test.id for test in contract.acceptance_tests])
    _append_duplicates(errors, "reference", [reference.id for reference in contract.references])
    _append_duplicates(errors, "forbidden_proxy", [proxy.id for proxy in contract.forbidden_proxies])
    _append_duplicates(errors, "link", [link.id for link in contract.links])

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


def _has_explicit_anchor_unknown(contract: ResearchContract) -> bool:
    """Return whether the contract explicitly records that anchors are still unknown."""

    candidates = [*contract.scope.unresolved_questions, *contract.context_intake.context_gaps]
    for item in candidates:
        if not isinstance(item, str):
            continue
        lowered = item.casefold()
        if not any(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_TOPIC_PATTERNS):
            continue
        if any(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_BLOCKER_PATTERNS):
            return True
        if all(pattern.search(lowered) for pattern in _ANCHOR_UNKNOWN_QUESTION_PATTERNS):
            return True
    return False


def _has_anchor_like_reference(contract: ResearchContract) -> bool:
    """Return whether the contract includes a reference that can ground approved mode."""

    reference_ids = {reference.id for reference in contract.references}
    linked_reference_ids = set(contract.context_intake.must_read_refs)
    linked_reference_ids.update(reference_id for claim in contract.claims for reference_id in claim.references)
    linked_reference_ids.update(
        evidence_id
        for test in contract.acceptance_tests
        for evidence_id in test.evidence_required
        if evidence_id in reference_ids
    )

    for reference in contract.references:
        role = reference.role.casefold().strip()
        if role == "background":
            continue
        if (
            reference.id in linked_reference_ids
            or reference.kind == "user_anchor"
            or role in _APPROVED_REFERENCE_ROLES
            or reference.must_surface
            or bool(reference.required_actions)
            or bool(reference.applies_to)
            or bool(reference.carry_forward_to)
        ):
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
            _has_anchor_like_reference(contract),
            contract.context_intake.must_include_prior_outputs,
            contract.context_intake.user_asserted_anchors,
            contract.context_intake.known_good_baselines,
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
        schema_errors: list[str] = []
    else:
        if not isinstance(contract, dict):
            return ProjectContractValidationResult(
                valid=False,
                errors=["project contract must be a JSON object"],
                mode=mode,
            )
        parsed, schema_errors = salvage_project_contract(contract)
        if parsed is None:
            if schema_errors:
                return ProjectContractValidationResult(valid=False, errors=schema_errors, mode=mode)
            try:
                parsed = ResearchContract.model_validate(contract)
            except PydanticValidationError as exc:
                return _schema_error_result(exc, mode=mode)
    errors: list[str] = list(schema_errors)
    warnings: list[str] = []

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

    if mode == "approved" and decisive_target_count > 0 and not (
        _has_approved_grounding_signal(parsed) or _has_explicit_anchor_unknown(parsed)
    ):
        errors.append(
            "approved project contract requires at least one concrete anchor/reference/prior-output/baseline or an explicit 'anchor unknown' blocker"
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
        errors=errors,
        warnings=warnings,
        question=question or None,
        decisive_target_count=decisive_target_count,
        guidance_signal_count=guidance_signal_count,
        reference_count=len(parsed.references),
        mode=mode,
    )
