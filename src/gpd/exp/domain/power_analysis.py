"""Layer 1 power analysis domain functions.

Computes sample sizes for t-test, ANOVA, and chi-square designs using
statsmodels. Pure domain logic: deterministic, no side effects.

All functions return PowerAnalysisResult frozen dataclasses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from statsmodels.stats.power import FTestAnovaPower, GofChisquarePower, TTestIndPower

from gpd.exp.contracts.experiment import (
    BetweenSubjectsDesign,
    FactorialDesign,
    VariableType,
    WithinSubjectsDesign,
)


@dataclass(frozen=True)
class PowerAnalysisResult:
    """Result of a statistical power analysis computation."""

    test_type: str
    effect_size: float
    alpha: float
    power: float
    sample_size_per_group: int
    total_sample_size: int
    k_groups: int
    reasoning: str


def compute_sample_size_ttest(
    effect_size: float,
    alpha: float = 0.05,
    power: float = 0.80,
    paired: bool = False,
) -> PowerAnalysisResult:
    """Compute sample size for a two-sample t-test.

    Uses statsmodels TTestIndPower.solve_power with math.ceil rounding
    to ensure adequate power. Always returns at least 1 per group.

    For paired (within-subjects) designs, the effective effect size is
    inflated by sqrt(2) because within-subjects variance is lower
    (subjects serve as their own controls).
    """
    # Paired designs reduce variance: effective d ≈ d * sqrt(2)
    effective_d = effect_size * math.sqrt(2) if paired else effect_size

    analysis = TTestIndPower()
    raw_n = analysis.solve_power(effect_size=effective_d, alpha=alpha, power=power, alternative="two-sided")
    n_per_group = max(math.ceil(raw_n), 1)

    label = "Paired" if paired else "Independent"
    return PowerAnalysisResult(
        test_type="paired_t_test" if paired else "t_test",
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        sample_size_per_group=n_per_group,
        total_sample_size=n_per_group * 2 if not paired else n_per_group,
        k_groups=2,
        reasoning=f"{label} two-sample t-test: d={effect_size}, alpha={alpha}, power={power} -> n={n_per_group}/group",
    )


def compute_sample_size_anova(
    effect_size: float,
    k_groups: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> PowerAnalysisResult:
    """Compute sample size for one-way ANOVA (F-test).

    Uses statsmodels FTestAnovaPower.solve_power with math.ceil rounding.
    effect_size is Cohen's f.
    """
    analysis = FTestAnovaPower()
    raw_n = analysis.solve_power(
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        k_groups=k_groups,
    )
    n_per_group = max(math.ceil(raw_n), 1)

    return PowerAnalysisResult(
        test_type="anova",
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        sample_size_per_group=n_per_group,
        total_sample_size=n_per_group * k_groups,
        k_groups=k_groups,
        reasoning=f"One-way ANOVA F-test: f={effect_size}, k={k_groups}, alpha={alpha}, power={power} -> n={n_per_group}/group",
    )


def compute_sample_size_chi_square(
    effect_size: float,
    n_bins: int,
    alpha: float = 0.05,
    power: float = 0.80,
) -> PowerAnalysisResult:
    """Compute sample size for chi-square goodness-of-fit test.

    Uses statsmodels GofChisquarePower.solve_power with math.ceil rounding.
    effect_size is Cohen's w.
    """
    analysis = GofChisquarePower()
    raw_n = analysis.solve_power(
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        n_bins=n_bins,
    )
    n_total = max(math.ceil(raw_n), 1)

    return PowerAnalysisResult(
        test_type="chi_square",
        effect_size=effect_size,
        alpha=alpha,
        power=power,
        sample_size_per_group=n_total,
        total_sample_size=n_total,
        k_groups=1,
        reasoning=f"Chi-square GOF: w={effect_size}, n_bins={n_bins}, alpha={alpha}, power={power} -> N={n_total}",
    )


def select_and_run_power_analysis(
    study_design: BetweenSubjectsDesign | WithinSubjectsDesign | FactorialDesign,
    dv_type: VariableType | str,
    predicted_effect_size: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> PowerAnalysisResult:
    """Select the appropriate power analysis based on study design and DV type.

    Dispatch rules:
    - BetweenSubjectsDesign + 2 groups + CONTINUOUS -> independent t-test
    - BetweenSubjectsDesign + 3+ groups + CONTINUOUS -> ANOVA (convert d to f: f = d/2)
    - BetweenSubjectsDesign + CATEGORICAL/BINARY -> chi-square
    - WithinSubjectsDesign + 2 conditions -> paired t-test (inflated effect size)
    - WithinSubjectsDesign + 3+ conditions -> repeated-measures ANOVA
    - FactorialDesign -> ANOVA with k = product of all factor levels
    """
    # Normalize string dv_type to enum
    if isinstance(dv_type, str):
        dv_type = VariableType(dv_type)

    if isinstance(study_design, BetweenSubjectsDesign):
        k = len(study_design.groups)

        # Categorical or binary DV -> chi-square
        if dv_type in (VariableType.CATEGORICAL, VariableType.BINARY):
            return compute_sample_size_chi_square(
                effect_size=predicted_effect_size,
                n_bins=k,
                alpha=alpha,
                power=power,
            )

        # Continuous/ordinal DV
        if k >= 3:
            # Convert Cohen's d to Cohen's f for ANOVA: f = d/2
            cohens_f = predicted_effect_size / 2
            return compute_sample_size_anova(
                effect_size=cohens_f,
                k_groups=k,
                alpha=alpha,
                power=power,
            )

        # 2-group between-subjects with continuous DV -> t-test
        return compute_sample_size_ttest(
            effect_size=predicted_effect_size,
            alpha=alpha,
            power=power,
        )

    if isinstance(study_design, WithinSubjectsDesign):
        k = len(study_design.conditions)

        if k <= 2:
            # Paired t-test: subjects serve as own controls, variance is lower
            return compute_sample_size_ttest(
                effect_size=predicted_effect_size,
                alpha=alpha,
                power=power,
                paired=True,
            )

        # 3+ conditions: repeated-measures ANOVA (use ANOVA with paired inflation)
        # Within-subjects designs need fewer subjects; inflate f by sqrt(2)
        cohens_f = (predicted_effect_size / 2) * math.sqrt(2)
        return compute_sample_size_anova(
            effect_size=cohens_f,
            k_groups=k,
            alpha=alpha,
            power=power,
        )

    if isinstance(study_design, FactorialDesign):
        # Total cells = product of levels across all factors
        k_cells = 1
        for levels in study_design.levels_per_factor.values():
            k_cells *= len(levels)

        # Use ANOVA with total cells as groups
        cohens_f = predicted_effect_size / 2
        return compute_sample_size_anova(
            effect_size=cohens_f,
            k_groups=k_cells,
            alpha=alpha,
            power=power,
        )

    # Unreachable if type annotation is respected, but defensive fallback
    return compute_sample_size_ttest(
        effect_size=predicted_effect_size,
        alpha=alpha,
        power=power,
    )
