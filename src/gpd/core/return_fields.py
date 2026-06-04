"""Pure metadata registry for top-level ``gpd_return`` fields.

This module intentionally does not import the typed return envelope.  The
envelope remains the wire-format and validation authority; this registry holds
field metadata that consumers can use without duplicating extension allowlists
or status-applicability logic.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

__all__ = [
    "RETURN_EXTENSION_FIELD_SPECS",
    "RETURN_FIELD_DEFAULTS",
    "RETURN_FIELD_VALIDATION_OWNERS",
    "ReturnFieldAllowedSource",
    "ReturnFieldSource",
    "ReturnFieldSpec",
    "allowed_return_extension_fields",
    "has_return_field_default",
    "known_return_field_names",
    "return_field_default",
    "return_field_registry_payload",
    "return_field_source",
    "return_field_status_allowed",
    "return_field_status_applicability",
    "return_field_validation_owner",
    "return_fields_allowed_for_status",
    "status_restricted_return_fields",
]

ReturnFieldSource = Literal["base", "extension"]
ReturnFieldAllowedSource = Literal["base", "extension", "unknown"]


@dataclass(frozen=True)
class ReturnFieldSpec:
    """Metadata for a top-level ``gpd_return`` field."""

    name: str
    source: ReturnFieldSource
    status_applicability: tuple[str, ...] | None = None
    role_visibility: tuple[str, ...] = ()
    validation_owner: str = "return_contract"
    default_available: bool = False
    description: str = ""


_RETURN_FIELD_DEFAULT_SEEDS = {
    "approximations": (),
    "approved_plans": (),
    "assumptions_made": (),
    "blocked_plans": (),
    "blockers": (),
    "checks_performed": (),
    "confidence": "unassessed",
    "confidence_summary": {},
    "context_pressure": "normal",
    "conventions": (),
    "categories_defined": (),
    "depth_profile": {},
    "dimensions_checked": (),
    "dimensions_evaluated": (),
    "duration_seconds": 0,
    "field_assessment": "pending",
    "focus": "unspecified",
    "citations_added": 0,
    "cross_convention_checks": (),
    "equations_added": 0,
    "figures_added": 0,
    "framing_strategy": "unspecified",
    "issues_found": (),
    "journal_calibration": "unspecified",
    "likely_objections": (),
    "likely_questions": (),
    "major_issues": (),
    "minor_issues": (),
    "papers_reviewed": 0,
    "patch_summary": {},
    "persona_calibration_confidence": "low",
    "persona_confidence": "low",
    "persona_fit_confidence": "low",
    "phase_checked": "unknown",
    "plans": (),
    "plans_created": 0,
    "privacy_notes": (),
    "privacy_summary": {},
    "recommendation": "needs_review",
    "reference_maps": (),
    "rejected_or_deferred": (),
    "ranked_directions": (),
    "revision_guidance": (),
    "revision_round": 1,
    "roadmap_updates": (),
    "score": "unscored",
    "section_name": "unspecified",
    "tasks_completed": 0,
    "tasks_total": 0,
    "skipped_or_compressed": (),
    "standards_to_satisfy": (),
    "summary": "not summarized",
    "test_values_defined": (),
    "verification_status": "gaps_found",
    "waves": (),
}

RETURN_FIELD_DEFAULTS: Mapping[str, object] = MappingProxyType(_RETURN_FIELD_DEFAULT_SEEDS)
"""Conservative default-value seeds for skeleton/profile consumers."""

_BASE_FIELD_VALIDATION_OWNERS = {
    "status": "return_contract.status",
    "files_written": "return_contract.string_list",
    "issues": "return_contract.string_list",
    "next_actions": "return_contract.string_list",
    "tasks_completed": "return_contract.integer",
    "tasks_total": "return_contract.integer",
    "duration_seconds": "return_contract.scalar",
    "phase": "return_contract.scalar",
    "plan": "return_contract.scalar",
    "design_file": "return_contract.scalar",
    "field_assessment": "return_contract.scalar",
    "state_updates": "return_contract.yaml_mapping",
    "contract_updates": "return_contract.yaml_mapping",
    "decisions": "return_contract.yaml_sequence",
    "approved_plans": "return_contract.string_list",
    "blocked_plans": "return_contract.string_list",
    "blockers": "return_contract.yaml_sequence",
    "continuation_update": "return_contract.continuation_update",
    "checkpoint_intent": "checkpoint_intent",
    "conventions_used": "return_contract.yaml_mapping",
    "checkpoint_hashes": "return_contract.checkpoint_hashes",
}

_EXTENSION_VALIDATION_OWNER = "return_contract.extension_yaml_native"

_RETURN_EXTENSION_FIELD_NAMES = (
    "affected_quantities",
    "approximations",
    "assumptions_made",
    "categories_defined",
    "capsule_role_used",
    "category",
    "change_id",
    "checks_performed",
    "citations_added",
    "confidence",
    "confidence_summary",
    "conflicts",
    "context_pressure",
    "conventions",
    "conventions_file",
    "conversion_table",
    "cross_convention_checks",
    "depth_profile",
    "dimensions_checked",
    "dimensions_evaluated",
    "downstream_phases_flagged",
    "entries_added",
    "equations_added",
    "expanded_for_user",
    "explanation_sections",
    "figures_added",
    "focus",
    "framing_strategy",
    "integrity_gate",
    "issues_found",
    "journal_calibration",
    "likely_objections",
    "likely_questions",
    "major_issues",
    "minor_issues",
    "new_value",
    "old_value",
    "papers_reviewed",
    "patch_summary",
    "persona_calibration_confidence",
    "persona_confidence",
    "persona_fit_confidence",
    "phase_checked",
    "phases_created",
    "plans",
    "plans_created",
    "privacy_notes",
    "privacy_summary",
    "recommendation",
    "reference_maps",
    "rejected_or_deferred",
    "ranked_directions",
    "revision_guidance",
    "revision_round",
    "roadmap_updates",
    "score",
    "section_name",
    "session_file",
    "severity",
    "skipped_or_compressed",
    "standards_to_satisfy",
    "summary",
    "test_values_defined",
    "verification_status",
    "waves",
)

RETURN_EXTENSION_FIELD_SPECS: Mapping[str, ReturnFieldSpec] = MappingProxyType(
    {
        field_name: ReturnFieldSpec(
            name=field_name,
            source="extension",
            validation_owner=_EXTENSION_VALIDATION_OWNER,
            default_available=field_name in _RETURN_FIELD_DEFAULT_SEEDS,
        )
        for field_name in _RETURN_EXTENSION_FIELD_NAMES
    }
)
"""Extension-field specs accepted as top-level ``gpd_return`` metadata."""

RETURN_FIELD_VALIDATION_OWNERS: Mapping[str, str] = MappingProxyType(
    {
        **_BASE_FIELD_VALIDATION_OWNERS,
        **{field_name: spec.validation_owner for field_name, spec in RETURN_EXTENSION_FIELD_SPECS.items()},
    }
)
"""Registry-level validation owner labels for known return fields."""


def allowed_return_extension_fields() -> frozenset[str]:
    """Return the extension field names accepted by the canonical envelope."""

    return frozenset(RETURN_EXTENSION_FIELD_SPECS)


def known_return_field_names(base_fields: Iterable[str]) -> frozenset[str]:
    """Return model field names plus registered extensions."""

    return frozenset(base_fields) | allowed_return_extension_fields()


def return_field_source(
    field_name: str,
    *,
    base_fields: Iterable[str],
) -> ReturnFieldAllowedSource:
    """Classify where a top-level return field is known from."""

    if field_name in set(base_fields):
        return "base"
    if field_name in RETURN_EXTENSION_FIELD_SPECS:
        return "extension"
    return "unknown"


def status_restricted_return_fields(status_contracts: Mapping[str, object]) -> frozenset[str]:
    """Return fields whose legality is described by status contracts."""

    return frozenset(
        field_name for contract in status_contracts.values() for field_name in _contract_structured_fields(contract)
    )


def return_field_status_allowed(
    field_name: str,
    status: str,
    *,
    base_fields: Iterable[str],
    status_contracts: Mapping[str, object],
) -> bool:
    """Return whether a known field is legal for a normalized status."""

    base_field_tuple = tuple(base_fields)
    if status not in status_contracts:
        return False
    source = return_field_source(field_name, base_fields=base_field_tuple)
    if source == "unknown":
        return False
    spec = RETURN_EXTENSION_FIELD_SPECS.get(field_name)
    if spec is not None and spec.status_applicability is not None:
        return status in spec.status_applicability
    if field_name in status_restricted_return_fields(status_contracts):
        return field_name in _contract_structured_fields(status_contracts[status])
    return True


def return_field_status_applicability(
    field_name: str,
    *,
    base_fields: Iterable[str],
    status_contracts: Mapping[str, object],
    all_statuses: Iterable[str],
) -> tuple[str, ...]:
    """Return statuses that allow a known field, or ``()`` for unknown fields."""

    base_field_tuple = tuple(base_fields)
    source = return_field_source(field_name, base_fields=base_field_tuple)
    if source == "unknown":
        return ()
    return tuple(
        status
        for status in all_statuses
        if return_field_status_allowed(
            field_name,
            status,
            base_fields=base_field_tuple,
            status_contracts=status_contracts,
        )
    )


def return_fields_allowed_for_status(
    status: str,
    *,
    base_fields: Iterable[str],
    status_contracts: Mapping[str, object],
) -> tuple[str, ...]:
    """List known top-level fields legal for a status in stable render order."""

    base_field_tuple = tuple(base_fields)
    fields: list[str] = []
    for field_name in base_field_tuple:
        if return_field_status_allowed(
            field_name,
            status,
            base_fields=base_field_tuple,
            status_contracts=status_contracts,
        ):
            fields.append(field_name)
    for field_name in sorted(RETURN_EXTENSION_FIELD_SPECS):
        if return_field_status_allowed(
            field_name,
            status,
            base_fields=base_field_tuple,
            status_contracts=status_contracts,
        ):
            fields.append(field_name)
    return tuple(fields)


def return_field_validation_owner(field_name: str) -> str | None:
    """Return the registry label for the component that validates a field."""

    return RETURN_FIELD_VALIDATION_OWNERS.get(field_name)


def has_return_field_default(field_name: str) -> bool:
    """Return whether a conservative default can be produced for a field."""

    return field_name in {"phase", "plan"} or field_name in RETURN_FIELD_DEFAULTS


def return_field_default(field_name: str, *, phase: str | None = None, plan: str | None = None) -> object:
    """Return a copy-safe conservative default for a return field."""

    if field_name == "phase":
        return phase or "unknown"
    if field_name == "plan":
        return plan or "unknown"
    try:
        value = RETURN_FIELD_DEFAULTS[field_name]
    except KeyError as exc:
        raise KeyError(f"no conservative default registered for gpd_return field '{field_name}'") from exc
    return _copy_default_value(value)


def return_field_registry_payload(
    *,
    base_fields: Iterable[str],
    status_contracts: Mapping[str, object],
    all_statuses: Iterable[str],
) -> dict[str, object]:
    """Return a JSON-like registry snapshot for compatibility consumers."""

    base_field_tuple = tuple(base_fields)
    status_tuple = tuple(all_statuses)
    known_fields = tuple(
        field_name
        for field_name in (*base_field_tuple, *sorted(RETURN_EXTENSION_FIELD_SPECS))
        if return_field_source(field_name, base_fields=base_field_tuple) != "unknown"
    )
    return {
        "known_fields": list(known_fields),
        "extension_fields": sorted(RETURN_EXTENSION_FIELD_SPECS),
        "status_allowed_fields": {
            status: list(
                return_fields_allowed_for_status(
                    status,
                    base_fields=base_field_tuple,
                    status_contracts=status_contracts,
                )
            )
            for status in status_tuple
        },
        "validation_owners": {
            field_name: owner
            for field_name in known_fields
            if (owner := return_field_validation_owner(field_name)) is not None
        },
        "default_fields": sorted(field_name for field_name in known_fields if has_return_field_default(field_name)),
    }


def _contract_structured_fields(contract: object) -> tuple[str, ...]:
    if isinstance(contract, Mapping):
        raw_fields = contract.get("structured_fields", ())
    else:
        raw_fields = getattr(contract, "structured_fields", ())
    if raw_fields is None:
        return ()
    return tuple(str(field_name) for field_name in raw_fields)


def _copy_default_value(value: object) -> object:
    if isinstance(value, tuple):
        return list(value)
    return copy.deepcopy(value)
