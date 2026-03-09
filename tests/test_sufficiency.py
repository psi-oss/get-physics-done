"""TDD tests for sufficiency domain module (O'Brien-Fleming + SPRT).

Tests for sequential analysis sufficiency checking:
- SufficiencyDecision frozen dataclass
- obrien_fleming_alpha_spend: cumulative alpha spending function
- check_sufficiency: O'Brien-Fleming interim stopping
- sprt_boundaries: SPRT decision boundaries
- check_sufficiency_sprt: SPRT-based sufficiency gate
"""

from __future__ import annotations

import numpy as np
import pytest

from gpd.exp.domain.sufficiency import (
    SufficiencyDecision,
    check_sufficiency,
    check_sufficiency_sprt,
    obrien_fleming_alpha_spend,
    sprt_boundaries,
)

# ---------------------------------------------------------------------------
# obrien_fleming_alpha_spend tests
# ---------------------------------------------------------------------------


class TestOBrienFlemingAlphaSpend:
    """Tests for obrien_fleming_alpha_spend(t, alpha)."""

    def test_alpha_spend_at_t_one_equals_alpha(self) -> None:
        """At t=1.0, cumulative alpha spent equals alpha (exactly)."""
        result = obrien_fleming_alpha_spend(1.0, alpha=0.05)
        assert abs(result - 0.05) < 1e-10, f"Expected 0.05, got {result}"

    def test_alpha_spend_at_t_zero_is_zero(self) -> None:
        """At t=0.0, no alpha is spent."""
        result = obrien_fleming_alpha_spend(0.0, alpha=0.05)
        assert result == 0.0, f"Expected 0.0, got {result}"

    def test_alpha_spend_at_t_half_is_approximately_0_00558(self) -> None:
        """At t=0.5, cumulative alpha spent is approximately 0.00558."""
        result = obrien_fleming_alpha_spend(0.5, alpha=0.05)
        assert abs(result - 0.00558) < 0.001, f"Expected ~0.00558, got {result}"

    def test_alpha_spend_at_t_quarter_is_approximately_0_000089(self) -> None:
        """At t=0.25, cumulative alpha spent is approximately 0.000089."""
        result = obrien_fleming_alpha_spend(0.25, alpha=0.05)
        assert abs(result - 0.000089) < 0.0001, f"Expected ~0.000089, got {result}"

    def test_alpha_spend_is_monotonically_increasing(self) -> None:
        """Alpha spend increases with information fraction t."""
        values = [obrien_fleming_alpha_spend(t / 10) for t in range(1, 11)]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1], (
                f"Alpha spend should increase: values[{i}]={values[i]} >= values[{i + 1}]={values[i + 1]}"
            )

    def test_alpha_spend_never_exceeds_alpha(self) -> None:
        """Alpha spend never exceeds the total alpha."""
        for t in [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            result = obrien_fleming_alpha_spend(t, alpha=0.05)
            assert result <= 0.05 + 1e-12, f"Alpha spend {result} exceeded alpha at t={t}"


# ---------------------------------------------------------------------------
# check_sufficiency (O'Brien-Fleming) tests
# ---------------------------------------------------------------------------


class TestCheckSufficiency:
    """Tests for check_sufficiency with O'Brien-Fleming stopping."""

    def test_sufficient_when_n_collected_at_least_n_planned(self) -> None:
        """When n_collected >= n_planned, returns 'sufficient' with method='complete'."""
        group_a = np.random.default_rng(0).normal(0, 1, 50)
        group_b = np.random.default_rng(1).normal(0, 1, 50)
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert result.decision == "sufficient"
        assert result.method == "complete"

    def test_insufficient_when_not_at_interim_fraction(self) -> None:
        """At t=0.3 (not near 0.5 or 1.0), returns 'insufficient' without testing."""
        rng = np.random.default_rng(42)
        group_a = rng.normal(0, 1, 15)  # 30 total, 100 planned -> t=0.30
        group_b = rng.normal(0, 1, 15)
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert result.decision == "insufficient"
        assert result.method == "obrien_fleming"
        assert result.n_collected == 30
        assert result.n_planned == 100

    def test_early_stop_at_interim_with_large_effect(self) -> None:
        """At t=0.5, clearly different groups trigger early stop -> 'sufficient'."""
        rng = np.random.default_rng(99)
        # Very large effect size: group_a near 0, group_b near 100
        group_a = rng.normal(0, 1, 25)
        group_b = rng.normal(100, 1, 25)  # 50 total of 100 planned -> t=0.50
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert result.decision == "sufficient", (
            f"Expected 'sufficient' with large effect at interim, got '{result.decision}'"
        )

    def test_no_early_stop_at_interim_with_null_effect(self) -> None:
        """At t=0.5, identical groups do not trigger early stop -> 'insufficient'."""
        rng = np.random.default_rng(7)
        group_a = rng.normal(0, 1, 25)
        group_b = rng.normal(0, 1, 25)  # 50 total of 100 planned -> t=0.50
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert result.decision == "insufficient", (
            f"Expected 'insufficient' with null effect at interim, got '{result.decision}'"
        )

    def test_sufficiency_decision_is_frozen_dataclass(self) -> None:
        """SufficiencyDecision is a frozen dataclass (immutable)."""
        rng = np.random.default_rng(0)
        group_a = rng.normal(0, 1, 50)
        group_b = rng.normal(0, 1, 50)
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert isinstance(result, SufficiencyDecision)
        with pytest.raises((AttributeError, TypeError)):
            result.decision = "changed"  # type: ignore[misc]

    def test_information_fraction_clamped_to_one_at_complete(self) -> None:
        """information_fraction is clamped to 1.0 when n_collected >= n_planned."""
        rng = np.random.default_rng(0)
        group_a = rng.normal(0, 1, 60)
        group_b = rng.normal(0, 1, 60)  # 120 > 100
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert result.information_fraction == 1.0

    def test_information_fraction_is_ratio(self) -> None:
        """information_fraction = n_collected / n_planned when incomplete."""
        rng = np.random.default_rng(0)
        group_a = rng.normal(0, 1, 15)
        group_b = rng.normal(0, 1, 15)  # 30 / 100 = 0.30
        result = check_sufficiency([group_a, group_b], n_planned=100)
        assert abs(result.information_fraction - 0.30) < 1e-10


# ---------------------------------------------------------------------------
# sprt_boundaries tests
# ---------------------------------------------------------------------------


class TestSprtBoundaries:
    """Tests for sprt_boundaries(alpha, beta)."""

    def test_upper_boundary_approximately_2_77(self) -> None:
        """Upper boundary is approximately log((1-beta)/alpha) ~= 2.77 for defaults."""
        upper, lower = sprt_boundaries(alpha=0.05, beta=0.20)
        assert abs(upper - 2.77) < 0.01, f"Expected upper ~2.77, got {upper}"

    def test_lower_boundary_approximately_neg_1_56(self) -> None:
        """Lower boundary is approximately log(beta/(1-alpha)) ~= -1.56 for defaults."""
        upper, lower = sprt_boundaries(alpha=0.05, beta=0.20)
        assert abs(lower - (-1.56)) < 0.01, f"Expected lower ~-1.56, got {lower}"

    def test_upper_greater_than_lower(self) -> None:
        """Upper boundary must be greater than lower boundary."""
        upper, lower = sprt_boundaries(alpha=0.05, beta=0.20)
        assert upper > lower


# ---------------------------------------------------------------------------
# check_sufficiency_sprt tests
# ---------------------------------------------------------------------------


class TestCheckSufficiencySprt:
    """Tests for check_sufficiency_sprt (SPRT-based)."""

    def test_sufficient_when_llr_exceeds_upper_boundary(self) -> None:
        """When LLR >= upper boundary, decision is 'sufficient'."""
        rng = np.random.default_rng(42)
        # Observations strongly consistent with mu1 (large effect)
        observations = rng.normal(5.0, 1.0, 200)
        result = check_sufficiency_sprt(
            observations=observations,
            mu0=0.0,
            mu1=5.0,
            sigma=1.0,
            n_planned=200,
        )
        assert result.decision == "sufficient", f"Expected 'sufficient' with extreme LLR, got '{result.decision}'"
        assert result.method == "sprt"

    def test_futile_when_llr_falls_below_lower_boundary(self) -> None:
        """When LLR <= lower boundary, decision is 'futile'."""
        rng = np.random.default_rng(42)
        # Observations centered on mu0 (no effect) — accumulates evidence against H1
        observations = rng.normal(0.0, 1.0, 300)
        result = check_sufficiency_sprt(
            observations=observations,
            mu0=0.0,
            mu1=5.0,
            sigma=1.0,
            n_planned=300,
        )
        assert result.decision == "futile", (
            f"Expected 'futile' with null-hypothesis observations, got '{result.decision}'"
        )
        assert result.method == "sprt"

    def test_insufficient_for_ambiguous_data(self) -> None:
        """Small n with ambiguous data (tiny effect, large sigma) stays 'insufficient'."""
        rng = np.random.default_rng(0)
        # mu0=0, mu1=1, sigma=5 -> very small signal-to-noise ratio; LLR stays near zero
        observations = rng.normal(0.5, 1.0, 5)
        result = check_sufficiency_sprt(
            observations=observations,
            mu0=0.0,
            mu1=1.0,
            sigma=5.0,
            n_planned=200,
        )
        assert result.decision == "insufficient", f"Expected 'insufficient' for ambiguous data, got '{result.decision}'"

    def test_sprt_result_always_has_method_sprt(self) -> None:
        """check_sufficiency_sprt always returns method='sprt'."""
        rng = np.random.default_rng(0)
        observations = rng.normal(0, 1, 10)
        result = check_sufficiency_sprt(observations=observations, mu0=0.0, mu1=1.0, sigma=1.0, n_planned=100)
        assert result.method == "sprt"


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Tests that identical inputs produce identical outputs."""

    def test_check_sufficiency_is_deterministic(self) -> None:
        """Two calls with identical inputs return identical SufficiencyDecision."""
        rng = np.random.default_rng(42)
        group_a = rng.normal(0, 1, 25)
        group_b = rng.normal(5, 1, 25)
        result1 = check_sufficiency([group_a, group_b], n_planned=100)
        result2 = check_sufficiency([group_a, group_b], n_planned=100)
        assert result1 == result2, "Non-deterministic: two calls returned different results"

    def test_check_sufficiency_sprt_is_deterministic(self) -> None:
        """Two SPRT calls with identical inputs return identical SufficiencyDecision."""
        rng = np.random.default_rng(0)
        observations = rng.normal(2.5, 1.0, 50)
        result1 = check_sufficiency_sprt(observations, mu0=0.0, mu1=5.0, sigma=1.0, n_planned=100)
        result2 = check_sufficiency_sprt(observations, mu0=0.0, mu1=5.0, sigma=1.0, n_planned=100)
        assert result1 == result2, "Non-deterministic: two SPRT calls returned different results"
