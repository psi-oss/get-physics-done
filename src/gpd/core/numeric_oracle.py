"""Deterministic numeric-oracle verification primitives.

This module is the engine-side half of GPD's executed numeric-oracle
verification. It performs ONLY deterministic bookkeeping: it compares numbers
that an agent obtained by calling the separate ``gpd-compute`` MCP tool and
content-addresses the resulting verdict. It makes no LLM calls and no network
or oracle calls of its own.

The verification model is "numbers vs numbers":

- A *blind* re-deriver (which never sees the claimed answer) authors an
  independent evaluator and evaluates it at shared sample points.
- The claim's own evaluator is evaluated at the same points.
- This module diffs the two numeric vectors and emits a tri-state verdict:

  * ``GREEN`` — every shared usable point agrees within tolerance, the blind
    agent's typed restatement matches the contracted observable, and both
    sides carry a backing executed-cell hash.
  * ``RED`` — the two evaluators disagree beyond tolerance (a real conflict).
  * ``INCONCLUSIVE`` — the oracle could not decide: a missing backing
    evaluator-cell hash (anti-fabrication), fewer than the required number of
    shared usable points, or a proposition-fidelity mismatch (the blind agent
    computed a different quantity than the contracted observable).

The kernel ``Result`` type stays binary (Pass/Fail); the tri-state lives here
and is surfaced one layer up (the contract-check ``status``). This mirrors
``reproducibility.py`` and reuses the shared content-addressing kernel.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from gpd.core.kernel import Fail, Pass, RegistryBase
from gpd.core.kernel import run as run_kernel

__all__ = [
    "EvaluatorCell",
    "TypedRestatement",
    "SamplePointEvaluation",
    "NumericOracleComparison",
    "NumericOracleVerdict",
    "NumericOracleRegistry",
    "compare_numeric_oracle",
    "build_numeric_oracle_kernel_verdict",
    "DEFAULT_MIN_SHARED_POINTS",
]

_HASH_HEX_RE = re.compile(r"[0-9a-f]{64}")
_STRICT_FROZEN_MODEL_CONFIG = ConfigDict(frozen=True, extra="forbid")

#: The default minimum number of shared, usable sample points required before a
#: numeric agreement can be scored GREEN. Fewer than this is INCONCLUSIVE.
DEFAULT_MIN_SHARED_POINTS = 20


def _coerce_optional_number(value: object) -> float | None:
    """Coerce a per-point evaluation value to ``float`` or ``None``.

    Rejects booleans and strings so a fabricated/ill-typed value cannot slip
    through the comparison as a number.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("evaluation value must be a number, not a bool")
    if isinstance(value, int | float):
        return float(value)
    raise ValueError("evaluation value must be a number or null")


class EvaluatorCell(BaseModel):
    """Provenance for one executed evaluator (claim-side or blind-side).

    The ``content_hash`` is the stable hash of the evaluator source that
    ``gpd-compute`` actually executed. Its presence is the anti-fabrication
    leg: numbers without a backing executed-cell hash are not accepted.
    """

    model_config = _STRICT_FROZEN_MODEL_CONFIG

    evaluator_id: str
    content_hash: str
    role: Literal["claim", "blind"]

    @field_validator("content_hash", mode="before")
    @classmethod
    def _normalize_hash(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("content_hash must be a string")
        raw = value.strip().lower()
        hexpart = raw[len("sha256:") :] if raw.startswith("sha256:") else raw
        if not _HASH_HEX_RE.fullmatch(hexpart):
            raise ValueError("content_hash must be a sha256 hex digest")
        return f"sha256:{hexpart}"

    @field_validator("evaluator_id")
    @classmethod
    def _non_empty_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evaluator_id cannot be empty")
        return value


class TypedRestatement(BaseModel):
    """The blind agent's typed restatement of WHAT quantity it computed.

    The proposition-fidelity guard compares this against the contracted
    observable so numeric agreement on the *wrong* quantity cannot pass GREEN.
    """

    model_config = _STRICT_FROZEN_MODEL_CONFIG

    observable_id: str
    observable_kind: str
    statement: str

    @field_validator("observable_id", "observable_kind", "statement")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field cannot be empty")
        return value


class SamplePointEvaluation(BaseModel):
    """One shared sample point with the value from each evaluator."""

    model_config = _STRICT_FROZEN_MODEL_CONFIG

    point_index: int
    sample_point: dict[str, str] = Field(default_factory=dict)
    claim_value: float | None = None
    blind_value: float | None = None

    @field_validator("claim_value", "blind_value", mode="before")
    @classmethod
    def _coerce_values(cls, value: object) -> float | None:
        return _coerce_optional_number(value)


class NumericOracleComparison(BaseModel):
    """The full input to a numeric-oracle comparison.

    Carries the two evaluators' provenance, the per-point numbers obtained from
    ``gpd-compute``, the tolerance, and the blind agent's typed restatement
    plus the contracted observable to check fidelity against.
    """

    model_config = _STRICT_FROZEN_MODEL_CONFIG

    contracted_observable_id: str
    contracted_observable_kind: str | None = None
    typed_restatement: TypedRestatement
    tolerance: float
    min_shared_points: int = DEFAULT_MIN_SHARED_POINTS
    sample_points: list[SamplePointEvaluation] = Field(default_factory=list)
    claim_cell: EvaluatorCell | None = None
    blind_cell: EvaluatorCell | None = None

    @field_validator("contracted_observable_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("contracted_observable_id cannot be empty")
        return value

    @field_validator("tolerance")
    @classmethod
    def _positive_tolerance(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("tolerance must be a positive finite number")
        return value

    @field_validator("min_shared_points")
    @classmethod
    def _positive_min_points(cls, value: int) -> int:
        if value < 1:
            raise ValueError("min_shared_points must be at least 1")
        return value


class NumericOracleVerdict(BaseModel):
    """The deterministic tri-state outcome of a numeric-oracle comparison."""

    model_config = _STRICT_FROZEN_MODEL_CONFIG

    verdict: Literal["GREEN", "INCONCLUSIVE", "RED"]
    reason: str
    both_cells_present: bool
    fidelity_ok: bool
    agreeing_points: int
    total_shared_points: int
    min_shared_points: int
    tolerance: float
    max_abs_diff: float | None = None
    worst_point_index: int | None = None


def compare_numeric_oracle(comparison: NumericOracleComparison) -> NumericOracleVerdict:
    """Deterministically compare claim-side vs blind-side numbers.

    Pure and fail-closed: returns INCONCLUSIVE on any undecidable condition
    (missing backing hash, fidelity mismatch, insufficient shared points),
    GREEN only on full agreement, RED on genuine numeric disagreement.
    """
    both_cells_present = comparison.claim_cell is not None and comparison.blind_cell is not None

    fidelity_ok = (
        comparison.typed_restatement.observable_id == comparison.contracted_observable_id
        and (
            comparison.contracted_observable_kind is None
            or comparison.typed_restatement.observable_kind == comparison.contracted_observable_kind
        )
    )

    usable: list[tuple[int, float]] = []
    for point in comparison.sample_points:
        claim_value = point.claim_value
        blind_value = point.blind_value
        if claim_value is None or blind_value is None:
            continue
        if not (math.isfinite(claim_value) and math.isfinite(blind_value)):
            continue
        usable.append((point.point_index, abs(claim_value - blind_value)))

    total_shared = len(usable)
    agreeing = sum(1 for _, diff in usable if diff <= comparison.tolerance)
    max_abs_diff = max((diff for _, diff in usable), default=None)
    worst_point_index = max(usable, key=lambda item: item[1])[0] if usable else None

    def _verdict(verdict: str, reason: str) -> NumericOracleVerdict:
        return NumericOracleVerdict(
            verdict=verdict,
            reason=reason,
            both_cells_present=both_cells_present,
            fidelity_ok=fidelity_ok,
            agreeing_points=agreeing,
            total_shared_points=total_shared,
            min_shared_points=comparison.min_shared_points,
            tolerance=comparison.tolerance,
            max_abs_diff=max_abs_diff,
            worst_point_index=worst_point_index,
        )

    # Anti-fabrication: every accepted number must carry a backing executed-cell hash.
    if not both_cells_present:
        missing = "claim" if comparison.claim_cell is None else "blind"
        if comparison.claim_cell is None and comparison.blind_cell is None:
            missing = "claim and blind"
        return _verdict(
            "INCONCLUSIVE",
            f"missing backing executed-cell hash for the {missing} evaluator",
        )

    # Proposition fidelity: the blind agent must have computed the contracted quantity.
    if not fidelity_ok:
        return _verdict(
            "INCONCLUSIVE",
            "blind restatement does not match the contracted observable "
            f"(restated {comparison.typed_restatement.observable_id!r}/"
            f"{comparison.typed_restatement.observable_kind!r} vs contracted "
            f"{comparison.contracted_observable_id!r}/{comparison.contracted_observable_kind!r})",
        )

    # Sufficiency: enough shared usable points to be decisive.
    if total_shared < comparison.min_shared_points:
        return _verdict(
            "INCONCLUSIVE",
            f"only {total_shared} shared usable sample points "
            f"(need >= {comparison.min_shared_points})",
        )

    # Agreement.
    if agreeing == total_shared:
        return _verdict(
            "GREEN",
            f"all {total_shared} shared points agree within tolerance {comparison.tolerance:g}",
        )
    return _verdict(
        "RED",
        f"{total_shared - agreeing}/{total_shared} shared points disagree beyond "
        f"tolerance {comparison.tolerance:g} (max abs diff {max_abs_diff:g} at point "
        f"{worst_point_index})",
    )


class NumericOracleRegistry(RegistryBase):
    """Kernel-compatible registry wrapper for a numeric-oracle comparison."""

    def __init__(
        self,
        comparison: NumericOracleComparison,
        verdict: NumericOracleVerdict,
        raw_bytes: bytes,
    ) -> None:
        super().__init__(raw_bytes)
        self.comparison = comparison
        self.verdict = verdict

    @classmethod
    def from_comparison(cls, comparison: NumericOracleComparison) -> NumericOracleRegistry:
        verdict = compare_numeric_oracle(comparison)
        payload = comparison.model_dump(mode="json")
        raw_bytes = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return cls(comparison=comparison, verdict=verdict, raw_bytes=raw_bytes)

    def stats(self) -> dict[str, int]:
        return {
            "sample_points": len(self.comparison.sample_points),
            "shared_usable_points": self.verdict.total_shared_points,
            "agreeing_points": self.verdict.agreeing_points,
        }


def build_numeric_oracle_kernel_verdict(
    comparison: NumericOracleComparison,
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Build a content-addressed kernel verdict for a numeric-oracle comparison.

    The kernel ``overall`` is ``PASS`` exactly when the comparison is GREEN
    (both cells present, fidelity matched, enough points, full agreement). The
    richer tri-state is attached under ``numeric_oracle_verdict`` for the
    contract-check layer to map onto its ``status`` (GREEN -> pass,
    RED -> fail, INCONCLUSIVE -> insufficient_evidence).
    """
    registry = NumericOracleRegistry.from_comparison(comparison)

    def both_cells_present(reg: RegistryBase) -> object:
        if not isinstance(reg, NumericOracleRegistry):
            return Fail("numeric oracle registry type mismatch")
        if reg.verdict.both_cells_present:
            return Pass("both evaluators carry a backing executed-cell hash")
        return Fail("missing a backing executed-cell hash (anti-fabrication)")

    def sufficient_sample_points(reg: RegistryBase) -> object:
        if not isinstance(reg, NumericOracleRegistry):
            return Fail("numeric oracle registry type mismatch")
        shared = reg.verdict.total_shared_points
        required = reg.comparison.min_shared_points
        if shared >= required:
            return Pass(f"{shared} shared usable points (>= {required})")
        return Fail(f"only {shared} shared usable points (need >= {required})")

    def proposition_fidelity(reg: RegistryBase) -> object:
        if not isinstance(reg, NumericOracleRegistry):
            return Fail("numeric oracle registry type mismatch")
        if reg.verdict.fidelity_ok:
            return Pass("blind restatement matches the contracted observable")
        return Fail("blind restatement does not match the contracted observable")

    def numbers_agree(reg: RegistryBase) -> object:
        if not isinstance(reg, NumericOracleRegistry):
            return Fail("numeric oracle registry type mismatch")
        shared = reg.verdict.total_shared_points
        agreeing = reg.verdict.agreeing_points
        if shared > 0 and agreeing == shared:
            return Pass(f"all {shared} shared points agree within tolerance")
        return Fail(reg.verdict.reason)

    verdict_dict = run_kernel(
        registry,
        {
            "both_cells_present": both_cells_present,
            "sufficient_sample_points": sufficient_sample_points,
            "proposition_fidelity": proposition_fidelity,
            "numbers_agree": numbers_agree,
        },
        predicates_source=Path(__file__),
        generated_at=generated_at,
    )
    verdict_dict["numeric_oracle_verdict"] = registry.verdict.model_dump(mode="json")
    return verdict_dict
