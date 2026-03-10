"""Intermediate result tracking for GPD research state.

All functions operate on state dicts (the caller handles persistence).
"""

from __future__ import annotations

import secrets
import time
from collections import deque

from pydantic import BaseModel, ConfigDict, Field

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

RESULT_FIELDS = frozenset({"equation", "description", "units", "validity", "phase", "depends_on", "verified"})


def _int_to_base36(n: int) -> str:
    """Convert a non-negative integer to a base-36 string."""
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    while n > 0:
        result.append(digits[n % 36])
        n //= 36
    return "".join(reversed(result))


def _auto_generate_id(state: dict) -> str:
    """Auto-generate a result ID from the current phase and existing results count.

    Format: "R-{phase}-{seq}-{suffix}" e.g. "R-03-01-lxk7a2b".

    Uses base-36 encoding for the timestamp suffix and secrets.token_hex
    for the random part to provide good collision resistance.
    """
    position = state.get("position", {})
    phase = position.get("current_phase", 0)
    padded_phase = phase_normalize(str(phase))

    normalized_current = phase_unpad(str(phase))
    results = state.get("intermediate_results", [])
    existing_in_phase = [
        r for r in results if r.get("phase") is not None and phase_unpad(r["phase"]) == normalized_current
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


def _find_result_index(results: list[dict], result_id: str) -> int:
    """Find a result by id. Returns the index, or -1 if not found."""
    for i, r in enumerate(results):
        if r.get("id") == result_id:
            return i
    return -1


# --- Functions ---


@instrument_gpd_function("results.add")
def result_add(
    state: dict,
    *,
    equation: str | None = None,
    description: str | None = None,
    units: str | None = None,
    validity: str | None = None,
    phase: str | None = None,
    depends_on: list[str] | str | None = None,
    verified: bool = False,
    result_id: str | None = None,
) -> IntermediateResult:
    """Add an intermediate result to state.

    Auto-generates an ID if not provided. Uses the current phase from
    state.position if phase is not specified.

    Raises ValueError for empty IDs or duplicate IDs.
    """
    if "intermediate_results" not in state:
        state["intermediate_results"] = []

    rid = result_id or _auto_generate_id(state)
    if not rid or not rid.strip():
        raise ResultError(
            f"Result ID must be a non-empty string, got {rid!r}. "
            "Provide a descriptive ID (e.g., 'energy-conservation-eq') or omit it for auto-generation."
        )

    if _find_result_index(state["intermediate_results"], rid) != -1:
        raise DuplicateResultError(rid)

    # Resolve phase from state position if not provided
    if phase is None:
        position = state.get("position", {})
        raw_phase = position.get("current_phase")
        phase = str(raw_phase) if raw_phase is not None else None

    # Normalize depends_on to list
    if depends_on is None:
        deps: list[str] = []
    elif isinstance(depends_on, str):
        deps = [depends_on]
    else:
        deps = list(depends_on)

    result_dict = {
        "id": rid,
        "equation": equation,
        "description": description,
        "units": units,
        "validity": validity,
        "phase": phase,
        "depends_on": deps,
        "verified": verified,
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
    results = state.get("intermediate_results", [])

    if phase is not None:
        normalized_filter = phase_unpad(phase)
        results = [r for r in results if r.get("phase") is not None and phase_unpad(r["phase"]) == normalized_filter]

    if verified is True and unverified is True:
        raise ValueError("Cannot filter by both verified=True and unverified=True; the result would always be empty.")

    if verified is True:
        results = [r for r in results if r.get("verified") is True]

    if unverified is True:
        results = [r for r in results if not r.get("verified")]

    return [IntermediateResult(**r) for r in results]


@instrument_gpd_function("results.deps")
def result_deps(state: dict, result_id: str) -> ResultDeps:
    """Trace dependencies for a result using BFS.

    Returns the result, its direct dependencies, and transitive dependencies.
    Missing dependencies are represented as MissingDep objects.

    Raises KeyError if result_id is not found.
    """
    results = state.get("intermediate_results", [])
    idx = _find_result_index(results, result_id)
    if idx == -1:
        raise ResultNotFoundError(result_id)

    result = results[idx]

    # Build lookup map
    by_id: dict[str, dict] = {}
    for r in results:
        if r.get("id"):
            by_id[r["id"]] = r

    direct_dep_ids = result.get("depends_on", [])

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
def result_verify(state: dict, result_id: str) -> IntermediateResult:
    """Mark a result as verified.

    Raises KeyError if result_id is not found.
    """
    results = state.get("intermediate_results", [])
    idx = _find_result_index(results, result_id)
    if idx == -1:
        raise ResultNotFoundError(result_id)

    state["intermediate_results"][idx]["verified"] = True
    return IntermediateResult(**state["intermediate_results"][idx])


@instrument_gpd_function("results.update")
def result_update(state: dict, result_id: str, **updates: object) -> tuple[list[str], IntermediateResult]:
    """Update fields on an existing result.

    Only known fields are updated. Returns (updated_field_names, updated_result).
    Raises KeyError if result_id is not found.
    Raises ValueError if no recognized fields are provided.
    """
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
        updates["verified"] = updates["verified"] is True or str(updates["verified"]).strip().lower() == "true"

    updated_fields: list[str] = []
    for field in RESULT_FIELDS:
        if field in updates:
            state["intermediate_results"][idx][field] = updates[field]
            updated_fields.append(field)

    if not updated_fields:
        raise ResultError(
            f"No recognized fields in the update. Got keys: {sorted(updates.keys())}. "
            f"Valid fields: {sorted(RESULT_FIELDS)}"
        )

    return updated_fields, IntermediateResult(**state["intermediate_results"][idx])
