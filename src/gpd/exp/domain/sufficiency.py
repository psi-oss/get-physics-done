"""Sequential and budget-based sufficiency domain functions.

Implements two complementary sufficiency gates:

1. Sequential analysis (O'Brien-Fleming + SPRT) — used by Plan 04's
   SufficiencyCheckNode to gate interim stopping based on statistical
   evidence. Pure scipy/numpy domain: no LLM, no side effects.

2. Budget/quality-based sufficiency (check_sufficiency_budget) — used by
   the existing SufficiencyCheckNode.run() in execute.py to assess whether
   enough validated data points have been collected given budget and time
   constraints.

All functions are deterministic with no I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm, ttest_ind

from gpd.exp.contracts.data import QualityStatus

#: Minimum number of validated data points required before sufficiency is possible.
MINIMUM_SAMPLE_FLOOR: int = 10

#: Tolerance for matching interim analysis fractions (absolute difference).
INTERIM_FRACTION_TOLERANCE: float = 0.05

#: Fraction of sample_size_target below which futility is checked.
FUTILITY_THRESHOLD_FRACTION: float = 0.2

#: Minutes remaining below which futility can be declared.
FUTILITY_MINUTES_REMAINING: float = 120


# ---------------------------------------------------------------------------
# Sequential analysis: SufficiencyDecision + O'Brien-Fleming + SPRT
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SufficiencyDecision:
    """Result of a sequential-analysis sufficiency check.

    Attributes:
        decision: One of 'sufficient', 'insufficient', or 'futile'.
        n_collected: Total observations collected across all groups.
        n_planned: Planned total sample size.
        information_fraction: n_collected / n_planned, clamped to 1.0.
        method: Analysis method used ('obrien_fleming' | 'sprt' | 'complete').
        alpha_spent: Cumulative alpha spent at this check (None if no interim
            check was run, i.e. not at an interim fraction).
    """

    decision: str
    n_collected: int
    n_planned: int
    information_fraction: float
    method: str
    alpha_spent: float | None = None


def obrien_fleming_alpha_spend(t: float, alpha: float = 0.05) -> float:
    """Cumulative O'Brien-Fleming alpha spent at information fraction t.

    Formula: 2 * (1 - norm.cdf(norm.ppf(1 - alpha/2) / sqrt(t)))

    At t=0.0 returns 0.0. At t=1.0 returns exactly alpha.

    Args:
        t: Information fraction (n_collected / n_planned). 0 <= t <= 1.
        alpha: Total significance level (default 0.05).

    Returns:
        Cumulative alpha spent at this information fraction.
    """
    if t <= 0:
        return 0.0
    z = norm.ppf(1 - alpha / 2)
    return float(2 * (1 - norm.cdf(z / math.sqrt(t))))


def check_sufficiency(
    group_data: list[np.ndarray],
    n_planned: int,
    alpha: float = 0.05,
    beta: float = 0.20,
    interim_fractions: tuple[float, ...] = (0.5, 1.0),
) -> SufficiencyDecision:
    """Check statistical sufficiency using O'Brien-Fleming alpha-spending.

    Decision logic:
      1. If n_collected >= n_planned: return 'sufficient' with method='complete'.
      2. If not at a pre-planned interim fraction (within 5% tolerance):
         return 'insufficient' (no test run).
      3. At an interim fraction: compute O'Brien-Fleming critical value, run
         ttest_ind on two groups. If |t_stat| >= z_crit: 'sufficient'.
         Otherwise: 'insufficient'.
      4. For single group or groups with n < 2: 'insufficient' (not enough data).

    Args:
        group_data: List of np.ndarrays, one per group.
        n_planned: Total planned sample size across all groups.
        alpha: Significance level (default 0.05).
        beta: Desired power complement (default 0.20, unused in OBF but
            included for API consistency with check_sufficiency_sprt).
        interim_fractions: Pre-planned fractions at which to evaluate stopping.
            Fractions < 1.0 are interim checks; 1.0 is the final analysis.

    Returns:
        SufficiencyDecision frozen dataclass.
    """
    n_collected = sum(len(g) for g in group_data)
    t = n_collected / n_planned if n_planned > 0 else 0.0

    # 1. Full collection: always sufficient
    if n_collected >= n_planned:
        return SufficiencyDecision(
            decision="sufficient",
            n_collected=n_collected,
            n_planned=n_planned,
            information_fraction=1.0,
            method="complete",
            alpha_spent=alpha,
        )

    # Guard: no data or single sample cannot compute interim test
    if n_collected == 0 or t <= 0:
        return SufficiencyDecision(
            decision="insufficient",
            n_collected=n_collected,
            n_planned=n_planned,
            information_fraction=max(0.0, t),
            method="obrien_fleming",
            alpha_spent=None,
        )

    # 2. Only check at pre-planned interim fractions (within 5% tolerance)
    at_interim = any(abs(t - frac) < INTERIM_FRACTION_TOLERANCE for frac in interim_fractions if frac < 1.0)
    if not at_interim:
        return SufficiencyDecision(
            decision="insufficient",
            n_collected=n_collected,
            n_planned=n_planned,
            information_fraction=t,
            method="obrien_fleming",
            alpha_spent=None,
        )

    # 3. At interim fraction: O'Brien-Fleming test
    alpha_spent = obrien_fleming_alpha_spend(t, alpha)
    z_crit = norm.ppf(1 - alpha_spent / 2) if alpha_spent > 0 else float("inf")

    # Require exactly 2 groups with at least 2 observations each
    if len(group_data) == 2 and len(group_data[0]) >= 2 and len(group_data[1]) >= 2:
        test_result = ttest_ind(group_data[0], group_data[1])
        z_stat = abs(float(test_result.statistic))
        if z_stat >= z_crit:
            return SufficiencyDecision(
                decision="sufficient",
                n_collected=n_collected,
                n_planned=n_planned,
                information_fraction=t,
                method="obrien_fleming",
                alpha_spent=alpha_spent,
            )

    # Not enough statistical evidence or not applicable
    return SufficiencyDecision(
        decision="insufficient",
        n_collected=n_collected,
        n_planned=n_planned,
        information_fraction=t,
        method="obrien_fleming",
        alpha_spent=alpha_spent,
    )


def sprt_boundaries(
    alpha: float = 0.05,
    beta: float = 0.20,
) -> tuple[float, float]:
    """Compute SPRT log-likelihood ratio decision boundaries.

    Based on Wald (1947):
      upper = log((1 - beta) / alpha)   ~= 2.77 for defaults
      lower = log(beta / (1 - alpha))   ~= -1.56 for defaults

    Args:
        alpha: Type I error rate (default 0.05).
        beta: Type II error rate (default 0.20).

    Returns:
        Tuple (upper_boundary, lower_boundary).
        LLR >= upper: reject H0 -> decision 'sufficient'.
        LLR <= lower: accept H0 -> decision 'futile'.
        lower < LLR < upper: continue collecting -> 'insufficient'.
    """
    upper = float(np.log((1 - beta) / alpha))
    lower = float(np.log(beta / (1 - alpha)))
    return upper, lower


def check_sufficiency_sprt(
    observations: np.ndarray,
    mu0: float,
    mu1: float,
    sigma: float,
    n_planned: int,
    alpha: float = 0.05,
    beta: float = 0.20,
) -> SufficiencyDecision:
    """Check statistical sufficiency using Wald's SPRT for normal data.

    Computes the log-likelihood ratio (LLR) for testing H0: mu=mu0 vs H1: mu=mu1
    with known sigma. The LLR is compared to the SPRT boundaries.

    LLR formula for normal data:
        LLR = (mu1 - mu0) / sigma^2 * sum(obs) - n * (mu1 + mu0) * (mu1 - mu0) / (2 * sigma^2)

    Decision:
      - LLR >= upper_boundary: decision='sufficient'
      - LLR <= lower_boundary: decision='futile'
      - lower < LLR < upper:   decision='insufficient'

    Args:
        observations: np.ndarray of all observations collected so far.
        mu0: Null hypothesis mean.
        mu1: Alternative hypothesis mean.
        sigma: Known (or estimated) standard deviation.
        n_planned: Planned total sample size (used for information_fraction).
        alpha: Type I error rate (default 0.05).
        beta: Type II error rate (default 0.20).

    Returns:
        SufficiencyDecision with method='sprt'.
    """
    n = len(observations)
    t = min(n / n_planned, 1.0) if n_planned > 0 else 1.0

    upper, lower = sprt_boundaries(alpha, beta)

    # Compute log-likelihood ratio
    llr = (mu1 - mu0) / sigma**2 * float(observations.sum()) - n * (mu1 + mu0) * (mu1 - mu0) / (2 * sigma**2)

    if llr >= upper:
        decision = "sufficient"
    elif llr <= lower:
        decision = "futile"
    else:
        decision = "insufficient"

    return SufficiencyDecision(
        decision=decision,
        n_collected=n,
        n_planned=n_planned,
        information_fraction=t,
        method="sprt",
        alpha_spent=None,
    )


# ---------------------------------------------------------------------------
# Budget/quality-based sufficiency (Phase 3 implementation)
# Used by SufficiencyCheckNode.run() in execute.py
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SufficiencyResult:
    """Result of the budget-based three-outcome sufficiency check.

    Attributes:
        outcome: One of 'sufficient', 'insufficient', or 'futile'.
        validated_count: Number of VALIDATED data points in the input.
        reason: Non-empty human-readable explanation of the outcome.
    """

    outcome: str
    validated_count: int
    reason: str


def check_sufficiency_budget(
    data_points: Sequence[object],
    sample_size_target: int,
    remaining_budget_cents: int,
    cost_per_bounty_cents: int,
    minutes_remaining: float,
) -> SufficiencyResult:
    """Determine whether data collection is sufficient, progressing, or futile.

    Decision logic (applied in this exact order):
      1. Futility check: n < target*0.2 AND cannot afford more bounties AND < 120 min remain
      2. Floor check: n < MINIMUM_SAMPLE_FLOOR (10) -> insufficient
      3. Target check: n >= sample_size_target -> sufficient
      4. Default -> insufficient

    Args:
        data_points: All collected data points; only VALIDATED are counted.
        sample_size_target: Required validated points to reach sufficiency.
        remaining_budget_cents: Budget remaining in integer cents.
        cost_per_bounty_cents: Cost of one additional bounty in integer cents.
        minutes_remaining: Minutes left until the experiment deadline.

    Returns:
        SufficiencyResult with outcome, validated_count, and a reason string.
    """
    # Filter to VALIDATED data points only
    validated = [dp for dp in data_points if getattr(dp, "quality_status", None) == QualityStatus.VALIDATED]
    n = len(validated)

    can_afford_more: bool = remaining_budget_cents >= cost_per_bounty_cents

    # --- Step 1: Futility check ---
    futility_threshold = sample_size_target * FUTILITY_THRESHOLD_FRACTION
    if n < futility_threshold and not can_afford_more and minutes_remaining < FUTILITY_MINUTES_REMAINING:
        return SufficiencyResult(
            outcome="futile",
            validated_count=n,
            reason=(
                f"Collection is futile: only {n} validated points "
                f"(need {futility_threshold:.0f}+ to make progress toward target {sample_size_target}), "
                f"no remaining budget, and only {minutes_remaining:.0f} minutes left."
            ),
        )

    # --- Step 2: Floor check ---
    if n < MINIMUM_SAMPLE_FLOOR:
        return SufficiencyResult(
            outcome="insufficient",
            validated_count=n,
            reason=(f"Insufficient data: {n} validated points is below the minimum floor of {MINIMUM_SAMPLE_FLOOR}."),
        )

    # --- Step 3: Target check ---
    if n >= sample_size_target:
        return SufficiencyResult(
            outcome="sufficient",
            validated_count=n,
            reason=(
                f"Data collection is sufficient: {n} validated points "
                f"meets or exceeds the target of {sample_size_target}."
            ),
        )

    # --- Step 4: Default -> insufficient ---
    remaining_needed = sample_size_target - n
    return SufficiencyResult(
        outcome="insufficient",
        validated_count=n,
        reason=(
            f"Insufficient data: {n} validated points, need {remaining_needed} more "
            f"to reach target of {sample_size_target}."
        ),
    )
