from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gpd.core.numeric_oracle import (
    DEFAULT_MIN_SHARED_POINTS,
    EvaluatorCell,
    NumericOracleComparison,
    SamplePointEvaluation,
    TypedRestatement,
    build_numeric_oracle_kernel_verdict,
    compare_numeric_oracle,
)

_CLAIM_HASH = "sha256:" + "a" * 64
_BLIND_HASH = "sha256:" + "b" * 64
_FIXED_TIME = datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC)


def _claim_cell() -> EvaluatorCell:
    return EvaluatorCell(evaluator_id="claim-eval", content_hash=_CLAIM_HASH, role="claim")


def _blind_cell() -> EvaluatorCell:
    return EvaluatorCell(evaluator_id="blind-eval", content_hash=_BLIND_HASH, role="blind")


def _restatement(observable_id: str = "obs-1", kind: str = "scalar") -> TypedRestatement:
    return TypedRestatement(
        observable_id=observable_id,
        observable_kind=kind,
        statement="value of the scalar observable at the sampled parameter points",
    )


def _points(
    count: int,
    *,
    offset: float = 0.0,
    drift_at: int | None = None,
    drift: float = 0.0,
) -> list[SamplePointEvaluation]:
    points: list[SamplePointEvaluation] = []
    for i in range(count):
        claim = 1.0 + 0.1 * i
        blind = claim + offset
        if drift_at is not None and i == drift_at:
            blind = claim + drift
        points.append(
            SamplePointEvaluation(
                point_index=i,
                sample_point={"x": str(i)},
                claim_value=claim,
                blind_value=blind,
            )
        )
    return points


def _comparison(**overrides: object) -> NumericOracleComparison:
    base: dict[str, object] = {
        "contracted_observable_id": "obs-1",
        "contracted_observable_kind": "scalar",
        "typed_restatement": _restatement(),
        "tolerance": 1e-6,
        "sample_points": _points(DEFAULT_MIN_SHARED_POINTS),
        "claim_cell": _claim_cell(),
        "blind_cell": _blind_cell(),
    }
    base.update(overrides)
    return NumericOracleComparison(**base)


def test_full_agreement_is_green() -> None:
    verdict = compare_numeric_oracle(_comparison())
    assert verdict.verdict == "GREEN"
    assert verdict.agreeing_points == DEFAULT_MIN_SHARED_POINTS
    assert verdict.total_shared_points == DEFAULT_MIN_SHARED_POINTS
    assert verdict.both_cells_present is True
    assert verdict.fidelity_ok is True


def test_one_point_over_tolerance_is_red_with_worst_point() -> None:
    points = _points(DEFAULT_MIN_SHARED_POINTS, drift_at=7, drift=0.5)
    verdict = compare_numeric_oracle(_comparison(sample_points=points))
    assert verdict.verdict == "RED"
    assert verdict.worst_point_index == 7
    assert verdict.max_abs_diff == pytest.approx(0.5)
    assert verdict.agreeing_points == DEFAULT_MIN_SHARED_POINTS - 1


def test_insufficient_points_is_inconclusive() -> None:
    points = _points(DEFAULT_MIN_SHARED_POINTS - 1)
    verdict = compare_numeric_oracle(_comparison(sample_points=points))
    assert verdict.verdict == "INCONCLUSIVE"
    assert "shared usable sample points" in verdict.reason


def test_missing_claim_cell_is_inconclusive() -> None:
    verdict = compare_numeric_oracle(_comparison(claim_cell=None))
    assert verdict.verdict == "INCONCLUSIVE"
    assert verdict.both_cells_present is False
    assert "backing executed-cell hash" in verdict.reason


def test_fidelity_mismatch_is_inconclusive_even_with_agreement() -> None:
    # Numbers agree perfectly, but the blind agent computed a different quantity.
    verdict = compare_numeric_oracle(
        _comparison(typed_restatement=_restatement(observable_id="obs-other"))
    )
    assert verdict.verdict == "INCONCLUSIVE"
    assert verdict.fidelity_ok is False
    assert verdict.agreeing_points == DEFAULT_MIN_SHARED_POINTS


def test_kind_mismatch_is_inconclusive() -> None:
    verdict = compare_numeric_oracle(
        _comparison(typed_restatement=_restatement(kind="curve"))
    )
    assert verdict.verdict == "INCONCLUSIVE"
    assert verdict.fidelity_ok is False


def test_none_and_nan_values_reduce_usable_count() -> None:
    points = _points(DEFAULT_MIN_SHARED_POINTS)
    # Knock two points out of the usable set: one None, one NaN.
    points[0] = SamplePointEvaluation(point_index=0, claim_value=None, blind_value=1.0)
    points[1] = SamplePointEvaluation(point_index=1, claim_value=1.0, blind_value=float("nan"))
    verdict = compare_numeric_oracle(_comparison(sample_points=points))
    assert verdict.total_shared_points == DEFAULT_MIN_SHARED_POINTS - 2
    # 18 usable points < 20 required -> INCONCLUSIVE.
    assert verdict.verdict == "INCONCLUSIVE"


def test_within_tolerance_offset_is_green() -> None:
    points = _points(DEFAULT_MIN_SHARED_POINTS, offset=1e-9)
    verdict = compare_numeric_oracle(_comparison(sample_points=points, tolerance=1e-6))
    assert verdict.verdict == "GREEN"


def test_bool_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        SamplePointEvaluation(point_index=0, claim_value=True, blind_value=1.0)


def test_non_positive_tolerance_is_rejected() -> None:
    with pytest.raises(ValueError):
        _comparison(tolerance=0.0)


def test_bad_hash_is_rejected() -> None:
    with pytest.raises(ValueError):
        EvaluatorCell(evaluator_id="x", content_hash="not-a-hash", role="claim")


def test_bare_hex_hash_is_normalized() -> None:
    cell = EvaluatorCell(evaluator_id="x", content_hash="A" * 64, role="claim")
    assert cell.content_hash == "sha256:" + "a" * 64


def test_kernel_verdict_pass_only_when_green() -> None:
    green = build_numeric_oracle_kernel_verdict(_comparison(), generated_at=_FIXED_TIME)
    assert green["overall"] == "PASS"
    assert green["numeric_oracle_verdict"]["verdict"] == "GREEN"

    red_points = _points(DEFAULT_MIN_SHARED_POINTS, drift_at=3, drift=1.0)
    red = build_numeric_oracle_kernel_verdict(
        _comparison(sample_points=red_points), generated_at=_FIXED_TIME
    )
    assert red["overall"] == "FAIL"
    assert red["numeric_oracle_verdict"]["verdict"] == "RED"

    inconclusive = build_numeric_oracle_kernel_verdict(
        _comparison(claim_cell=None), generated_at=_FIXED_TIME
    )
    assert inconclusive["overall"] == "FAIL"
    assert inconclusive["numeric_oracle_verdict"]["verdict"] == "INCONCLUSIVE"


def test_kernel_verdict_hash_is_deterministic() -> None:
    first = build_numeric_oracle_kernel_verdict(_comparison(), generated_at=_FIXED_TIME)
    second = build_numeric_oracle_kernel_verdict(_comparison(), generated_at=_FIXED_TIME)
    assert first["verdict_hash"] == second["verdict_hash"]
    assert first["registry_hash"] == second["registry_hash"]
