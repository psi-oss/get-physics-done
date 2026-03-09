"""Approximations, uncertainties, open questions, and active calculations for GPD state.

Ported from experiments/get-physics-done/get-physics-done/src/state-extras.js.
All functions operate on state dicts (the caller handles persistence).
"""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.errors import DuplicateApproximationError, ExtrasError
from gpd.core.observability import instrument_gpd_function

__all__ = [
    "Approximation",
    "ApproximationCheckResult",
    "Uncertainty",
    "ValidityStatus",
    "check_approximation_validity",
    "approximation_add",
    "approximation_list",
    "approximation_check",
    "uncertainty_add",
    "uncertainty_list",
    "question_add",
    "question_list",
    "question_resolve",
    "calculation_add",
    "calculation_list",
    "calculation_complete",
]

# ─── Models ──────────────────────────────────────────────────────────────────────


class Approximation(BaseModel):
    """A tracked physics approximation with its validity range."""

    model_config = ConfigDict(frozen=True)

    name: str
    validity_range: str = ""
    controlling_param: str = ""
    current_value: str = ""
    status: str = "Valid"


class ApproximationCheckResult(BaseModel):
    """Result of checking all approximations against their validity ranges."""

    valid: list[Approximation] = Field(default_factory=list)
    marginal: list[Approximation] = Field(default_factory=list)
    invalid: list[Approximation] = Field(default_factory=list)
    unchecked: list[Approximation] = Field(default_factory=list)


class Uncertainty(BaseModel):
    """A propagated uncertainty record."""

    model_config = ConfigDict(frozen=True)

    quantity: str
    value: str = ""
    uncertainty: str = ""
    phase: str = ""
    method: str = ""


# ─── Approximation Validity Checking ─────────────────────────────────────────────

ValidityStatus = Literal["valid", "marginal", "invalid"]


def check_approximation_validity(val: float, range_str: str) -> ValidityStatus | None:
    """Parse a validity range string and check a numeric value against it.

    Supports patterns:
      "x << bound"       — much less than
      "x >> bound"       — much greater than
      "low < x < high"   — double-bounded range
      "x ~ bound"        — approximately equal (within order of magnitude)
      "x < bound"        — less than
      "x > bound"        — greater than

    Returns "valid", "marginal", "invalid", or None (unparseable).
    """
    if not range_str:
        return None

    # Pattern: "x << bound" — much less than
    m = re.search(r"<<\s*([0-9.eE+-]+)", range_str)
    if m:
        bound = _parse_float(m.group(1))
        if bound is None:
            return None
        if bound < 0:
            if val < 0.1 * bound:
                return "valid"
            if val < 0.5 * bound:
                return "marginal"
            return "invalid"
        if abs(val) < 0.1 * abs(bound):
            return "valid"
        if abs(val) < 0.5 * abs(bound):
            return "marginal"
        return "invalid"

    # Pattern: "x >> bound" — much greater than
    m = re.search(r">>\s*([0-9.eE+-]+)", range_str)
    if m:
        bound = _parse_float(m.group(1))
        if bound is None:
            return None
        if bound == 0:
            if abs(val) > 10:
                return "valid"
            if abs(val) > 1:
                return "marginal"
            return "invalid"
        if abs(val) > 10 * abs(bound):
            return "valid"
        if abs(val) > 2 * abs(bound):
            return "marginal"
        return "invalid"

    # Pattern: "low OP x OP high" — double-bounded range
    m = re.search(r"([0-9.eE+-]+)\s*([<>]=?)\s*\w+\s*([<>]=?)\s*([0-9.eE+-]+)", range_str)
    if m:
        n1 = _parse_float(m.group(1))
        op1 = m.group(2)
        op2 = m.group(3)
        n2 = _parse_float(m.group(4))
        if n1 is not None and n2 is not None:
            op1_inclusive = "=" in op1
            op2_inclusive = "=" in op2

            # First condition: n1 OP1 x
            if op1.startswith("<"):
                passes_first = val >= n1 if op1_inclusive else val > n1
            else:
                passes_first = val <= n1 if op1_inclusive else val < n1

            # Second condition: x OP2 n2
            if op2.startswith("<"):
                passes_second = val <= n2 if op2_inclusive else val < n2
            else:
                passes_second = val >= n2 if op2_inclusive else val > n2

            if passes_first and passes_second:
                lo = min(n1, n2)
                hi = max(n1, n2)
                span = hi - lo
                if span > 0:
                    margin_lo = lo + 0.2 * span
                    margin_hi = hi - 0.2 * span
                    if val < margin_lo or val > margin_hi:
                        return "marginal"
                return "valid"
            return "invalid"

    # Pattern: "x ~ bound" — approximately equal
    m = re.search(r"~\s*([0-9.eE+-]+)", range_str)
    if m:
        bound = _parse_float(m.group(1))
        if bound is None:
            return None
        if bound == 0:
            if abs(val) < 0.1:
                return "valid"
            if abs(val) < 1:
                return "marginal"
            return "invalid"
        ratio = abs(val / bound)
        if 0.3 < ratio < 3:
            return "valid"
        if 0.1 < ratio < 10:
            return "marginal"
        return "invalid"

    # Pattern: "x < bound" or "x <= bound"
    m = re.search(r"<(=?)\s*([0-9.eE+-]+)", range_str)
    if m:
        inclusive = m.group(1) == "="
        bound = _parse_float(m.group(2))
        if bound is None:
            return None
        passes = val <= bound if inclusive else val < bound
        if passes:
            if bound != 0 and abs(val - bound) < 0.2 * abs(bound):
                return "marginal"
            return "valid"
        return "invalid"

    # Pattern: "x > bound" or "x >= bound"
    m = re.search(r">(=?)\s*([0-9.eE+-]+)", range_str)
    if m:
        inclusive = m.group(1) == "="
        bound = _parse_float(m.group(2))
        if bound is None:
            return None
        passes = val >= bound if inclusive else val > bound
        if passes:
            if bound != 0 and abs(val - bound) < 0.2 * abs(bound):
                return "marginal"
            return "valid"
        return "invalid"

    return None


def _parse_float(s: str) -> float | None:
    """Parse a float, returning None on failure."""
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


# ─── Approximation Commands ──────────────────────────────────────────────────────


def approximation_add(
    state: dict,
    *,
    name: str,
    validity_range: str = "",
    controlling_param: str = "",
    current_value: str = "",
    status: str = "Valid",
) -> Approximation:
    """Add an approximation to state.

    Raises ValueError if name is empty or a duplicate (case-insensitive) exists.
    """
    if not name:
        raise ExtrasError("name required for approximation-add")

    if "approximations" not in state:
        state["approximations"] = []

    # Check for duplicate (case-insensitive)
    for existing in state["approximations"]:
        if existing.get("name", "").lower() == name.lower():
            raise DuplicateApproximationError(name)

    entry = {
        "name": name,
        "validity_range": validity_range,
        "controlling_param": controlling_param,
        "current_value": current_value,
        "status": status,
    }
    state["approximations"].append(entry)
    return Approximation(**entry)


def approximation_list(state: dict) -> list[Approximation]:
    """List all approximations from state."""
    return [Approximation(**a) for a in state.get("approximations", [])]


@instrument_gpd_function("extras.approximation_check")
def approximation_check(state: dict) -> ApproximationCheckResult:
    """Check all approximations against their validity ranges.

    Categorizes each approximation as valid, marginal, invalid, or unchecked.
    """
    result = ApproximationCheckResult()

    for approx_dict in state.get("approximations", []):
        approx = Approximation(**approx_dict)
        val = _parse_float(approx.current_value)
        range_str = approx.validity_range

        if val is None or not range_str:
            result.unchecked.append(approx)
            continue

        check = check_approximation_validity(val, range_str)
        if check is None:
            result.unchecked.append(approx)
        elif check == "valid":
            result.valid.append(approx)
        elif check == "marginal":
            result.marginal.append(approx)
        else:
            result.invalid.append(approx)

    return result


# ─── Uncertainty Commands ────────────────────────────────────────────────────────


def uncertainty_add(
    state: dict,
    *,
    quantity: str,
    value: str = "",
    uncertainty: str = "",
    phase: str = "",
    method: str = "",
) -> Uncertainty:
    """Add or update a propagated uncertainty record.

    If a record with the same quantity (case-insensitive) exists, it is updated
    in place. Otherwise, a new record is added.

    Raises ValueError if quantity is empty.
    """
    if not quantity:
        raise ExtrasError("quantity required for uncertainty-add")

    if "propagated_uncertainties" not in state:
        state["propagated_uncertainties"] = []

    entry = {
        "quantity": quantity,
        "value": value,
        "uncertainty": uncertainty,
        "phase": phase,
        "method": method,
    }

    # Update existing or append
    for i, existing in enumerate(state["propagated_uncertainties"]):
        if existing.get("quantity", "").lower() == quantity.lower():
            state["propagated_uncertainties"][i] = entry
            return Uncertainty(**entry)

    state["propagated_uncertainties"].append(entry)
    return Uncertainty(**entry)


def uncertainty_list(state: dict) -> list[Uncertainty]:
    """List all propagated uncertainties from state."""
    return [Uncertainty(**u) for u in state.get("propagated_uncertainties", [])]


# ─── Open Question Commands ──────────────────────────────────────────────────────


def question_add(state: dict, text: str) -> str:
    """Add an open question to state.

    Raises ValueError if text is empty.
    Returns the added question text.
    """
    if not text:
        raise ExtrasError("text required for question-add")

    if "open_questions" not in state:
        state["open_questions"] = []

    state["open_questions"].append(text)
    return text


def question_list(state: dict) -> list[str]:
    """List all open questions from state."""
    return list(state.get("open_questions", []))


def question_resolve(state: dict, text: str) -> int:
    """Resolve (remove) an open question matching the given text.

    First tries exact match (case-insensitive), then falls back to
    word-boundary substring match. Removes only the first match.

    Raises ValueError if text is empty or too short (< 3 chars).
    Returns the number of questions removed (0 or 1).
    """
    if not text:
        raise ExtrasError("text required for question-resolve")
    if len(text) < 3:
        raise ExtrasError("search text must be at least 3 characters to avoid accidental matches")

    if "open_questions" not in state:
        state["open_questions"] = []

    questions: list[str] = state["open_questions"]
    before = len(questions)

    # Try exact match (case-insensitive)
    for i, q in enumerate(questions):
        if q.lower() == text.lower():
            questions.pop(i)
            return before - len(questions)

    # Fall back to word-boundary match
    escaped = re.escape(text)
    pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    for i, q in enumerate(questions):
        if pattern.search(q):
            questions.pop(i)
            return before - len(questions)

    return 0


# ─── Active Calculation Commands ─────────────────────────────────────────────────


def calculation_add(state: dict, text: str) -> str:
    """Add an active calculation to state.

    Raises ValueError if text is empty.
    Returns the added calculation text.
    """
    if not text:
        raise ExtrasError("text required for calculation-add")

    if "active_calculations" not in state:
        state["active_calculations"] = []

    state["active_calculations"].append(text)
    return text


def calculation_list(state: dict) -> list[str]:
    """List all active calculations from state."""
    return list(state.get("active_calculations", []))


def calculation_complete(state: dict, text: str) -> int:
    """Complete (remove) an active calculation matching the given text.

    First tries exact match (case-insensitive), then falls back to
    word-boundary substring match. Removes only the first match.

    Raises ValueError if text is empty or too short (< 3 chars).
    Returns the number of calculations removed (0 or 1).
    """
    if not text:
        raise ExtrasError("text required for calculation-complete")
    if len(text) < 3:
        raise ExtrasError("search text must be at least 3 characters to avoid accidental matches")

    if "active_calculations" not in state:
        state["active_calculations"] = []

    calculations: list[str] = state["active_calculations"]
    before = len(calculations)

    # Try exact match (case-insensitive)
    for i, c in enumerate(calculations):
        if c.lower() == text.lower():
            calculations.pop(i)
            return before - len(calculations)

    # Fall back to word-boundary match
    escaped = re.escape(text)
    pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    for i, c in enumerate(calculations):
        if pattern.search(c):
            calculations.pop(i)
            return before - len(calculations)

    return 0
