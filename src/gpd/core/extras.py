"""Approximations, uncertainties, open questions, and active calculations for GPD state.

All functions operate on state dicts (the caller handles persistence).
"""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as _PydanticValidationError

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
    status: str = "valid"


class ApproximationCheckResult(BaseModel):
    """Result of checking all approximations against their validity ranges."""

    model_config = ConfigDict(frozen=True)

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

_NUMERIC_BOUND = r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?"
_RANGE_OPERATOR = r"(?:<<|>>|<=|>=|<|>)"
_DOUBLE_BOUNDED_RE = re.compile(
    rf"^\s*({_NUMERIC_BOUND})\s*({_RANGE_OPERATOR})\s*([A-Za-z_][A-Za-z0-9_]*)\s*({_RANGE_OPERATOR})\s*({_NUMERIC_BOUND})\s*$"
)


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

    # Pattern: "low OP x OP high" — double-bounded range
    # NOTE: this must be checked BEFORE the single-bound << / >> patterns,
    # because strings like "0 << x << 10" would otherwise match the
    # single-bound << regex via re.search and never reach this block.
    m = _DOUBLE_BOUNDED_RE.fullmatch(range_str)
    if m:
        n1 = _parse_float(m.group(1))
        op1 = m.group(2)
        op2 = m.group(4)
        n2 = _parse_float(m.group(5))
        if n1 is not None and n2 is not None:
            has_much = op1 in ("<<", ">>") or op2 in ("<<", ">>")

            if has_much:
                # Apply "much less/greater than" semantics for each bound
                # separately, requiring BOTH conditions to pass.
                # op1 relates n1 to val: "n1 OP1 val"
                # op2 relates val to n2: "val OP2 n2"
                def _check_single(op: str, bound: float, val: float, bound_is_lower: bool) -> ValidityStatus:
                    if op == "<<":
                        if bound_is_lower:
                            # bound << val  =>  val >> bound  =>  val much greater than bound
                            if bound == 0:
                                if val > 10:
                                    return "valid"
                                if val > 1:
                                    return "marginal"
                                return "invalid"
                            if bound < 0:
                                distance = val - bound
                                scale = abs(bound)
                                if distance > 10 * scale:
                                    return "valid"
                                if distance > 2 * scale:
                                    return "marginal"
                                return "invalid"
                            if val > 10 * bound:
                                return "valid"
                            if val > 2 * bound:
                                return "marginal"
                            return "invalid"
                        else:
                            # val << bound  =>  val much less than bound
                            if bound == 0:
                                if val < -10:
                                    return "valid"
                                if val < -1:
                                    return "marginal"
                                return "invalid"
                            if bound < 0:
                                distance = bound - val  # positive when val < bound
                                scale = abs(bound)
                                if distance > 10 * scale:
                                    return "valid"
                                if distance > 2 * scale:
                                    return "marginal"
                                if distance > 0:
                                    return "marginal"
                                return "invalid"
                            if abs(val) < 0.1 * abs(bound):
                                return "valid"
                            if abs(val) < 0.5 * abs(bound):
                                return "marginal"
                            return "invalid"
                    elif op == ">>":
                        if bound_is_lower:
                            # bound >> val  =>  val << bound  =>  val much less than bound
                            if bound == 0:
                                if val < -10:
                                    return "valid"
                                if val < -1:
                                    return "marginal"
                                return "invalid"
                            if abs(val) < 0.1 * abs(bound):
                                return "valid"
                            if abs(val) < 0.5 * abs(bound):
                                return "marginal"
                            return "invalid"
                        else:
                            # val >> bound  =>  val much greater than bound
                            if bound == 0:
                                if val > 10:
                                    return "valid"
                                if val > 1:
                                    return "marginal"
                                return "invalid"
                            if bound < 0:
                                distance = val - bound
                                scale = abs(bound)
                                if distance > 10 * scale:
                                    return "valid"
                                if distance > 2 * scale:
                                    return "marginal"
                                return "invalid"
                            if val > 10 * bound:
                                return "valid"
                            if val > 2 * bound:
                                return "marginal"
                            return "invalid"
                    else:
                        # Simple < or > with inclusive variants
                        inclusive = "=" in op
                        if op.startswith("<"):
                            if bound_is_lower:
                                passes = val >= bound if inclusive else val > bound
                            else:
                                passes = val <= bound if inclusive else val < bound
                        else:
                            if bound_is_lower:
                                passes = val <= bound if inclusive else val < bound
                            else:
                                passes = val >= bound if inclusive else val > bound
                        return "valid" if passes else "invalid"

                s1 = _check_single(op1, n1, val, bound_is_lower=True)
                s2 = _check_single(op2, n2, val, bound_is_lower=False)

                # Both must pass; worst status wins
                _rank = {"valid": 0, "marginal": 1, "invalid": 2}
                worst = max(s1, s2, key=lambda s: _rank[s])
                return worst
            else:
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

    # Pattern: "x << bound" — much less than
    m = re.search(r"<<\s*([0-9.eE+-]+)", range_str)
    if m:
        bound = _parse_float(m.group(1))
        if bound is None:
            return None
        if bound < 0:
            # For negative bound, "much less than" means much more negative
            if val < bound * 10:  # e.g., val < -50 for bound=-5
                return "valid"
            if val < bound * 2:  # e.g., val < -10 for bound=-5
                return "marginal"
            return "invalid"
        if bound == 0:
            # "much less than zero" — value should be very negative
            if val < -10:
                return "valid"
            if val < -1:
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
            # "much greater than zero" — value should be large and positive
            if val > 10:
                return "valid"
            if val > 1:
                return "marginal"
            return "invalid"
        if bound < 0:
            # For negative bound, "much greater than" means the value is far
            # above the bound.  Use the *distance* from the bound (val - bound)
            # scaled by |bound| to judge how much greater the value is.
            distance = val - bound  # positive when val > bound
            scale = abs(bound)
            if distance > 10 * scale:
                return "valid"
            if distance > 2 * scale:
                return "marginal"
            if distance > 0:
                return "marginal"
            return "invalid"
        if val > 10 * bound:
            return "valid"
        if val > 2 * bound:
            return "marginal"
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
        rel_diff = abs(val - bound) / max(abs(bound), 1e-15)
        if rel_diff < 0.7:
            return "valid"
        if rel_diff < 1.5:
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


def _item_text(item: object) -> str:
    """Extract a plain string from a list item that may be a dict or str."""
    if isinstance(item, dict):
        return str(item.get("text", ""))
    return str(item)


# ─── Approximation Commands ──────────────────────────────────────────────────────


def approximation_add(
    state: dict,
    *,
    name: str,
    validity_range: str = "",
    controlling_param: str = "",
    current_value: str = "",
    status: str = "valid",
) -> Approximation:
    """Add an approximation to state.

    Raises ValueError if name is empty or a duplicate (case-insensitive) exists.
    """
    name = name.strip()
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
    raw = state.get("approximations", [])
    approximations: list[Approximation] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            approximations.append(Approximation(**item))
        except _PydanticValidationError:
            continue
    return approximations


@instrument_gpd_function("extras.approximation_check")
def approximation_check(state: dict) -> ApproximationCheckResult:
    """Check all approximations against their validity ranges.

    Categorizes each approximation as valid, marginal, invalid, or unchecked.
    """
    valid: list[Approximation] = []
    marginal: list[Approximation] = []
    invalid: list[Approximation] = []
    unchecked: list[Approximation] = []

    for approx_dict in state.get("approximations", []):
        if not isinstance(approx_dict, dict):
            continue
        try:
            approx = Approximation(**approx_dict)
        except _PydanticValidationError:
            continue
        val = _parse_float(approx.current_value)
        range_str = approx.validity_range

        if val is None or not range_str:
            unchecked.append(approx)
            continue

        status = check_approximation_validity(val, range_str)
        if status is None:
            unchecked.append(approx)
        elif status == "valid":
            valid.append(approx)
        elif status == "marginal":
            marginal.append(approx)
        else:
            invalid.append(approx)

    return ApproximationCheckResult(
        valid=valid, marginal=marginal, invalid=invalid, unchecked=unchecked
    )


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
    quantity = quantity.strip()
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
    text = text.strip()
    if not text:
        raise ExtrasError("text required for question-add")

    if "open_questions" not in state:
        state["open_questions"] = []

    state["open_questions"].append(text)
    return text


def question_list(state: dict) -> list[str | dict]:
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

    questions: list[object] = state["open_questions"]
    before = len(questions)

    # Try exact match (case-insensitive)
    for i, q in enumerate(questions):
        q_text = _item_text(q)
        if q_text.lower() == text.lower():
            questions.pop(i)
            return before - len(questions)

    # Fall back to substring match with word-boundary-like assertions
    escaped = re.escape(text)
    pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    for i, q in enumerate(questions):
        q_text = _item_text(q)
        if pattern.search(q_text):
            questions.pop(i)
            return before - len(questions)

    return 0


# ─── Active Calculation Commands ─────────────────────────────────────────────────


def calculation_add(state: dict, text: str) -> str:
    """Add an active calculation to state.

    Raises ValueError if text is empty.
    Returns the added calculation text.
    """
    text = text.strip()
    if not text:
        raise ExtrasError("text required for calculation-add")

    if "active_calculations" not in state:
        state["active_calculations"] = []

    state["active_calculations"].append(text)
    return text


def calculation_list(state: dict) -> list[str | dict]:
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

    calculations: list[object] = state["active_calculations"]
    before = len(calculations)

    # Try exact match (case-insensitive)
    for i, c in enumerate(calculations):
        c_text = _item_text(c)
        if c_text.lower() == text.lower():
            calculations.pop(i)
            return before - len(calculations)

    # Fall back to substring match with word-boundary-like assertions
    escaped = re.escape(text)
    pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    for i, c in enumerate(calculations):
        c_text = _item_text(c)
        if pattern.search(c_text):
            calculations.pop(i)
            return before - len(calculations)

    return 0
