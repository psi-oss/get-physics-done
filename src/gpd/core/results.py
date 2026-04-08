"""Intermediate result tracking for GPD research state.

All functions operate on state dicts (the caller handles persistence).
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from collections import deque
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as _PydanticValidationError

from gpd.contracts import VerificationEvidence
from gpd.core.errors import DuplicateResultError, ResultError, ResultNotFoundError
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import normalize_ascii_slug, phase_normalize, phase_unpad

__all__ = [
    "RESULT_FIELDS",
    "IntermediateResult",
    "ResultSearchResult",
    "ResultUpsertResult",
    "ResultDeps",
    "ResultDownstream",
    "MissingDep",
    "result_add",
    "result_list",
    "result_search",
    "result_upsert",
    "result_upsert_derived",
    "result_deps",
    "result_downstream",
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


class ResultDownstream(BaseModel):
    """Reverse dependency trace for a result — all results that depend on it."""

    model_config = ConfigDict(frozen=True)

    result: IntermediateResult
    direct_dependents: list[IntermediateResult]
    transitive_dependents: list[IntermediateResult]


class ResultSearchResult(BaseModel):
    """Search results for the intermediate result registry."""

    model_config = ConfigDict(frozen=True)

    matches: list[IntermediateResult] = Field(default_factory=list)
    total: int = 0


class ResultUpsertResult(BaseModel):
    """Outcome of adding or updating a canonical intermediate result."""

    model_config = ConfigDict(frozen=True)

    action: str
    matched_by: str | None = None
    result: IntermediateResult
    updated_fields: list[str] = Field(default_factory=list)


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


def _strict_verification_records(
    records: object,
) -> list[VerificationEvidence]:
    """Validate an update-time verification-record payload without dropping data."""
    if records is None:
        return []
    if not isinstance(records, list):
        raise ResultError("verification_records must be a list of verification records")

    normalized: list[VerificationEvidence] = []
    for index, record in enumerate(records):
        if isinstance(record, VerificationEvidence):
            normalized.append(record)
            continue
        if isinstance(record, dict):
            try:
                normalized.append(VerificationEvidence(**record))
            except (TypeError, _PydanticValidationError) as exc:
                raise ResultError(f"Invalid verification_records[{index}]: {exc}") from exc
            continue
        raise ResultError(f"verification_records[{index}] must be a verification record object")
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


def _normalize_dependency_ids(depends_on: object) -> list[str]:
    """Normalize a raw depends_on payload into a list of dependency IDs."""
    if depends_on is None:
        return []
    if isinstance(depends_on, str):
        raw_dependencies: list[object] = [depends_on]
    elif isinstance(depends_on, (list, tuple, set, frozenset)):
        raw_dependencies = list(depends_on)
    else:
        raw_dependencies = [depends_on]

    normalized: list[str] = []
    for dependency in raw_dependencies:
        if isinstance(dependency, str):
            normalized.append(dependency)
        elif dependency is not None:
            normalized.append(str(dependency))
    return normalized


def _build_result_lookup(results: list[object]) -> dict[str, dict]:
    """Build a result-id lookup for structured registry entries."""
    by_id: dict[str, dict] = {}
    for result in results:
        if isinstance(result, dict):
            result_id = result.get("id")
            if result_id:
                by_id[str(result_id)] = result
    return by_id


def _result_from_record(record: dict) -> IntermediateResult:
    """Build a validated result model from a raw registry record."""
    payload = dict(record)
    payload["depends_on"] = _normalize_dependency_ids(record.get("depends_on", []))
    return IntermediateResult(**payload)


def _get_result_registry_context(state: dict, result_id: str) -> tuple[list[object], dict, dict[str, dict]]:
    """Return the raw registry list, the target result, and an ID lookup."""
    results = state.get("intermediate_results", [])
    idx = _find_result_index(results, result_id)
    if idx == -1:
        raise ResultNotFoundError(result_id)
    return results, results[idx], _build_result_lookup(results)


def term_matches(term: str, value: str) -> bool:
    """Check whether a term matches a value using case-insensitive substring matching."""
    if not term or not value:
        return False
    return str(term).lower() in str(value).lower()


def _normalize_identifier(value: object) -> str:
    """Return a normalized identifier token for exact matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().casefold()).strip()


def _normalized_identifier_matches(identifier: str, value: object) -> bool:
    """Check whether two identifiers match after normalization."""
    normalized_identifier = _normalize_identifier(identifier)
    if not normalized_identifier:
        return False
    return _normalize_identifier(value) == normalized_identifier


def _normalize_equation_for_match(value: str | None) -> str:
    """Return an equation token normalized only for whitespace-insensitive equality."""
    return re.sub(r"\s+", "", str(value or ""))


def _result_has_upstream_dependency(
    result: IntermediateResult,
    depends_on: str,
    *,
    results_by_normalized_id: dict[str, IntermediateResult],
) -> bool:
    """Return whether ``result`` depends on ``depends_on`` directly or transitively."""
    target_id = _normalize_identifier(depends_on)
    if not target_id:
        return False

    queue: deque[str] = deque(_normalize_dependency_ids(result.depends_on))
    visited: set[str] = set()

    while queue:
        dependency = queue.popleft()
        normalized_dependency = _normalize_identifier(dependency)
        if not normalized_dependency or normalized_dependency in visited:
            continue
        if normalized_dependency == target_id:
            return True
        visited.add(normalized_dependency)
        upstream_result = results_by_normalized_id.get(normalized_dependency)
        if upstream_result is not None:
            queue.extend(upstream_result.depends_on)

    return False


def _stable_derivation_result_id(state: dict, derivation_slug: str, *, phase: str | None = None) -> str:
    """Build a deterministic result ID from the current phase and derivation slug."""
    resolved_phase = phase
    if resolved_phase is None:
        position = state.get("position", {})
        raw_phase = position.get("current_phase")
        resolved_phase = str(raw_phase) if raw_phase is not None else "0"

    phase_token = phase_normalize(str(resolved_phase)).replace(".", "_")
    slug_token = normalize_ascii_slug(derivation_slug)
    if not slug_token:
        raise ResultError("derivation_slug must normalize to a non-empty ASCII identifier")
    return f"R-{phase_token}-{slug_token}"


def _collect_upsert_updates(
    *,
    equation: str | None,
    description: str | None,
    units: str | None,
    validity: str | None,
    phase: str | None,
    depends_on: list[str] | str | None,
    verified: bool | None,
    verification_records: list[VerificationEvidence | dict[str, object]] | None,
) -> dict[str, object]:
    """Collect only the fields explicitly supplied for an upsert update."""
    updates: dict[str, object] = {}
    if equation is not None:
        updates["equation"] = equation
    if description is not None:
        updates["description"] = description
    if units is not None:
        updates["units"] = units
    if validity is not None:
        updates["validity"] = validity
    if phase is not None:
        updates["phase"] = phase
    if depends_on is not None:
        updates["depends_on"] = depends_on
    if verified is not None:
        updates["verified"] = verified
    if verification_records is not None:
        updates["verification_records"] = verification_records
    return updates


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

    normalized_records = _strict_verification_records(verification_records)

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

    return [_result_from_record(r) for r in results]


@instrument_gpd_function("results.search")
def result_search(
    state: dict,
    *,
    id: str | None = None,
    text: str | None = None,
    equation: str | None = None,
    phase: str | None = None,
    depends_on: str | None = None,
    verified: bool | None = None,
    unverified: bool | None = None,
) -> ResultSearchResult:
    """Search the intermediate result registry.

    Only structured result entries are searched. Legacy string entries in
    ``state["intermediate_results"]`` are ignored.
    """
    if verified is True and unverified is True:
        raise ResultError("Cannot filter by both verified=True and unverified=True; the result would always be empty.")

    def _normalize_term(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    id = _normalize_term(id)
    text = _normalize_term(text)
    equation = _normalize_term(equation)
    phase = _normalize_term(phase)
    depends_on = _normalize_term(depends_on)

    candidates = result_list(state, phase=phase, verified=verified, unverified=unverified)
    all_results = result_list(state)
    results_by_normalized_id = {
        _normalize_identifier(result.id): result
        for result in all_results
        if _normalize_identifier(result.id)
    }
    matches: list[IntermediateResult] = []

    for result in candidates:
        if id is not None and not _normalized_identifier_matches(id, result.id):
            continue

        if equation is not None and not term_matches(equation, result.equation or ""):
            continue

        if depends_on is not None and not _result_has_upstream_dependency(
            result,
            depends_on,
            results_by_normalized_id=results_by_normalized_id,
        ):
            continue

        if text is not None:
            searchable_values = (result.id, result.description or "", result.equation or "")
            if not any(term_matches(text, value) for value in searchable_values):
                continue

        matches.append(result)

    return ResultSearchResult(matches=matches, total=len(matches))


@instrument_gpd_function("results.upsert")
def result_upsert(
    state: dict,
    *,
    equation: str | None = None,
    description: str | None = None,
    units: str | None = None,
    validity: str | None = None,
    phase: str | None = None,
    depends_on: list[str] | str | None = None,
    verified: bool | None = None,
    verification_records: list[VerificationEvidence | dict[str, object]] | None = None,
    result_id: str | None = None,
) -> ResultUpsertResult:
    """Add a canonical result or update the matching existing entry.

    Matching precedence:
    1. Explicit ``result_id`` if it already exists.
    2. Exact equation match after whitespace normalization, optionally narrowed by phase.
    3. Exact normalized description match, optionally narrowed by phase.
    4. Otherwise add a new result.
    """
    results = state.get("intermediate_results", [])
    if result_id is not None and _find_result_index(results, result_id) != -1:
        updates = _collect_upsert_updates(
            equation=equation,
            description=description,
            units=units,
            validity=validity,
            phase=phase,
            depends_on=depends_on,
            verified=verified,
            verification_records=verification_records,
        )
        updated_fields, updated = result_update(state, result_id, updates)
        return ResultUpsertResult(action="updated", matched_by="id", result=updated, updated_fields=updated_fields)

    normalized_equation = _normalize_equation_for_match(equation)
    if normalized_equation:
        equation_matches = [
            result
            for result in result_list(state, phase=phase)
            if _normalize_equation_for_match(result.equation) == normalized_equation
        ]
        if len(equation_matches) > 1:
            raise ResultError(
                "Multiple existing results match this equation. Provide an explicit result_id or phase to disambiguate."
            )
        if len(equation_matches) == 1:
            matched = equation_matches[0]
            updates = _collect_upsert_updates(
                equation=equation,
                description=description,
                units=units,
                validity=validity,
                phase=phase,
                depends_on=depends_on,
                verified=verified,
                verification_records=verification_records,
            )
            updated_fields, updated = result_update(state, matched.id, updates)
            return ResultUpsertResult(
                action="updated",
                matched_by="equation",
                result=updated,
                updated_fields=updated_fields,
            )

    normalized_description = _normalize_identifier(description)
    if normalized_description:
        description_matches = [
            result
            for result in result_list(state, phase=phase)
            if _normalize_identifier(result.description) == normalized_description
        ]
        if len(description_matches) > 1:
            raise ResultError(
                "Multiple existing results match this description. Provide an explicit result_id or phase to disambiguate."
            )
        if len(description_matches) == 1:
            matched = description_matches[0]
            updates = _collect_upsert_updates(
                equation=equation,
                description=description,
                units=units,
                validity=validity,
                phase=phase,
                depends_on=depends_on,
                verified=verified,
                verification_records=verification_records,
            )
            updated_fields, updated = result_update(state, matched.id, updates)
            return ResultUpsertResult(
                action="updated",
                matched_by="description",
                result=updated,
                updated_fields=updated_fields,
            )

    added = result_add(
        state,
        result_id=result_id,
        equation=equation,
        description=description,
        units=units,
        validity=validity,
        phase=phase,
        depends_on=depends_on,
        verified=bool(verified),
        verification_records=verification_records,
    )
    return ResultUpsertResult(action="added", result=added, updated_fields=[])


@instrument_gpd_function("results.upsert_derived")
def result_upsert_derived(
    state: dict,
    *,
    derivation_slug: str | None = None,
    equation: str | None = None,
    description: str | None = None,
    units: str | None = None,
    validity: str | None = None,
    phase: str | None = None,
    depends_on: list[str] | str | None = None,
    verified: bool | None = None,
    verification_records: list[VerificationEvidence | dict[str, object]] | None = None,
    result_id: str | None = None,
) -> ResultUpsertResult:
    """Persist a derivation result through the canonical upsert path.

    Reuses an explicit ``result_id`` when present. Otherwise, if a derivation
    slug is supplied, derives a deterministic stable ID from the target phase
    and slug before delegating to ``result_upsert``.
    """
    effective_result_id = result_id
    if effective_result_id is None and derivation_slug is not None:
        effective_result_id = _stable_derivation_result_id(state, derivation_slug, phase=phase)

    return result_upsert(
        state,
        equation=equation,
        description=description,
        units=units,
        validity=validity,
        phase=phase,
        depends_on=depends_on,
        verified=verified,
        verification_records=verification_records,
        result_id=effective_result_id,
    )


@instrument_gpd_function("results.deps")
def result_deps(state: dict, result_id: str) -> ResultDeps:
    """Trace dependencies for a result using BFS.

    Returns the result, its direct dependencies, and transitive dependencies.
    Missing dependencies are represented as MissingDep objects.

    Raises ResultNotFoundError if result_id is not found.
    """
    results, result, by_id = _get_result_registry_context(state, result_id)

    direct_dep_ids = list(dict.fromkeys(_normalize_dependency_ids(result.get("depends_on", []))))

    # Direct dependencies
    direct_deps: list[IntermediateResult | MissingDep] = []
    for dep_id in direct_dep_ids:
        if dep_id in by_id:
            direct_deps.append(_result_from_record(by_id[dep_id]))
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
            transitive_deps.append(_result_from_record(dep))

        for sub_dep_id in _normalize_dependency_ids(dep.get("depends_on", [])):
            if sub_dep_id not in visited:
                queue.append(sub_dep_id)

    return ResultDeps(
        result=_result_from_record(result),
        depends_on=list(direct_dep_ids),
        direct_deps=direct_deps,
        transitive_deps=transitive_deps,
    )


@instrument_gpd_function("results.downstream")
def result_downstream(state: dict, result_id: str) -> ResultDownstream:
    """Find all results that depend on the given result, transitively.

    Returns the result, its direct dependents (results whose ``depends_on``
    includes *result_id*), and transitive dependents (results that depend on
    those, and so on).

    Raises ResultNotFoundError if result_id is not found.
    """
    results, result, by_id = _get_result_registry_context(state, result_id)

    # Build a reverse adjacency map: for each result, which results list it
    # in their depends_on?
    reverse_deps: dict[str, list[str]] = {}
    for r in results:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        for dep_id in _normalize_dependency_ids(r.get("depends_on", [])):
            reverse_deps.setdefault(dep_id, []).append(r["id"])

    # Direct dependents — results whose depends_on contains result_id.
    direct_dependent_ids = list(dict.fromkeys(reverse_deps.get(result_id, [])))
    direct_dependents = [_result_from_record(by_id[did]) for did in direct_dependent_ids if did in by_id]

    # Transitive dependents via BFS, excluding direct dependents and the
    # result itself.
    visited: set[str] = {result_id}
    queue: deque[str] = deque(direct_dependent_ids)
    transitive_dependents: list[IntermediateResult] = []
    direct_dep_set = set(direct_dependent_ids)

    while queue:
        dep_id = queue.popleft()
        if dep_id in visited:
            continue
        visited.add(dep_id)

        if dep_id not in direct_dep_set and dep_id in by_id:
            transitive_dependents.append(_result_from_record(by_id[dep_id]))

        for downstream_id in reverse_deps.get(dep_id, []):
            if downstream_id not in visited:
                queue.append(downstream_id)

    return ResultDownstream(
        result=_result_from_record(result),
        direct_dependents=direct_dependents,
        transitive_dependents=transitive_dependents,
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
    deliverable_id: str | None = None,
    acceptance_test_id: str | None = None,
    reference_id: str | None = None,
    forbidden_proxy_id: str | None = None,
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
        deliverable_id=deliverable_id,
        acceptance_test_id=acceptance_test_id,
        reference_id=reference_id,
        forbidden_proxy_id=forbidden_proxy_id,
    )

    raw_result = state["intermediate_results"][idx]
    try:
        records = _strict_verification_records(raw_result.get("verification_records"))
    except ResultError as exc:
        raise ResultError(f"Existing verification_records for {result_id} are invalid: {exc}") from exc
    records.append(record)
    raw_result["verification_records"] = [entry.model_dump() for entry in records]
    raw_result["verified"] = True
    return _result_from_record(raw_result)


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

    if "verified" in updates:
        raw = updates["verified"]
        if not isinstance(raw, bool):
            raise ResultError("verified must be a boolean")

    if "verification_records" in updates:
        records = _strict_verification_records(updates["verification_records"])
        updates["verification_records"] = [record.model_dump() for record in records]
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
        validated = _result_from_record(trial)
    except _PydanticValidationError as exc:
        raise ResultError(f"Invalid update: {exc}") from exc

    # Commit to state only after validation succeeds
    state["intermediate_results"][idx].update(pending)
    state["intermediate_results"][idx]["depends_on"] = list(validated.depends_on)

    return updated_fields, _result_from_record(state["intermediate_results"][idx])
