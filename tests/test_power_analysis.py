"""TDD tests for power analysis domain functions.

Tests cover t-test, ANOVA, and chi-square sample size computations
via statsmodels, plus the select_and_run_power_analysis dispatcher.
"""

from __future__ import annotations

from gpd.exp.contracts.experiment import (
    BetweenSubjectsDesign,
    FactorialDesign,
    VariableType,
    WithinSubjectsDesign,
)
from gpd.exp.domain.power_analysis import (
    PowerAnalysisResult,
    compute_sample_size_anova,
    compute_sample_size_chi_square,
    compute_sample_size_ttest,
    select_and_run_power_analysis,
)


class TestTTest:
    """Tests for compute_sample_size_ttest."""

    def test_ttest_medium_effect_size(self) -> None:
        """Cohen's benchmark: d=0.5, alpha=0.05, power=0.80 -> n=64 per group."""
        result = compute_sample_size_ttest(effect_size=0.5, alpha=0.05, power=0.80)
        assert isinstance(result, PowerAnalysisResult)
        assert result.sample_size_per_group == 64
        assert result.total_sample_size == 128
        assert result.k_groups == 2
        assert result.test_type == "t_test"

    def test_ttest_large_effect_size(self) -> None:
        """Large effect (d=0.8) should produce smaller N (~26 per group)."""
        result = compute_sample_size_ttest(effect_size=0.8, alpha=0.05, power=0.80)
        assert result.sample_size_per_group == 26
        assert result.total_sample_size == 52

    def test_ttest_small_effect_size(self) -> None:
        """Small effect (d=0.2) should produce larger N (~394 per group)."""
        result = compute_sample_size_ttest(effect_size=0.2, alpha=0.05, power=0.80)
        assert result.sample_size_per_group == 394
        assert result.total_sample_size == 788


class TestAnova:
    """Tests for compute_sample_size_anova."""

    def test_anova_three_groups(self) -> None:
        """ANOVA with 3 groups and medium effect should produce sensible N."""
        result = compute_sample_size_anova(effect_size=0.25, k_groups=3, alpha=0.05, power=0.80)
        assert isinstance(result, PowerAnalysisResult)
        assert result.k_groups == 3
        assert result.total_sample_size == result.sample_size_per_group * 3
        assert result.test_type == "anova"


class TestChiSquare:
    """Tests for compute_sample_size_chi_square."""

    def test_chi_square(self) -> None:
        """Chi-square with medium effect and 4 bins should produce positive N."""
        result = compute_sample_size_chi_square(effect_size=0.3, n_bins=4, alpha=0.05, power=0.80)
        assert isinstance(result, PowerAnalysisResult)
        assert result.total_sample_size > 0
        assert result.test_type == "chi_square"


class TestSelectAndRun:
    """Tests for select_and_run_power_analysis dispatcher."""

    def test_select_between_subjects_two_groups(self) -> None:
        """BetweenSubjectsDesign with 2 groups + CONTINUOUS DV -> t-test."""
        design = BetweenSubjectsDesign(groups=["A", "B"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.CONTINUOUS,
            predicted_effect_size=0.5,
        )
        assert result.test_type == "t_test"
        assert result.k_groups == 2

    def test_select_between_subjects_multi_groups(self) -> None:
        """BetweenSubjectsDesign with 3+ groups -> ANOVA."""
        design = BetweenSubjectsDesign(groups=["A", "B", "C"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.CONTINUOUS,
            predicted_effect_size=0.5,
        )
        assert result.test_type == "anova"
        assert result.k_groups == 3

    def test_select_categorical_dv(self) -> None:
        """CATEGORICAL DV with between-subjects -> chi-square."""
        design = BetweenSubjectsDesign(groups=["A", "B"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.CATEGORICAL,
            predicted_effect_size=0.3,
        )
        assert result.test_type == "chi_square"

    def test_select_binary_dv(self) -> None:
        """BINARY DV with between-subjects -> chi-square."""
        design = BetweenSubjectsDesign(groups=["A", "B"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.BINARY,
            predicted_effect_size=0.3,
        )
        assert result.test_type == "chi_square"

    def test_within_subjects_paired(self) -> None:
        """Within-subjects with 2 conditions uses paired t-test."""
        design = WithinSubjectsDesign(conditions=["baseline", "treatment"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.CONTINUOUS,
            predicted_effect_size=0.5,
        )
        assert result.test_type == "paired_t_test"
        # Paired designs need fewer total subjects (n per group, not n*2)
        assert result.total_sample_size == result.sample_size_per_group

    def test_within_subjects_multi_conditions(self) -> None:
        """Within-subjects with 3+ conditions uses ANOVA."""
        design = WithinSubjectsDesign(conditions=["baseline", "low", "high"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.CONTINUOUS,
            predicted_effect_size=0.5,
        )
        assert result.test_type == "anova"
        assert result.k_groups == 3

    def test_factorial_design(self) -> None:
        """FactorialDesign dispatches to ANOVA with cells = product of levels."""
        design = FactorialDesign(
            factors=["caffeine", "sleep"],
            levels_per_factor={
                "caffeine": ["none", "low", "high"],
                "sleep": ["4h", "8h"],
            },
        )
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type=VariableType.CONTINUOUS,
            predicted_effect_size=0.5,
        )
        assert result.test_type == "anova"
        assert result.k_groups == 6  # 3 x 2

    def test_string_dv_type(self) -> None:
        """String dv_type values are accepted and normalized."""
        design = BetweenSubjectsDesign(groups=["A", "B"])
        result = select_and_run_power_analysis(
            study_design=design,
            dv_type="continuous",
            predicted_effect_size=0.5,
        )
        assert result.test_type == "t_test"

    def test_effect_size_bounds(self) -> None:
        """Minimum sample_size_per_group >= 1 for any valid inputs."""
        result = compute_sample_size_ttest(effect_size=3.0, alpha=0.05, power=0.80)
        assert result.sample_size_per_group >= 1
