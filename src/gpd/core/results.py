"""Intermediate result tracking for GPD research state.

All functions operate on state dicts (the caller handles persistence).
"""

from __future__ import annotations

import logging
import secrets
import time
from collections import deque
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as _PydanticValidationError

from gpd.contracts import VerificationEvidence
from gpd.core.errors import DuplicateResultError, ResultError, ResultNotFoundError
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import phase_normalize, phase_unpad

__all__ = [
    "RESULT_FIELDS",
    "IntermediateResult",
    "ResultDeps",
    "MissingDep",
    "result_add",
    "result_list",
    "result_deps",
    "result_verify",
    "result_update",
]

logger = logging.getLogger(__name__)

# --- Models ---


class IntermediateResult(BaseModel):
    """A single intermediate result tracked in the GPD state."""

    model_config = ConfigDict(frozen=True)

    id: str
    equation: str | None = None
    description: str | None = None
    units: str | None = None
    validity: str | None = None
    phase: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    verified: bool = False
    verification_records: list[VerificationEvidence] = Field(default_factory=list)


class ResultDeps(BaseModel):
    """Dependency trace for a result."""

    model_config = ConfigDict(frozen=True)

    result: IntermediateResult
    depends_on: list[str]
    direct_deps: list[IntermediateResult | MissingDep]
    transitive_deps: list[IntermediateResult | MissingDep]


class MissingDep(BaseModel):
    """Placeholder for a dependency that wasn't found in the results list."""

    model_config = ConfigDict(frozen=True)

    id: str
    missing: bool = True


# --- Helpers ---

RESULT_FIELDS = frozenset(
    {"equation", "description", "units", "validity", "phase", "depends_on", "verified", "verification_records"}
)


def _normalize_verification_records(
    records: list[VerificationEvidence | dict[str, object]] | None,
) -> list[VerificationEvidence]:
    """Normalize a raw verification-record payload into model instances."""
    if not records:
        return []
    normalized: list[VerificationEvidence] = []
    for record in records:
        if isinstance(record, VerificationEvidence):
            normalized.append(record)
        elif isinstance(record, dict):
            try:
                normalized.append(VerificationEvidence(**record))
            except (TypeError, _PydanticValidationError) as exc:
                logger.warning("Skipping malformed verification record %r: %s", record, exc)
        else:
            logger.warning(
                "Skipping verification record of unsupported type %s: %r",
                type(record).__name__,
                record,
            )
    return normalized


def _has_verification_evidence(result: dict[str, object]) -> bool:
    """Return whether a result has any verification signal."""
    return result.get("verified") is True or bool(result.get("verification_records"))


def _int_to_base36(n: int) -> str:
    """Convert a non-negative integer to a base-36 string."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    while n > 0:
        result.append(digits[n % 36])
        n //= 36
    return "".join(reversed(result))


def _auto_generate_id(state: dict, *, phase: str | None = None) -> str:
    """Auto-generate a result ID from the target phase and existing results count.

    Format: "R-{phase}-{seq}-{suffix}" e.g. "R-03-01-lxk7a2b".

    Uses base-36 encoding for the timestamp suffix and secrets.token_hex
    for the random part to provide good collision resistance.
    """
    resolved_phase = phase
    if resolved_phase is None:
        position = state.get("position", {})
        resolved_phase = position.get("current_phase") or 0

    padded_phase = phase_normalize(str(resolved_phase))
    normalized_current = phase_unpad(str(resolved_phase))
    results = state.get("intermediate_results", [])
    existing_in_phase = [
        r
        for r in results
        if isinstance(r, dict) and r.get("phase") is not None and phase_unpad(r["phase"]) == normalized_current
    ]
    seq = len(existing_in_phase) + 1
    padded_seq = str(seq).zfill(2)

    # Base-36 timestamp suffix (last 4 chars of ms-since-epoch in base-36)
    ts_part = _int_to_base36(int(time.time() * 1000))[-4:]
    rand_part = secrets.token_hex(2)[:3]
    suffix = ts_part + rand_part

    # Use underscore for dots in phase: "01.1" -> "01_1"
    id_phase = padded_phase.replace(".", "_")
    return f"R-{id_phase}-{padded_seq}-{suffix}"


def _find_result_index(results: list, result_id: str) -> int:
    """Find a result by id. Returns the index, or -1 if not found."""
    for i, r in enumerate(results):
        if isinstance(r, dict) and r.get("id") == result_id:
            return i
    return -1


# --- Functions ---


@instrument_gpd_function("results.add")
def result_add(
    state: dict,
    *,
    equation: str | None = None,
    description: str | None = None,
    value: str | None = None,
    units: str | None = None,
    validity: str | None = None,
    phase: str | None = None,
    depends_on: list[str] | str | None = None,
    verified: bool = False,
    verification_records: list[VerificationEvidence | dict[str, object]] | None = None,
    result_id: str | None = None,
) -> IntermediateResult:
    """Add an intermediate result to state.

    Auto-generates an ID if not provided. Uses the current phase from
    state.position if phase is not specified.

    Raises ValueError for empty IDs or duplicate IDs.
    """
    if "intermediate_results" not in state:
        state["intermediate_results"] = []

    # Resolve phase from state position if not provided
    if phase is None:
        position = state.get("position", {})
        raw_phase = position.get("current_phase")
        phase = str(raw_phase) if raw_phase is not None else None

    rid = result_id or _auto_generate_id(state, phase=phase)
    if not rid or not rid.strip():
        raise ResultError(
            f"Result ID must be a non-empty string, got {rid!r}. "
            "Provide a descriptive ID (e.g., 'energy-conservation-eq') or omit it for auto-generation."
        )

    if _find_result_index(state["intermediate_results"], rid) != -1:
        raise DuplicateResultError(rid)

    if value is not None and equation is None and description is None:
        description = str(value)

    # Normalize depends_on to list
    if depends_on is None:
        deps: list[str] = []
    elif isinstance(depends_on, str):
        deps = [depends_on]
    else:
        deps = list(depends_on)

    normalized_records = _normalize_verification_records(verification_records)

    result_dict = {
        "id": rid,
        "equation": equation,
        "description": description,
        "units": units,
        "validity": validity,
        "phase": phase,
        "depends_on": deps,
        "verified": verified or bool(normalized_records),
        "verification_records": [record.model_dump() for record in normalized_records],
    }

    state["intermediate_results"].append(result_dict)
    return IntermediateResult(**result_dict)


def result_list(
    state: dict,
    *,
    phase: str | None = None,
    verified: bool | None = None,
    unverified: bool | None = None,
) -> list[IntermediateResult]:
    """List intermediate results with optional filters.

    Args:
        state: GPD state dict.
        phase: Filter to results in this phase.
        verified: If True, only return verified results.
        unverified: If True, only return unverified results.
    """
    if verified is True and unverified is True:
        raise ResultError("Cannot filter by both verified=True and unverified=True; the result would always be empty.")

    results = state.get("intermediate_results", [])

    if phase is not None:
        normalized_filter = phase_unpad(phase)
        results = [
            r
            for r in results
            if isinstance(r, dict) and r.get("phase") is not None and phase_unpad(r["phase"]) == normalized_filter
        ]
    else:
        results = [r for r in results if isinstance(r, dict)]

    if verified is True:
        results = [r for r in results if _has_verification_evidence(r)]

    if unverified is True:
        results = [r for r in results if not _has_verification_evidence(r)]

    return [IntermediateResult(**r) for r in results]


@instrument_gpd_function("results.deps")
def result_deps(state: dict, result_id: str) -> ResultDeps:
    """Trace dependencies for a result using BFS.

    Returns the result, its direct dependencies, and transitive dependencies.
    Missing dependencies are represented as MissingDep objects.

    Raises ResultNotFoundError if result_id is not found.
    """
    results = state.get("intermediate_results", [])
    idx = _find_result_index(results, result_id)
    if idx == -1:
        raise ResultNotFoundError(result_id)

    result = results[idx]

    # Build lookup map
    by_id: dict[str, dict] = {}
    for r in results:
        if isinstance(r, dict) and r.get("id"):
            by_id[r["id"]] = r

    direct_dep_ids = list(dict.fromkeys(result.get("depends_on", [])))

    # Direct dependencies
    direct_deps: list[IntermediateResult | MissingDep] = []
    for dep_id in direct_dep_ids:
        if dep_id in by_id:
            direct_deps.append(IntermediateResult(**by_id[dep_id]))
        else:
            direct_deps.append(MissingDep(id=dep_id))

    # Transitive dependencies (BFS, excluding direct deps and the result itself)
    visited: set[str] = {result_id}
    queue: deque[str] = deque(direct_dep_ids)
    transitive_deps: list[IntermediateResult | MissingDep] = []
    direct_dep_set = set(direct_dep_ids)

    while queue:
        dep_id = queue.popleft()
        if dep_id in visited:
            continue
        visited.add(dep_id)

        dep = by_id.get(dep_id)
        is_direct = dep_id in direct_dep_set

        if dep is None:
            if not is_direct:
                transitive_deps.append(MissingDep(id=dep_id))
            continue

        if not is_direct:
            transitive_deps.append(IntermediateResult(**dep))

        for sub_dep_id in dep.get("depends_on", []):
            if sub_dep_id not in visited:
                queue.append(sub_dep_id)

    return ResultDeps(
        result=IntermediateResult(**result),
        depends_on=list(direct_dep_ids),
        direct_deps=direct_deps,
        transitive_deps=transitive_deps,
    )


@instrument_gpd_function("results.verify")
def result_verify(
    state: dict,
    result_id: str,
    *,
    verifier: str | None = None,
    method: str = "manual",
    confidence: str = "medium",
    evidence_path: str | None = None,
    trace_id: str | None = None,
    commit_sha: str | None = None,
    notes: str | None = None,
    claim_id: str | None = None,
    verified_at: str | None = None,
) -> IntermediateResult:
    """Mark a result as verified.

    Raises ResultNotFoundError if result_id is not found.
    """
    _VALID_CONFIDENCE = {"high", "medium", "low", "unreliable"}
    if confidence not in _VALID_CONFIDENCE:
        raise ResultError(f"Invalid confidence {confidence!r}; expected one of {sorted(_VALID_CONFIDENCE)}")

    results = state.get("intermediate_results", [])
    idx = _find_result_index(results, result_id)
    if idx == -1:
        raise ResultNotFoundError(result_id)

    record = VerificationEvidence(
        verified_at=verified_at or datetime.now(UTC).isoformat(),
        verifier=verifier,
        method=method,
        confidence=confidence,  # type: ignore[arg-type]
        evidence_path=evidence_path,
        trace_id=trace_id,
        commit_sha=commit_sha,
        notes=notes,
        claim_id=claim_id,
    )

    raw_result = state["intermediate_results"][idx]
    records = _normalize_verification_records(raw_result.get("verification_records"))
    records.append(record)
    raw_result["verification_records"] = [entry.model_dump() for entry in records]
    raw_result["verified"] = True
    return IntermediateResult(**raw_result)


@instrument_gpd_function("results.update")
def result_update(
    state: dict,
    result_id: str,
    updates: dict[str, object] | None = None,
    **kwargs: object,
) -> tuple[list[str], IntermediateResult]:
    """Update fields on an existing result.

    Only known fields are updated. Returns (updated_field_names, updated_result).
    Raises ResultNotFoundError if result_id is not found.
    Raises ValueError if no recognized fields are provided.
    """
    updates = dict(updates or {})
    updates.update(kwargs)

    results = state.get("intermediate_results", [])
    idx = _find_result_index(results, result_id)
    if idx == -1:
        raise ResultNotFoundError(result_id)

    # Normalize depends_on to list
    if "depends_on" in updates:
        if updates["depends_on"] is None:
            updates["depends_on"] = []
        elif not isinstance(updates["depends_on"], list):
            updates["depends_on"] = [updates["depends_on"]]

    # Coerce verified to bool
    if "verified" in updates:
        raw = updates["verified"]
        if isinstance(raw, bool):
            updates["verified"] = raw
        elif isinstance(raw, str):
            updates["verified"] = raw.strip().lower() in ("true", "1", "yes")
        else:
            updates["verified"] = bool(raw)

    if "verification_records" in updates:
        records_raw = updates["verification_records"]
        if records_raw is None:
            updates["verification_records"] = []
        elif isinstance(records_raw, list):
            updates["verification_records"] = [record.model_dump() for record in _normalize_verification_records(records_raw)]
        else:
            raise ResultError("verification_records must be a list of verification records")
        has_records = bool(updates["verification_records"])
        if "verified" not in updates:
            updates["verified"] = has_records
        elif bool(updates["verified"]) != has_records:
            raise ResultError("verified must match whether verification_records is empty")

    updated_fields: list[str] = []
    pending: dict[str, object] = {}
    for field in RESULT_FIELDS:
        if field in updates:
            pending[field] = updates[field]
            updated_fields.append(field)

    if not updated_fields:
        raise ResultError(
            f"No recognized fields in the update. Got keys: {sorted(updates.keys())}. "
            f"Valid fields: {sorted(RESULT_FIELDS)}"
        )

    # Validate before mutating state
    trial = dict(state["intermediate_results"][idx])
    trial.update(pending)
    if trial.get("verification_records") and not bool(trial.get("verified")):
        raise ResultError("verified cannot be false when verification_records are present")
    try:
        IntermediateResult(**trial)
    except _PydanticValidationError as exc:
        raise ResultError(f"Invalid update: {exc}") from exc

    # Commit to state only after validation succeeds
    state["intermediate_results"][idx].update(pending)

    return updated_fields, IntermediateResult(**state["intermediate_results"][idx])
